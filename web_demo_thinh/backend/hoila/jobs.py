"""Hàng đợi lượt hỏi và giám sát worker. Dựa trên pvvqa/web/jobs.py của Khoa.

Khác biệt: đường dẫn ảnh lấy qua DemoData.image_path (ảnh mẫu hoặc ảnh tải lên); ảnh tải lên bị xoá
ngay khi lượt hỏi dùng nó kết thúc; thông điệp lỗi tiếng Việt.
"""
import copy
import logging
import multiprocessing as mp
import queue
import threading
import time
import uuid
from collections import deque

from .normalize import normalize_vi
from .worker import run_worker

TERMINAL = {'succeeded', 'partial', 'failed', 'cancelled'}


class JobManager:
    def __init__(self, cfg, data, disabled=False):
        self.cfg, self.data, self.disabled = cfg, data, disabled
        self.jobs, self.waiting = {}, deque()
        self.active = None
        self.ready = False
        self.runtime_error = 'Chế độ chỉ xem nội dung: không chạy model.' if disabled else None
        self.gpu = None
        self.provenance = {}
        self.memory = None
        self.lock = threading.RLock()
        self.stop = threading.Event()
        self.process = None
        self.thread = None
        self.ctx = mp.get_context('spawn')

    def start(self):
        if self.disabled:
            return
        self._spawn()
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def _spawn(self):
        self.ready = False
        self.dead_at = None
        self.started_at = time.monotonic()
        self.last_event_at = self.started_at
        self.inbox, self.outbox = self.ctx.Queue(), self.ctx.Queue()
        self.cancel_event = self.ctx.Event()
        sample = next(iter(self.data.samples.values()))
        warmup = dict(image_path=str(self.data.image_path(sample['image_id'])), question=sample['question'])
        self.process = self.ctx.Process(target=run_worker, args=(self.cfg, self.inbox, self.outbox, self.cancel_event, warmup), daemon=True)
        self.process.start()

    def close(self):
        self.stop.set()
        if self.thread:
            self.thread.join(timeout=2)
        self._kill()

    def _kill(self):
        self.ready = False
        if self.process:
            self.process.terminate()
            self.process.join(timeout=5)
            if self.process.is_alive():
                self.process.kill()
                self.process.join(timeout=5)
        for name in ['inbox', 'outbox']:
            channel = getattr(self, name, None)
            if channel:
                channel.close()

    def runtime(self):
        with self.lock:
            return dict(inference_ready=self.ready, gpu=self.gpu, device_name=self.gpu,
                        state='ready' if self.ready else 'unavailable' if self.runtime_error else 'warming_up',
                        message=self.runtime_error, queue_depth=len(self.waiting), active_job=self.active,
                        execution_device=self.cfg['device'], provenance=self.provenance, memory=self.memory,
                        uploads_enabled=not self.disabled,
                        profile=dict(dtype=self.cfg['dtype'], attention=self.cfg['attention'],
                                     use_cache=self.cfg['use_cache'], max_new_tokens=self.cfg['max_new_tokens']))

    def submit(self, image_id, question_id, question, model_ids):
        resolved, reference = self.data.resolve_input(image_id, question_id, question)
        if not model_ids or len(model_ids) > len(self.cfg['models']) or len(set(model_ids)) != len(model_ids) or set(model_ids) - self.cfg['models'].keys():
            raise ValueError(f"Chọn từ 1 đến {len(self.cfg['models'])} mô hình khác nhau.")
        with self.lock:
            if not self.ready:
                raise RuntimeError('Model chưa sẵn sàng. Hãy thử lại sau ít phút.')
            if len(self.waiting) >= self.cfg['queue_size']:
                raise OverflowError('Hàng đợi đang đầy. Hãy thử lại sau.')
            job_id = str(uuid.uuid4())
            order = [key for key in self.cfg['models'] if key in model_ids]
            job = dict(job_id=job_id, status='queued', image_id=image_id, question_id=question_id,
                       question=resolved, input_revision=job_id, created_at=time.monotonic(),
                       reference=reference, outputs=[dict(model_id=key, status='pending') for key in order],
                       image_source='upload' if self.data.is_upload(image_id) else 'sample')
            sample = self.data.samples.get(question_id, {})
            if sample.get('expected_answer'):
                job['expected_answer'] = sample['expected_answer']
            self.jobs[job_id] = job
            self.waiting.append(job_id)
            return self.get(job_id)

    def get(self, job_id):
        with self.lock:
            if job_id not in self.jobs:
                raise KeyError(job_id)
            result = copy.deepcopy(self.jobs[job_id])
            for key in ['created_at', 'started_at', 'finished_at']:
                result.pop(key, None)
            if 'started_at' not in self.jobs[job_id]:
                result.pop('reference', None)
                result.pop('expected_answer', None)
            return result

    def cancel(self, job_id):
        with self.lock:
            job = self.jobs[job_id]
            if job['status'] not in TERMINAL:
                job['cancel_requested'] = True
                if job_id == self.active:
                    self.cancel_event.set()
                else:
                    self.waiting.remove(job_id)
                    self._finish(job, 'cancelled')
            return self.get(job_id)

    def _finish(self, job, status=None):
        successes = sum(out['status'] == 'succeeded' for out in job['outputs'])
        job['status'] = status or ('partial' if 0 < successes < len(job['outputs']) else
                                   'succeeded' if successes == len(job['outputs']) else
                                   'cancelled' if job.get('cancel_requested') else 'failed')
        for out in job['outputs']:
            if out['status'] in {'pending', 'generating', 'loading'}:
                out['status'] = 'cancelled' if job['status'] == 'cancelled' else 'failed'
                out.setdefault('error', dict(code='CANCELLED' if job['status'] == 'cancelled' else 'NOT_COMPLETED',
                                            message='Mô hình này chưa chạy xong.'))
        job['finished_at'] = time.monotonic()
        job['total_ms'] = (job['finished_at'] - job['created_at']) * 1000
        self._release_upload(job)

    def _release_upload(self, job):
        """Xoá ảnh tải lên ngay khi không còn lượt hỏi nào đang chờ/chạy dùng nó."""
        image_id = job['image_id']
        if not self.data.is_upload(image_id) or not self.data.uploads:
            return
        still_used = any(other['image_id'] == image_id and other['status'] not in TERMINAL
                         for other in self.jobs.values())
        if not still_used:
            self.data.uploads.remove(image_id)

    def _event(self, event):
        kind = event['type']
        if kind == 'ready':
            self.ready, self.runtime_error = True, None
            self.gpu, self.provenance = event['gpu'], event['provenance']
            self.memory = event.get('memory')
            return
        if kind == 'fatal':
            self.runtime_error = event['message']
            return
        if event.get('job_id') != self.active:
            return
        job = self.jobs[self.active]
        self.last_event_at = time.monotonic()
        if kind == 'done':
            self._finish(job)
            self.active = None
            if event.get('restart'):
                self._kill()
                self._spawn()
            return
        out = next(out for out in job['outputs'] if out['model_id'] == event['model_id'])
        if kind == 'progress':
            out['status'] = event['status']
        elif kind == 'error':
            out.update(status='failed', error=dict(code=event['code'], message=event['message']))
        elif kind == 'result':
            out.update({key: val for key, val in event.items() if key not in {'type', 'job_id'}})
            out['status'] = 'succeeded'
            if job['reference'] is not None:
                out['normalized_exact_match'] = normalize_vi(out['answer']) == normalize_vi(job['reference'])

    def _tick(self):
        now = time.monotonic()
        for job_id in list(self.waiting):
            job = self.jobs[job_id]
            if now - job['created_at'] > self.cfg['queue_timeout']:
                self.waiting.remove(job_id)
                job['error'] = dict(code='QUEUE_TIMEOUT', message='Lượt hỏi chờ quá lâu. Hãy hỏi lại.')
                self._finish(job, 'failed')
        for job_id, job in list(self.jobs.items()):
            if job['status'] in TERMINAL and now - job['finished_at'] > self.cfg['job_ttl']:
                del self.jobs[job_id]
        if self.active and (now - self.last_event_at > self.cfg['model_timeout'] + 10 or
                            now - self.jobs[self.active]['started_at'] > self.cfg['job_timeout'] + 10):
            job = self.jobs[self.active]
            job['error'] = dict(code='INFERENCE_TIMEOUT', message='Worker quá thời gian và đang khởi động lại.')
            self._finish(job)
            self.active = None
            self._kill()
            self._spawn()
        if self.process and not self.process.is_alive() and not self.runtime_error:
            # Tiến trình con có thể thoát sau khi đã đẩy sự kiện cuối; chờ 1 giây để không mất sự kiện OOM.
            if self.dead_at is None:
                self.dead_at = now
            elif now - self.dead_at > 1:
                if self.active:
                    job = self.jobs[self.active]
                    job['error'] = dict(code='WORKER_EXITED', message='Worker model dừng bất ngờ.')
                    self._finish(job)
                    self.active = None
                self.ready = False
                self.runtime_error = 'Worker model đã dừng. Khởi động lại demo để tiếp tục.'
        if not self.ready and not self.runtime_error and now - self.started_at > self.cfg['startup_timeout']:
            self._kill()
            self.runtime_error = 'Nạp model quá thời gian. Xem log của server và khởi động lại demo.'
        if self.ready and self.active is None and self.waiting:
            self.active = self.waiting.popleft()
            job = self.jobs[self.active]
            path = self.data.image_path(job['image_id'])
            if path is None:
                job['error'] = dict(code='UPLOAD_EXPIRED', message='Ảnh tải lên đã hết hạn. Hãy tải lại ảnh.')
                self._finish(job, 'failed')
                self.active = None
                return
            job.update(status='running', started_at=now, queued_ms=(now - job['created_at']) * 1000)
            self.cancel_event.clear()
            self.last_event_at = now
            self.inbox.put(dict(job_id=self.active, image_path=str(path),
                                question=job['question'], model_ids=[out['model_id'] for out in job['outputs']]))

    def _loop(self):
        while not self.stop.is_set():
            try:
                try:
                    event = self.outbox.get(timeout=0.1)
                except queue.Empty:
                    event = None
                with self.lock:
                    if event:
                        self._event(event)
                    self._tick()
            except Exception:
                logging.exception('Model supervisor failed')
                with self.lock:
                    if self.active:
                        self._finish(self.jobs[self.active], 'failed')
                        self.active = None
                    self.runtime_error = 'Bộ giám sát model đã dừng. Khởi động lại demo để tiếp tục.'
                    self._kill()
                return

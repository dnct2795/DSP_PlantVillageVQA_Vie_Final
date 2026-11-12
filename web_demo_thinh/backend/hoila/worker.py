"""Tiến trình worker chạy model. Dựa trên pvvqa/web/worker.py của Khoa; nhận biết OOM trên cả CUDA lẫn MPS."""
import logging
import time
import traceback


def is_oom(exc):
    try:
        import torch
        if isinstance(exc, torch.cuda.OutOfMemoryError):
            return True
    except Exception:
        pass
    return isinstance(exc, RuntimeError) and 'out of memory' in str(exc).lower()


def run_worker(cfg, inputs, outputs, cancel, warmup):
    """Spawn target. Trạng thái thiết bị không bao giờ vượt qua ranh giới tiến trình."""
    try:
        from .inference import ModelService
        service = ModelService(cfg)
        service.generate('nora', warmup['image_path'], warmup['question'], cancel,
                         time.monotonic() + cfg['startup_timeout'])
        outputs.put(dict(type='ready', gpu=service.device_name, provenance=service.provenance,
                         memory=service.memory_info()))
    except Exception:
        logging.exception('Model initialization failed')
        outputs.put(dict(type='fatal', message='Không khởi động được model. Xem log của server.'))
        return
    while True:
        task = inputs.get()
        if task is None:
            return
        job_id = task['job_id']
        started = time.monotonic()
        for model_id in task['model_ids']:
            if cancel.is_set():
                break
            outputs.put(dict(type='progress', job_id=job_id, model_id=model_id, status='generating'))
            try:
                deadline = min(started + cfg['job_timeout'], time.monotonic() + cfg['model_timeout'])
                # Chỉ ảnh, câu hỏi và adapter được chọn đi vào dịch vụ model.
                result = service.generate(model_id, task['image_path'], task['question'], cancel, deadline)
                outputs.put(dict(type='result', job_id=job_id, model_id=model_id, **result))
            except Exception as exc:
                logging.error('Model request failed: %s\n%s', type(exc).__name__, traceback.format_exc())
                code = ('CANCELLED' if isinstance(exc, InterruptedError) else
                        'INFERENCE_TIMEOUT' if isinstance(exc, TimeoutError) else
                        'DEVICE_OOM' if is_oom(exc) else 'INFERENCE_FAILED')
                outputs.put(dict(type='error', job_id=job_id, model_id=model_id, code=code,
                                 message={'CANCELLED': 'Lượt hỏi đã bị huỷ.',
                                          'INFERENCE_TIMEOUT': 'Model chạy quá thời gian cho phép.',
                                          'DEVICE_OOM': 'Máy hết bộ nhớ cho model. Worker đang khởi động lại.'}.get(
                                              code, 'Model gặp lỗi. Xem log của server.')))
                if code in {'DEVICE_OOM', 'INFERENCE_FAILED'}:
                    outputs.put(dict(type='done', job_id=job_id, restart=True))
                    return
                break
        outputs.put(dict(type='done', job_id=job_id, restart=False))

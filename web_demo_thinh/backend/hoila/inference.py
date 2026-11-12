"""Dịch vụ model, chỉ import trong tiến trình worker. Dựa trên pvvqa/web/inference.py của Khoa.

Khác biệt so với bản Khoa:
- Thiết bị lấy từ config (`mps` trên Mac, `cuda:0` trên máy NVIDIA); dtype fp16 trên MPS.
- Số đo bộ nhớ: CUDA dùng peak allocated/reserved; MPS dùng torch.mps.current_allocated_memory /
  driver_allocated_memory (MPS không có thống kê đỉnh).
- Giữ nguyên mọi kiểm tra xuất xứ: hash nguồn PEFT NoRA, chế độ use_nora, SHA-256 adapter, processor giống nhau.
"""
import hashlib
import json
import platform
import subprocess
import time
from contextlib import nullcontext
from pathlib import Path

from .data import ROOT


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def seed_everything(seed):
    import random
    import numpy as np
    import torch
    from transformers import set_seed
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    set_seed(seed)


def device_label(backend):
    import torch
    if backend == 'cuda':
        return torch.cuda.get_device_name(0)
    if backend == 'mps':
        try:
            chip = subprocess.run(['sysctl', '-n', 'machdep.cpu.brand_string'], capture_output=True, text=True,
                                  timeout=5).stdout.strip()
        except Exception:
            chip = ''
        return f'{chip or platform.machine()} · MPS'
    return platform.processor() or 'CPU'


class ModelService:
    def __init__(self, cfg):
        import torch
        from huggingface_hub import snapshot_download
        from peft import PeftModel
        from transformers import AutoProcessor, Qwen3VLForConditionalGeneration
        from .nora import check_nora_capability

        self.device = cfg['device']
        self.backend = self.device.split(':')[0]
        if self.backend == 'cuda' and not torch.cuda.is_available():
            raise RuntimeError('CUDA không khả dụng. Đổi `device` trong configs/web_demo.yaml.')
        if self.backend == 'mps' and not torch.backends.mps.is_available():
            raise RuntimeError('MPS không khả dụng. Cần macOS trên chip Apple và PyTorch có MPS.')
        check_nora_capability()
        seed_everything(42)
        self.cfg = cfg
        self.torch = torch
        base = Path(cfg['base_model']).expanduser()
        if not base.is_dir():
            base = Path(snapshot_download(cfg['base_model'], revision=cfg['base_revision'], local_files_only=True))
        contexts = json.loads((ROOT / 'content/run_context.json').read_text())
        weights = ROOT / 'output_perf_weight'
        self.provenance = {}
        processor_hashes = None
        adapters = {key: value for key, value in cfg['models'].items() if key != 'baseline'}
        for model_id, model_cfg in adapters.items():
            run = weights / model_cfg['run']
            if not (run / 'adapter/adapter_config.json').is_file():
                raise RuntimeError(f'Thiếu adapter {model_cfg["run"]} trong output_perf_weight/. '
                                   'Chạy scripts/download_weights.sh.')
            adapter_cfg = json.loads((run / 'adapter/adapter_config.json').read_text())
            if type(adapter_cfg['use_nora']) is not type(model_cfg['use_nora']) or adapter_cfg['use_nora'] != model_cfg['use_nora']:
                raise RuntimeError(f'Adapter normalization mismatch for {model_id}')
            actual = digest(run / 'adapter/adapter_model.safetensors')
            expected = contexts[model_cfg['run']]['ablation_provenance']['adapter_sha256']
            if actual != expected:
                raise RuntimeError(f'Adapter checksum differs from report provenance for {model_id}')
            self.provenance[model_id] = dict(adapter_sha256=actual, report_verified=True)
            current = {p.name: digest(p) for p in (run / 'processor').iterdir() if p.is_file()}
            if processor_hashes is not None and current != processor_hashes:
                raise RuntimeError('Processors differ across adapters; a shared processor is unsafe.')
            processor_hashes = current
        self.provenance['baseline'] = dict(base_model=cfg['base_model'], base_revision=cfg['base_revision'],
                                           adapter_enabled=False)
        first = next(iter(adapters.values()))
        self.processor = AutoProcessor.from_pretrained(weights / first['run'] / 'processor', local_files_only=True)
        self.processor.tokenizer.padding_side = 'right'
        self.model = Qwen3VLForConditionalGeneration.from_pretrained(
            base, dtype=getattr(torch, cfg['dtype']), attn_implementation=cfg['attention'],
            device_map={'': self.device}, local_files_only=True)
        self.model.config.use_cache = cfg['use_cache']
        self.model = PeftModel.from_pretrained(self.model, weights / first['run'] / 'adapter',
                                               adapter_name='lora', is_trainable=False, local_files_only=True)
        for model_id in ['nora_init', 'nora']:
            self.model.load_adapter(weights / cfg['models'][model_id]['run'] / 'adapter',
                                    adapter_name=model_id, is_trainable=False, local_files_only=True)
        self.model.eval()
        if any(p.device.type != self.backend for p in self.model.parameters()):
            raise RuntimeError(f'The model must fit entirely on {self.backend}; CPU offload is disabled.')
        self.system_prompt = contexts[first['run']]['config']['prompt']['system']
        self.device_name = device_label(self.backend)

    # --- số đo thiết bị -------------------------------------------------
    def synchronize(self):
        if self.backend == 'cuda':
            self.torch.cuda.synchronize()
        elif self.backend == 'mps':
            self.torch.mps.synchronize()

    def reset_peak(self):
        if self.backend == 'cuda':
            self.torch.cuda.reset_peak_memory_stats()

    def peak_memory(self):
        if self.backend == 'cuda':
            return self.torch.cuda.max_memory_allocated(), self.torch.cuda.max_memory_reserved()
        if self.backend == 'mps':
            return self.torch.mps.current_allocated_memory(), self.torch.mps.driver_allocated_memory()
        return None, None

    def memory_info(self):
        if self.backend == 'cuda':
            free, total = self.torch.cuda.mem_get_info()
            return dict(free_bytes=free, total_bytes=total)
        if self.backend == 'mps':
            total = self.torch.mps.recommended_max_memory()
            used = self.torch.mps.driver_allocated_memory()
            return dict(free_bytes=max(total - used, 0), total_bytes=total)
        return None

    def generate(self, model_id, image_path, question, cancel, deadline):
        from PIL import Image
        from transformers import StoppingCriteria, StoppingCriteriaList
        from .generate import generate_answer

        class Stop(StoppingCriteria):
            def __call__(self, input_ids, scores, **kwargs):
                return cancel.is_set() or time.monotonic() > deadline

        start = time.perf_counter()
        if model_id not in self.cfg['models']:
            raise ValueError('Unknown model selection')
        if model_id != 'baseline':
            self.model.set_adapter(model_id)
        # PEFT restores the previous adapter state even if generation raises.
        with self.model.disable_adapter() if model_id == 'baseline' else nullcontext():
            self.model.eval()
            self.synchronize()
            load_ms = (time.perf_counter() - start) * 1000
            self.reset_peak()
            with Image.open(image_path) as image:
                result = generate_answer(self.model, self.processor, image.convert('RGB'), question, self.system_prompt,
                                         max_new_tokens=self.cfg['max_new_tokens'], do_sample=False, num_beams=1,
                                         stopping_criteria=StoppingCriteriaList([Stop()]), use_cache=self.cfg['use_cache'])
        if cancel.is_set():
            raise InterruptedError('Inference was cancelled.')
        if time.monotonic() > deadline:
            raise TimeoutError('Inference exceeded the time limit.')
        if not result['answer']:
            raise RuntimeError('The model generated an empty answer.')
        allocated, reserved = self.peak_memory()
        return dict(answer=result['answer'], generation_ms=result['latency_seconds'] * 1000, load_ms=load_ms,
                    model_total_ms=(time.perf_counter() - start) * 1000,
                    peak_allocated_bytes=allocated, peak_reserved_bytes=reserved, execution_device=self.device)

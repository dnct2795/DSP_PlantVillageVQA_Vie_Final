"""Chạy thử thật trên máy này (MPS/fp16): nạp model, sinh câu trả lời cho E0→E1→E2→E3 với một ảnh mẫu,
đo thời gian và bộ nhớ. Dừng server demo trước khi chạy (chỉ một model trong RAM).
Kết quả ghi vào logs/check_mps.json."""
import json
import resource
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from hoila.data import DemoData, settings  # noqa: E402
from hoila.inference import ModelService  # noqa: E402


def rss_gb():
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024 ** 3


def main():
    cfg, data = settings(), DemoData()
    t0 = time.perf_counter()
    service = ModelService(cfg)
    load_s = time.perf_counter() - t0
    print(f'model loaded in {load_s:.1f}s, device={service.device_name}, rss={rss_gb():.2f} GB', flush=True)
    event = threading.Event()
    rows = []
    row_ids = ['row_017244', 'row_016334', 'rw01_dataset']
    for row_id in row_ids:
        sample = data.samples[row_id]
        for model_id in cfg['models']:
            t = time.perf_counter()
            out = service.generate(model_id, data.image_path(sample['image_id']), sample['question'], event,
                                   time.monotonic() + cfg['model_timeout'])
            rows.append(dict(row_id=row_id, model_id=model_id, question=sample['question'],
                             reference=sample.get('reference'), expected=sample.get('expected_answer'),
                             answer=out['answer'], generation_s=out['generation_ms'] / 1000,
                             total_s=time.perf_counter() - t, mps_alloc_gb=(out['peak_allocated_bytes'] or 0) / 1024 ** 3,
                             rss_gb=rss_gb()))
            print(f"[{row_id}] {model_id:9s} {out['generation_ms']/1000:6.1f}s  {out['answer'][:90]!r}", flush=True)
    result = dict(timestamp=datetime.now(timezone.utc).isoformat(), device=service.device_name, dtype=cfg['dtype'],
                  load_seconds=load_s, memory=service.memory_info(), max_rss_gb=rss_gb(), rows=rows)
    Path('logs/check_mps.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print('saved logs/check_mps.json', flush=True)


if __name__ == '__main__':
    main()

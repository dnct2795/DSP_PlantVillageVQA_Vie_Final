"""Tải base model Qwen3-VL-2B-Instruct (snapshot ghim) vào cache HF, tự tiếp tục khi đứt mạng."""
import sys
import time

from huggingface_hub import snapshot_download

REPO = 'Qwen/Qwen3-VL-2B-Instruct'
REV = '89644892e4d85e24eaac8bacfd4f463576704203'
for attempt in range(1, 21):
    try:
        path = snapshot_download(REPO, revision=REV, max_workers=2)
        print('BASE_MODEL_PATH', path, flush=True)
        sys.exit(0)
    except Exception as exc:  # noqa: BLE001
        print(f'attempt {attempt} failed: {type(exc).__name__}: {exc}', flush=True)
        time.sleep(min(60, 5 * attempt))
sys.exit(1)

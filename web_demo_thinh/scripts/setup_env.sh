#!/usr/bin/env bash
# Tạo venv Python 3.11 cho demo trên Mac (MPS) và cài phụ thuộc.
# PEFT lấy từ wheel NoRA của Khoa (vendor/), không phải PEFT thường.
set -euo pipefail
cd "$(dirname "$0")/.."
KHOA="${KHOA_REPO:-../Final_report/Model_Khoa}"
uv venv --python 3.11 .venv
uv pip install --python .venv/bin/python \
  "torch>=2.5" "torchvision>=0.20" "transformers==4.57.6" "huggingface_hub==0.36.2" \
  "accelerate>=1.0" "pillow>=10.4" "pyyaml>=6.0" "numpy>=2.0" "safetensors" \
  "fastapi==0.162.0" "uvicorn==0.54.0" "httpx==0.28.1" "python-multipart" \
  "pytest>=8" "gdown"
uv pip install --python .venv/bin/python --no-deps "$KHOA/vendor/wheels/peft-0.19.2.dev0-py3-none-any.whl"
.venv/bin/python - <<'PY'
import torch, transformers, peft, inspect
from peft import LoraConfig
print('torch', torch.__version__, 'mps', torch.backends.mps.is_available())
print('transformers', transformers.__version__, 'peft', peft.__version__, 'use_nora' in inspect.signature(LoraConfig).parameters)
PY

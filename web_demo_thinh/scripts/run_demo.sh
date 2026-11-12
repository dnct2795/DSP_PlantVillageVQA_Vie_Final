#!/usr/bin/env bash
# Chạy demo "Hỏi Lá" ở 127.0.0.1:8000 (offline). PVVQA_DEMO_NO_GPU=1 = chỉ xem nội dung, không nạp model.
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH="${PWD}/backend${PYTHONPATH:+:${PYTHONPATH}}"
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export PYTORCH_ENABLE_MPS_FALLBACK="${PYTORCH_ENABLE_MPS_FALLBACK:-1}"
python_bin="${PVVQA_PYTHON:-.venv/bin/python}"
exec "$python_bin" -m uvicorn hoila.app:app --host 127.0.0.1 --port "${PVVQA_DEMO_PORT:-8000}" --workers 1

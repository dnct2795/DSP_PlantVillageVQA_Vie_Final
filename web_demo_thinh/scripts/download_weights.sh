#!/usr/bin/env bash
# Tải adapter E1/E2/E3 (Drive public của nhóm) và base model Qwen3-VL-2B (HF, snapshot ghim).
set -euo pipefail
cd "$(dirname "$0")/.."
DRIVE_FOLDER="${DRIVE_FOLDER:-18PWnyGWy1iUPlTODv9v2qXeMOaf4eZ4A}"   # pvvqa_results (5)/runs/kaggle_vi24195
mkdir -p output_perf_weight
.venv/bin/gdown --folder "https://drive.google.com/drive/folders/$DRIVE_FOLDER" -O output_perf_weight &
GD=$!
.venv/bin/python - <<'PY' &
from huggingface_hub import snapshot_download
p = snapshot_download('Qwen/Qwen3-VL-2B-Instruct', revision='89644892e4d85e24eaac8bacfd4f463576704203')
print('BASE_MODEL_PATH', p)
PY
HF=$!
wait $GD; echo "gdown exit $?"
wait $HF; echo "hf exit $?"
find output_perf_weight -maxdepth 3 -type d | sort

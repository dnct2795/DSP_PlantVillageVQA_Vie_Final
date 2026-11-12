# Hỏi Lá — web demo hỏi đáp bệnh lá cây bằng tiếng Việt

Demo chạy **trực tiếp trên MacBook (Apple Silicon, MPS)**: Qwen3-VL-2B-Instruct + adapter LoRA (E1),
NoRA-init (E2), NoRA (E3) và mô hình nền không adapter (E0), huấn luyện trên PlantVillageVQA-Vie.
Toàn bộ giao diện tiếng Việt, phong cách "Ruộng xanh" (xem `docs/WEB_DEMO_HANDOFF.md` mục 4).

**Dựa trên web demo của Khoa** (`PlantVillage-VQA/web-demo`, backend `src/pvvqa/web`): giữ nguyên hàng đợi
một tiến trình worker, các kiểm tra xuất xứ (hash nguồn PEFT NoRA, chế độ `use_nora`, SHA-256 adapter,
processor giống nhau) và dữ liệu mẫu; khác ở thiết bị (MPS/fp16), chức năng tải ảnh lên, và giao diện.

## Cấu trúc

```
backend/hoila/      FastAPI + worker model (app, data, jobs, worker, inference, uploads, generate, nora, normalize)
frontend/           React + Vite + TypeScript; 4 trang: hoi-dap, bo-du-lieu, phuong-phap, ket-qua
configs/web_demo.yaml   device: mps, dtype: float16, registry 4 mô hình, giới hạn upload
generated/          samples.json, assets.json, results.json (bản chụp từ CSV báo cáo của repo mô hình)
samples/            ảnh PlantVillage (9) + ảnh ngoài vườn (5, CC) + manifest
content/            run_context.json (hash adapter, prompt hệ thống), CSV báo cáo, comparison.csv
vendor/wheels/      peft-0.19.2.dev0 (bản NoRA, build từ Joluck/NoRA 4669c35)
scripts/            setup_env.sh, download_weights.sh, download_base_model.py, run_demo.sh, check_mps.py
tests/              pytest backend (chế độ không model)
output_perf_weight/ adapter + processor E1/E2/E3 (tải về, không commit)
```

## Cài đặt (một lần)

Yêu cầu: macOS trên chip Apple, `uv`, Homebrew Node ≥ 20.19 (dùng `brew install node@22`), ~5 GB trống.

```bash
cd web_demo_thinh
bash scripts/setup_env.sh                      # venv Python 3.11: torch (MPS), transformers 4.57.6, PEFT NoRA
bash scripts/download_weights.sh               # adapter E1/E2/E3 từ Drive nhóm + base model từ Hugging Face
export PATH=/opt/homebrew/opt/node@22/bin:$PATH
npm --prefix frontend ci --cache /tmp/hoila-npm-cache
npm --prefix frontend run build
```

Kiểm tra model chạy được trên máy (nạp model, 3 câu hỏi × 4 mô hình, ghi `logs/check_mps.json`):

```bash
PYTHONPATH=backend HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 .venv/bin/python scripts/check_mps.py
```

## Chạy demo

```bash
bash scripts/run_demo.sh          # http://127.0.0.1:8000 ; Ctrl+C để dừng
PVVQA_DEMO_NO_GPU=1 bash scripts/run_demo.sh   # chỉ xem nội dung, không nạp model, không cho tải ảnh
```

Lần đầu nạp model khoảng 1 phút (đọc 4 GB từ SSD); các lần sau khoảng 30–40 giây. Nên đóng bớt ứng dụng
nặng (Chrome nhiều tab, Zalo, Discord…) khi chạy: model chiếm ~4 GB bộ nhớ MPS.

Số đo trên MacBook Pro M1 16 GB (fp16, `logs/check_mps.json`): câu Có/Không 0,8–0,9 giây mỗi mô hình; câu
trả lời dài 2–7 giây; E0 chậm hơn vì trả lời dài. Câu trả lời của E1/E2/E3 trên ảnh mẫu khớp với
`predictions.normal.jsonl` của báo cáo; E0 (fp16) có thể khác bản bf16.

## API

Giống bản của Khoa (`/api/runtime`, `/api/samples`, `/api/assets/{id}`, `/api/results`, `POST /api/inferences`,
`GET/DELETE /api/inferences/{job_id}`), thêm:

- `POST /api/uploads` (multipart `file`, JPEG/PNG ≤ 10 MB) → `{image_id: "upload_…", width, height}`.
  Ảnh được kiểm tra nội dung, xoay theo EXIF, thu về cạnh dài 1024 px, lưu trong thư mục tạm và **xoá ngay
  khi lượt hỏi dùng nó kết thúc** (hoặc sau 10 phút, hoặc khi tắt server). Không ghi log nội dung ảnh.
  Dùng `image_id` này với `POST /api/inferences` (`question_id: null`, kèm `question`). Ảnh tải lên không có
  đáp án nên không có điểm khớp.
- Client không thể chọn đường dẫn file trên máy hay đổi tham số sinh (giữ nguyên nguyên tắc bản Khoa).

## Kiểm thử

```bash
.venv/bin/python -m pytest -q tests                 # backend, chế độ không model
# với server thật đang chạy ở :8000 và Google Chrome đã cài:
npm --prefix frontend run test:e2e                  # DEMO_NO_GPU=1 để bỏ qua test cần model
```

## Sự thật về số liệu

Mọi con số trên web lấy từ `generated/results.json` (xuất từ CSV báo cáo, cùng số với
`content/comparison_2026-10-31_01.csv`) và `PROGRESS.md` của repo dữ liệu; không có số nào tự bịa.
Bản dịch chỉ được kiểm định tự động ("silver-standard"), không có người kiểm định. Demo chạy fp16 trên MPS,
khác bf16 trên GPU khi đo báo cáo: câu trả lời và thời gian trên web chỉ là quan sát demo.

## Chạy trên máy có GPU NVIDIA (ví dụ máy của Khoa)

Không cần sửa mã. Khác với Mac ở ba chỗ:

1. **Môi trường Python**: dùng venv CUDA sẵn có của repo mô hình (`PVVQA_PYTHON=/đường/dẫn/.venv/bin/python`),
   cài thêm `fastapi==0.162.0 uvicorn==0.54.0 python-multipart pyyaml pillow`. Không chạy `setup_env.sh`
   (script đó cài torch bản mặc định cho Mac). PEFT phải là bản NoRA (`vendor/wheels/peft-0.19.2.dev0-py3-none-any.whl`).
2. **Config**: `PVVQA_WEB_CONFIG=configs/web_demo_cuda.yaml` (device `cuda:0`, dtype `bfloat16`).
3. **Trọng số**: copy hoặc symlink 3 thư mục `E1_lora_r16_a16`, `E2_nora_init_r16_a16`, `E3_nora_r16_a16`
   (mỗi thư mục có `adapter/` và `processor/`) vào `output_perf_weight/`; base model đã có trong cache HF thì
   không cần tải lại (hoặc `PVVQA_DEMO_BASE=/đường/dẫn/model`).

```bash
npm --prefix frontend ci && npm --prefix frontend run build
PVVQA_PYTHON=/path/to/.venv/bin/python PVVQA_WEB_CONFIG=configs/web_demo_cuda.yaml bash scripts/run_demo.sh
```

Trên Windows chạy script bằng Git Bash hoặc WSL (script chỉ đặt vài biến môi trường rồi gọi `uvicorn hoila.app:app`).

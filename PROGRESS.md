# PROGRESS — nhật ký tiến trình

Ghi mục mới ở đầu file. Mỗi mục gồm: đã làm, số liệu, vấn đề, việc tiếp theo.

## 2026-10-27 17:50 — Step 2: code chuẩn bị + runner dịch (chưa gọi model)

**Đã làm**
- `config/glossary.yaml`: glossary cố định (15 cây, 20 bệnh/sinh vật hại, 24 thuật ngữ triệu chứng,
  19 từ giữ nguyên: tên khoa học, HLB, TYLCV, ToMV...). Do Claude soạn từ toàn bộ tên trong subset.
  Ghi chú: nguồn có lỗi chính tả "Haunglongbing" (= Huanglongbing).
- `src/pvvqa/step2_prepare.py` → `outputs/step2/`: pairs.parquet, pair_qa_map.parquet,
  questions.csv, batches.jsonl, prepare_report.json.
- `prompts/translator.md`, `schemas/translation.json`.
- `src/pvvqa/step2_rules.py`: luật (đủ khoá, Yes/No = Có/Không, dạng "… có … không?", cấm câu
  hỏi đuôi, glossary cây/bệnh, từ tiếng Anh sót lại trừ danh sách giữ nguyên).
- `src/pvvqa/step2_translate.py`: gọi `claude -p` (cwd thư mục tạm để KHÔNG nạp CLAUDE.md),
  ghi append-only `runs/step2/translations.jsonl` sau mỗi batch, idempotent, dừng sạch khi hết
  quota, dừng sau 3 lỗi liên tiếp, `--pilot N`, `--status`, `--dry-run`.
  Đơn vị ghi = cả câu hỏi (mọi cặp cùng một question_vi); câu hỏi trả thiếu cặp → thử lại cả câu.
- Tests: `tests/test_step2.py` + `tests/fake_claude.py` (claude giả). `pytest -q`: 12 passed.

**Số liệu**
- 24.201 dòng → 7.522 cặp (968 Yes/No, 6.554 mở), 1.088 câu hỏi, tối đa 33 cặp/câu hỏi,
  240 batch (≤ 40 cặp, không tách câu hỏi).
- Pilot `--pilot 50`: 53 cặp, đủ 9 question_type, 2 lần gọi.

**Quyết định nhỏ (ghi lại để minh bạch)**
- `answer_label` = câu trả lời gốc tiếng Anh, sao chép nguyên văn (cho mọi loại câu hỏi).
- Thứ tự gọi lệnh: `claude -p --output-format json --max-turns 1 --tools "" --system-prompt-file
  runs/step2/system_prompt.md --json-schema <schema>`; cấu hình ở `config/phase1.yaml` → step2.

**Chọn model (17:45, đề xuất cho người dùng)**
- Dịch + repair: Claude Sonnet 5.5 (`--model sonnet` trong config) — cân bằng chất lượng/quota Pro.
- Chấm: Codex (khác hãng với người dịch), model mặc định, reasoning effort `medium` thay vì `high`;
  xác nhận bằng smoke test Step 3, bắt sót lỗi hiển nhiên thì nâng lại `high`.

**Tiếp theo**
- Người dùng đăng nhập Claude Code trên Mac (`claude` → `/login`, chọn gói Pro).
- Chạy pilot trên Terminal Mac: `PYTHONPATH=src python3 -m pvvqa.step2_translate --pilot 50`,
  đo thời gian/token, báo người dùng, rồi mới dịch toàn bộ.

## 2026-10-27 17:35 — Sửa repo local, kiểm tra môi trường trước Step 2

**Đã làm**
- Repo local trên Mac chưa có commit: lệnh `git fetch <bundle> main:main` ở CLAUDE.md mục 7 bị git
  từ chối (fetch vào nhánh hiện tại). Sửa bằng
  `git fetch --update-head-ok <bundle> refs/heads/main:refs/heads/main && git reset`.
  Đã khôi phục 3 commit `8671cac`, `44b369a`, `eea0215`; remote `origin` đúng.
- Shell của phiên (máy ảo Linux trên Mac) đã chạy được sau ~20 phút tải.

**Kết quả kiểm tra môi trường (máy ảo của phiên)**
- Python 3.10.12, cài được pandas/pyarrow/pyyaml/pytest; `pytest -q`: 3 passed.
- `outputs/step1/subset_en.parquet` có sẵn (đầu vào Step 2).
- `claude -p` trong máy ảo: "claude is not enabled in this environment" → KHÔNG dùng được.
- `codex`: không có trong máy ảo.
- Máy ảo không có thông tin đăng nhập GitHub → push phải làm từ Terminal của Mac.
- Git trong thư mục kết nối để lại file .lock (phiên không có quyền xoá) → cần cấp quyền xoá
  cho thư mục dự án thì phiên mới commit được.

**Kiểm tra trên Terminal Mac (17:36)**
- `claude`: CHƯA CÀI (zsh: command not found) → cần cài Claude Code và đăng nhập bằng tài khoản Pro.
- `codex-cli 0.159.2`, "Logged in using ChatGPT", `codex exec` trả "pong" (model gpt-5.6-sol,
  reasoning high, ~8.000 token cho một ping). Có lỗi MCP server `localhost:8000` không chạy
  (cấu hình trong ~/.codex) — vô hại nhưng làm chậm; sẽ tắt MCP khi gọi judge.
- Python 3.10.11 trên Mac, pandas/pyarrow/yaml có sẵn.

**Vấn đề / quyết định cần**
- Lời gọi model ở Step 2/3 (`claude -p`, `codex exec`) phải chạy trên Terminal của Mac
  (nơi đã đăng nhập Claude Pro / ChatGPT Plus), không chạy trong máy ảo của phiên.

**Tiếp theo**
- Đã push lên GitHub (main = eea0215). Người dùng: kiểm tra `claude -p` / `codex exec` trên Terminal Mac.
- Phiên: viết code Step 2 (gom cặp, glossary, prompt/schema, kiểm tra luật, checkpoint) + test.

## 2026-10-27 — Step 1 xong

**Đã làm**
- Thiết kế chốt: pipeline 3 bước (doc claude.ai, tab "Pipeline chính thức (3 bước)").
- Viết `step1_inspect.py`, `step1_sample.py` và test. Chạy trên cloud với revision HF
  `a025a438308eff9a7289231ebc09e27e8ec6678c`.
- Commit `8671cac`, `44b369a`, rồi commit CLAUDE.md + PROGRESS.md.

**Số liệu**
- Nguồn: 193.609 QA, train/test (không có val), 50.073 ảnh có QA trên 55.448 ảnh trong zip.
- Subset: 24.201 dòng, 18 tầng, 7.522 cặp duy nhất, 1.088 câu hỏi duy nhất. Mọi check PASS.

**Vấn đề**
- Chưa push được lên GitHub: repo không nằm trong danh sách nguồn của phiên cloud.
- Shell trên Mac không khởi động được ("Workspace unavailable"), nên Step 2/3 chưa chạy
  được `claude -p` / `codex exec` từ phiên.

**Tiếp theo**
- Push code (CLAUDE.md mục 7).
- Kiểm tra môi trường (CLAUDE.md mục 6), rồi chờ người dùng yêu cầu Step 2.

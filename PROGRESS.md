# PROGRESS — nhật ký tiến trình

Ghi mục mới ở đầu file. Mỗi mục gồm: đã làm, số liệu, vấn đề, việc tiếp theo.

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

# PROGRESS — nhật ký tiến trình

Ghi mục mới ở đầu file. Mỗi mục gồm: đã làm, số liệu, vấn đề, việc tiếp theo.

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

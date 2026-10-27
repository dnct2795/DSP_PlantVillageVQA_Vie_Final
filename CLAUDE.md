# CLAUDE.md — Hướng dẫn cho phiên làm việc tiếp theo

Dự án DSP391 (FPTU): xây subset VQA nông nghiệp tiếng Việt từ PlantVillageVQA.
File này là **plan pipeline chính thức + quy tắc khi chạy**. Đọc hết trước khi làm gì.

- Thiết kế gốc (nguồn sự thật): doc "Pipeline chính thức (3 bước)",
  https://claude.ai/artifact/AyFdKhWsCixoMn1SRFXTVU
- Ghi chú dự án trên claude.ai (project "DSP_VQA_Final"): `claude/critical_review_phase1.md`,
  `claude/step1_results.md`
- Repo: https://github.com/dnct2795/DSP391m_DSP391_PlantVillageVQA_v2
- Thư mục trên Mac: `/Users/mac/Documents/FPTU/FA26/DSP/DSP391_PlantVillageVQA_Final`

---

## 1. Trạng thái hiện tại (2026-10-27)

| Bước | Trạng thái |
|---|---|
| Step 1 — Representative Subset Selection | **XONG**, mọi acceptance check PASS |
| Step 2 — Context-aware EN–VI QA Translation | Chưa làm |
| Step 3 — Independent Evaluation & Selective Repair | Chưa làm |

Việc còn treo:
- Code mới có 2 commit (`8671cac`, `44b369a`), **chưa push lên GitHub**. Nếu repo trên GitHub còn
  trống: push từ `DSP391m_DSP391_PlantVillageVQA_v2.bundle` (xem mục 7).
- Phiên trước không chạy được shell trên Mac ("Workspace unavailable"). Kiểm tra lại ngay đầu phiên.

Kết quả Step 1 (chi tiết: `outputs/step1/*.md`):
- HF `SyedNazmusSakib/PlantVillageVQA`, revision **`a025a438308eff9a7289231ebc09e27e8ec6678c`**.
  Repo chỉ có `PlantVillageVQA.zip` (870 MB). QA lấy từ `PlantVillageVQA/PlantVillageVQA.csv`
  (giống hệt bản JSON). Chỉ đọc CSV/JSON qua HTTP range, không tải ảnh.
- 193.609 dòng QA; split thực tế **chỉ có train/test** (154.977 / 38.632); 9 `question_type` → 18 tầng.
- 55.448 ảnh trong zip, 50.073 ảnh có QA. `image_path` ghi `images/<split>/<file>` nhưng zip để
  phẳng `PlantVillageVQA/Images/<file>` → giữ nguyên giá trị gốc, đối chiếu theo tên file (khớp 100%).
- Nguồn không có id cho QA → `qa_id = pvqa_<chỉ số dòng CSV>` (ổn định khi đã ghim revision).
- Subset 12,5%, seed 42: **24.201 dòng**, 18.751 ảnh, **7.522 cặp QA duy nhất**, 1.088 câu hỏi duy nhất;
  Yes/No: 10.178 dòng / 968 cặp. Cặp phổ biến nhất ứng với 143 dòng.
  `qa_id` sha256 của subset: `d322d907ec88015af41f477af40512fbadb156e4dad58ed76b48d00e69ab091f`.

---

## 2. Ràng buộc (không được vi phạm)

- Tự động hoàn toàn, **không có người trong pipeline**.
- **Không phát sinh phí API.** Chỉ dùng Claude Pro (Claude Code `claude -p`) và ChatGPT Plus
  (Codex CLI `codex exec`). Không dùng API key trả phí, không gọi API trực tiếp.
- Máy: MacBook M1 16 GB. Phase 1 chỉ xây dataset: **không training, không fine-tuning, không benchmark**.
- Bảo toàn `split`, `question_type`, `image_path` và mapping QA gốc từ đầu đến cuối.
- **Đơn giản trước.** Không thêm stage, model đánh giá hay thuật toán chỉ để xử lý tình huống hiếm.
  Không bắt buộc pilot lớn, ngưỡng Wilson, LaBSE, COMETKiwi. Không mở vòng phản biện mới trừ khi
  thấy lỗi nghiêm trọng.
- **Chỉ chạy từng bước khi người dùng yêu cầu.** Xong mỗi bước: báo cáo rồi dừng.

---

## 3. Pipeline 3 bước

### Step 1 — Representative Subset Selection (đã xong)
```bash
export PYTHONPATH=src
python -m pvvqa.step1_inspect   # 1.1 revision, schema, split, ảnh
python -m pvvqa.step1_sample    # 1.2 lấy mẫu + 1.3 nghiệm thu
pytest -q
```
Proportional stratified random sampling theo `split × question_type`, 12,5%, seed 42,
largest remainder, ≥1 dòng mỗi tầng không rỗng, đơn vị là dòng QA, không thay mẫu.
Đầu ra: `outputs/step1/subset_en.parquet` (đầu vào của Step 2).

### Step 2 — Context-aware EN–VI QA Translation (dịch: Claude)
1. **Gom cặp:** `pair_id` = hash của `(question_type, question_en, answer_en)`. Lưu
   `pair_id → [qa_id…]` và tần suất (số dòng). Mỗi cặp dịch một lần, áp cho mọi dòng.
2. **Glossary:** tên cây, bệnh, thuật ngữ; tạo một lần, cố định trước khi dịch. Tên khoa học giữ nguyên.
   Viết tắt tiếng Anh (HLB, TYLCV, ToMV) **luôn dịch thành tên tiếng Việt đầy đủ**, không giữ kể cả trong ngoặc.
3. **Batch theo câu hỏi:** các cặp chung `(question_type, question_en)` vào cùng batch và **dùng
   chung đúng một `question_vi`**. Lưu bảng câu hỏi `(question_type, question_en) → question_vi`.
   Dịch câu hỏi và câu trả lời cùng lúc.
4. **Quy tắc Yes/No:** giữ nguyên mệnh đề P và cực tính ("free of disease" → "sạch bệnh");
   câu hỏi dạng "… có … không?" hoặc "… có phải … không?", không dùng câu phủ định hay câu hỏi đuôi;
   `answer_vi` ∈ {"Có", "Không"}; `answer_label` **sao chép từ nguồn**, không qua dịch.
   Câu hỏi mở: dịch câu trả lời thành văn bản như gốc.
5. **Kiểm tra bằng luật (không dùng model):** JSON hợp lệ, đủ trường; Yes/No khớp `answer_label`
   và đúng dạng câu hỏi; tên cây/bệnh khớp glossary; không còn tiếng Anh chưa dịch, trừ tên khoa học,
   tên riêng và thuật ngữ glossary cho giữ nguyên; cùng câu hỏi EN → cùng `question_vi`.
   Cặp không qua luật → chuyển thẳng sang repair ở Step 3.

Gọi Claude (dùng gói Pro, **không** `--bare`):
```bash
claude -p --max-turns 1 --tools "" --system-prompt-file prompts/translator.md \
  --output-format json --json-schema schemas/translation.json < batch.json
```

### Step 3 — Independent Evaluation & Selective Repair (chấm: Codex, sửa: Claude)
1. **Smoke test bắt buộc** trước khi chấm toàn bộ: khoảng 10 cặp cố ý sai cho mỗi loại
   (đảo mệnh đề/cực tính, đổi cây, đổi bệnh, mất điều kiện giả định "nếu") + khoảng 10 cặp đúng làm
   đối chứng. Báo cáo "Codex bắt được x/10". Bỏ sót lỗi hiển nhiên → sửa prompt judge rồi chạy lại.
   **Không** gọi đây là hiệu chuẩn.
2. **Chấm toàn bộ:** Codex chấm từng cặp EN↔VI, có `question_type` và glossary. Lỗi kiểu MQM
   (sai nghĩa, đảo cực tính, thiếu, thừa, thuật ngữ, độ trôi chảy) × (minor, major, critical).
   PASS = qua luật và không có major/critical; còn lại NEEDS_REPAIR.
3. **Repair đúng một lần:** Claude dịch lại kèm nhận xét của judge → chấm lại.
   Đạt → `PASS_AFTER_REPAIR`; không đạt → `UNRESOLVED`, không sửa thêm.
   Nếu sửa làm đổi `question_vi` dùng chung: cập nhật bảng câu hỏi, áp cho mọi cặp cùng câu hỏi,
   **chấm lại** (không dịch lại) các cặp đó; cặp nào không đạt → `UNRESOLVED`.
4. `UNRESOLVED` được giữ lại với trạng thái rõ ràng, **không xoá âm thầm, không thay mẫu**.
5. **Chuẩn hoá thuật ngữ (3.4):** thay viết tắt HLB/TYLCV/ToMV còn sót bằng tên tiếng Việt đầy đủ theo
   luật cố định (`pvvqa.step3_expand`), kiểm tra luật và Codex chấm lại các cặp bị đổi; không đạt → `UNRESOLVED`.

Gọi Codex:
```bash
codex exec --sandbox read-only --skip-git-repo-check --ephemeral \
  --output-schema schemas/judge.json "$(cat prompts/judge.md batch.json)"
```

### Đầu ra cuối và quality report
- **Dataset tiếng Việt:** `qa_id, image_path, split, question_type, question_vi, answer_vi,
  answer_label, pair_id, status`.
- **Bản đối chiếu EN–VI:** thêm `question_en, answer_en`, kết quả judge, log repair.
- Chỉ `PASS` + `PASS_AFTER_REPAIR` là *automatically validated silver-standard* và dùng cho training.
  `UNRESOLVED` chỉ để truy vết.
- **Quality report** gồm:
  1. Nguồn: revision, schema, split thực tế.
  2. Phân phối `split × question_type` của 3 tập: gốc, subset EN, VI cuối; số dòng mất ở từng tầng.
  3. PASS lần đầu / PASS_AFTER_REPAIR / UNRESOLVED, tính **cả theo cặp lẫn theo dòng**.
  4. Số câu hỏi EN có nhiều hơn một `question_vi` (mục tiêu 0).
  5. Smoke test x/10.
  6. Giới hạn: Codex là lớp ngữ nghĩa duy nhất, chưa hiệu chuẩn với người; dữ liệu gốc sinh từ template.

---

## 4. Quy tắc khi chạy

### 4.1 Lưu tiến trình
- **`PROGRESS.md`** ở gốc repo là nhật ký chính. Cập nhật **trước khi kết thúc mỗi phiên** và sau
  mỗi mốc: đã làm gì, lệnh đã chạy, số liệu chính, lỗi gặp phải, việc tiếp theo.
  Phiên mới đọc `CLAUDE.md` rồi đến `PROGRESS.md` trước tiên.
- **`runs/<step>/run_log.jsonl`:** mỗi lần chạy ghi một dòng gồm thời điểm, lệnh, git commit,
  config hash, số mục đã xong / tổng, số lỗi, lý do dừng.
- Sau mỗi bước hoặc mốc quan trọng: cập nhật `claude/step*_results.md` trong project claude.ai.

### 4.2 Checkpoint và chạy tiếp
- Mọi kết quả từ model (bản dịch, kết quả chấm, bản sửa) được ghi **append-only** vào
  `runs/<step>/*.jsonl`, mỗi dòng có `pair_id`. **Ghi ngay sau mỗi batch**, không gom lại cuối.
- Chạy lại phải **idempotent**: bỏ qua `pair_id` đã có kết quả hợp lệ, không gọi model lại.
- Dòng hỏng (JSON lỗi, thiếu trường) không xoá: ghi kèm `error`, lần chạy sau thử lại cặp đó.
- **Hết quota hoặc bị rate limit:** dừng sạch (ghi checkpoint, ghi lý do vào `run_log.jsonl`),
  in lệnh để chạy tiếp. Không lặp gọi liên tục.
- Batch nhỏ (ví dụ 20–50 cặp, hoặc tất cả cặp của một câu hỏi) để mất ít khi bị ngắt.

### 4.3 Không ghi đè, không phá dữ liệu
- `data/raw/` chỉ đọc. `outputs/step1/` coi như đã đóng băng: muốn chạy lại thì ghi sang thư mục
  mới và so `qa_id` sha256.
- Không xoá file kết quả. Muốn làm lại thì tạo `runs/<step>/<YYYYMMDD-HHMM>/` mới.
- Giữ ghim revision HF và seed 42 trong `config/phase1.yaml`. Không đổi tham số lấy mẫu.

### 4.4 Quota và chi phí
- Trước khi gọi model: `unset ANTHROPIC_API_KEY OPENAI_API_KEY` và kiểm tra
  `claude -p "ping"` / `codex exec "ping"` chạy bằng tài khoản đăng nhập, không phải API key.
- Ước lượng trước khi chạy: Step 2 khoảng 7.522 cặp trong khoảng 1.088 nhóm câu hỏi.
  Chạy thử khoảng 50 cặp, đo tốc độ và mức dùng quota, báo người dùng rồi mới chạy toàn bộ.

### 4.5 Kiểm tra và git
- Mỗi module mới có test trên dữ liệu giả trong `tests/`. `pytest -q` phải xanh trước khi commit.
- Commit sau mỗi mốc với message rõ ràng. Không commit `data/`, không commit secret.
- Kết quả nhỏ (report, manifest, bảng câu hỏi, glossary) được commit. File lớn ghi đường dẫn
  trong `PROGRESS.md`.

### 4.6 Báo cáo trung thực
- Báo số liệu thật, kể cả khi xấu. Không gọi kết quả là "đã kiểm định bởi người" hay "đã hiệu chuẩn".
- Ghi rõ phần nào lấy từ paper, phần nào lấy ý tưởng, phần nào nhóm tự quyết định
  (xem bảng trong doc thiết kế).

---

## 5. Cấu trúc repo

```
config/phase1.yaml          # revision ghim, seed, tỷ lệ
src/pvvqa/                  # common.py, step1_inspect.py, step1_sample.py, (step2_*, step3_*)
prompts/  schemas/          # tạo ở Step 2/3
tests/                      # pytest trên dữ liệu giả
outputs/step1/              # reports + subset_en.parquet (đã đóng băng)
runs/step2/  runs/step3/    # checkpoint jsonl + run_log.jsonl
data/raw/                   # metadata tải về (git-ignored)
PROGRESS.md                 # nhật ký tiến trình
```

---

## 6. Việc đầu tiên của phiên mới

1. Đọc `CLAUDE.md` và `PROGRESS.md`.
2. Kiểm tra môi trường:
   - shell trên Mac chạy được không;
   - `git status` và remote;
   - `python3 --version`, `pip install -r requirements.txt`;
   - `pytest -q`;
   - `claude -p "ping"`, `codex exec "ping"` (không API key).
3. Nếu GitHub chưa có code thì push (mục 7).
4. Báo người dùng trạng thái, **chờ yêu cầu** rồi mới bắt đầu Step 2. Thứ tự đề xuất:
   gom cặp + glossary → chạy thử khoảng 50 cặp → đo quota → dịch toàn bộ.

## 7. Đưa code lên GitHub (nếu chưa)

```bash
cd /Users/mac/Documents/FPTU/FA26/DSP/DSP391_PlantVillageVQA_Final
git init -b main
git fetch DSP391m_DSP391_PlantVillageVQA_v2.bundle main:main
git reset main                 # working tree đã có file, chỉ đồng bộ index
git remote add origin https://github.com/dnct2795/DSP391m_DSP391_PlantVillageVQA_v2.git
git push -u origin main
```
Nếu phiên chạy trên cloud: repo phải được chọn làm nguồn của phiên lúc tạo task, nếu không proxy
sẽ trả lỗi 403.

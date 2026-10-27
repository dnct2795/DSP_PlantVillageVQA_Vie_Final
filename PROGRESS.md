# PROGRESS — nhật ký tiến trình

Ghi mục mới ở đầu file. Mỗi mục gồm: đã làm, số liệu, vấn đề, việc tiếp theo.

## 2026-10-27 22:55 — Step 3 XONG: chấm toàn bộ + repair

**Lệnh**: `python -m pvvqa.step3_judge` (run 20261027-215657 + 1 lần chấm bù 1 cặp `missing_item`),
`python -m pvvqa.step3_repair` (run 20261027-225232).

**Chấm lần đầu** (gpt-6-luna, high): 7.508/7.508 cặp đã qua luật được chấm; 7.493 PASS,
15 NEEDS_REPAIR (13 mistranslation major, 1 terminology major, 1 addition major). 329 cặp có ít nhất
một lỗi (chủ yếu fluency minor 267, terminology minor 36). 55 phút model, 2,98M token vào, 0,23M ra.

**Repair** (Claude Sonnet, 1 lần gọi) 29 cặp = 14 trượt luật + 15 NEEDS_REPAIR; chấm lại 29 cặp:
29/29 PASS → **PASS_AFTER_REPAIR**. 5 câu hỏi đổi question_vi (không có cặp anh em nào khác).
Kết quả cuối: **PASS 7.493 cặp / 23.979 dòng; PASS_AFTER_REPAIR 29 cặp / 222 dòng; UNRESOLVED 0**.
Câu hỏi EN có > 1 question_vi: 0.

**Cần ghi vào báo cáo (trung thực)**
- 5/29 cặp "sửa" không đổi chữ nào nhưng lần chấm lại cho PASS: đều thuộc 3 câu hỏi nguồn dạng
  "What …?" mà câu trả lời là Yes/No (lỗi template của nguồn: 434 dòng / 3 câu hỏi trong toàn bộ nguồn).
  Bản dịch "… có … nào không?" là hợp lý vì đáp án là Có/Không; judge chấm lần đầu NEEDS_REPAIR,
  lần sau PASS → judge không ổn định ở ca ranh giới.
- Một số bản sửa còn hơi gượng: "… có hoàn toàn không có không?", "bão hòa màu".

**Tiếp theo**: xuất dataset tiếng Việt + bản đối chiếu EN–VI + quality report; đưa lên Kaggle.
Tuỳ chọn: kiểm tra chéo ~120 cặp bằng gpt-6.1-sol high.

## 2026-10-27 21:55 — Step 3: judge + smoke test + pilot chấm 81 cặp

**Đã làm**
- `prompts/judge.md`, `schemas/judge.json` (lỗi MQM: mistranslation, polarity, omission, addition,
  terminology, fluency × minor/major/critical; PASS = không có major/critical).
- `src/pvvqa/step3_judge.py`: `--smoke`, `--pilot N`, chấm toàn bộ, `--status`; chỉ chấm cặp đã qua
  luật; checkpoint append-only `runs/step3/judgments.jsonl`, idempotent, dừng sạch khi hết quota.
- Codex gọi với `--ignore-user-config`, prompt judge làm `model_instructions_file`, tắt công cụ:
  phần cố định mỗi lần gọi ~19k → ~7,6k token.
- Tests: `tests/test_step3.py` + `tests/fake_codex.py`; `pytest -q`: 24 passed.

**Smoke test** (gpt-6-luna, high; 50 mục sinh tự động, seed 42; KHÔNG phải hiệu chuẩn)
- Đảo cực tính 10/10, đổi cây 10/10, đổi bệnh 10/10, mất điều kiện "nếu" 10/10; đối chứng báo nhầm 0/10.
- Loại lỗi gán đúng: crop/disease → mistranslation critical; polarity → polarity critical (7/10);
  conditional → omission major (10/10). Báo cáo: `outputs/step3/smoke_report__gpt-6-luna__high.md`.
- 2 lần gọi, 36 s, 23k token vào.

**Pilot chấm 81 cặp thật**: 81 PASS, 0 NEEDS_REPAIR; 5 lỗi fluency minor (lặp "vàng lá gân xanh",
"đốm lốm đốm"). 43 s, 36k token vào, 3k token ra.
→ Ước lượng chấm toàn bộ 7.508 cặp: ~190 lần gọi, ~65 phút, ~3,4M token vào, ~0,3M token ra.

**Tiếp theo**: chờ người dùng cho chấm toàn bộ; viết repair (Claude) + chấm lại.

## 2026-10-27 21:45 — Step 2 XONG: dịch toàn bộ 7.522 cặp

**Lệnh**: `PYTHONPATH=src python3 -m pvvqa.step2_translate` (3 lần chạy: 20261027-180111 dừng do hết
phiên Pro; 20261027-211144 dừng do 3 lần "claude exited 1" liên tiếp; 20261027-212100 hoàn tất),
rồi `--recheck` sau khi thêm Solanum tuberosum, Citrus sinensis vào `keep` của glossary.

**Số liệu**
- 7.522/7.522 cặp đã dịch, 0 lỗi chờ. Qua luật: **7.508 cặp (99,81%)**, **24.105/24.201 dòng (99,60%)**.
  Trượt luật: 14 cặp / 96 dòng → chuyển sang repair ở Step 3.
- Câu hỏi EN có > 1 `question_vi`: **0** / 1.088. Yes/No: `answer_vi` khớp `answer_label` 100%.
- Lỗi luật còn lại: tên TYLCV kèm tên tiếng Anh đầy đủ trong ngoặc; "Huanglongbing" không kèm
  "vàng lá gân xanh"; câu "stress … phải không?".
- Tổng (gồm pilot): 2,36M token vào, 0,56M token ra, 75 phút model.
- Nhận xét chất lượng thấy khi đọc mẫu: có câu lặp ý ("…(Huanglongbing, HLB), hay còn gọi là bệnh vàng
  lá gân xanh trên cây có múi") — luật không bắt, để judge Step 3 đánh giá.

**Sự cố & sửa**
- "claude exited 1" không kèm thông báo xảy ra ngẫu nhiên (cả với ping) → thêm thử lại 1 lần sau 30 s.
- "session limit" chưa được nhận là hết quota → đã thêm vào QUOTA_PAT.

**File**: `runs/step2/translations.jsonl` (không commit, ~3.0MB), `runs/step2/raw/`, `runs/step2/run_log.jsonl`.

**Tiếp theo**: Step 3 (prompt/schema judge, smoke test với gpt-6-luna high) — chờ người dùng yêu cầu.

## 2026-10-27 18:57 — Step 2: dịch toàn bộ (dừng giữa chừng do hết giới hạn phiên Pro)

- Run `20261027-180111`: 5.106/7.522 cặp đã dịch, 5.097 qua luật, 9 trượt luật, 239 cặp lỗi chờ
  dịch lại (b0020, b0030, b0060, b0166: "claude exited 1" không rõ lý do; b0172–b0174: hết phiên).
  72 batch còn lại. 1,63M token vào, 0,39M token ra, 54 phút model.
- Dừng: "You've hit your session limit · resets 9:10pm (Asia/Saigon)". Regex quota chưa bắt
  "session limit" → runner dừng sau 3 lỗi liên tiếp. Đã sửa QUOTA_PAT + test (16 passed).
- Tiếp theo: sau 21:10 chạy lại `PYTHONPATH=src python3 -m pvvqa.step2_translate`.

## 2026-10-27 18:20 — Chọn model judge cho Step 3

- Codex đã kết nối: `codex-cli 0.159.2`, đăng nhập bằng ChatGPT (không API key), `codex exec` ping → "pong"
  (~7.700 token/lần gọi kể cả ping: system prompt Codex + MCP).
- Mặc định trong `~/.codex/config.toml` là gpt-5.6-sol + high (thế hệ cũ, tốn) → không dùng.
- Người dùng chốt: judge = **gpt-6-luna, reasoning high**; dự phòng gpt-6.1-sol low nếu smoke test
  bỏ sót lỗi hiển nhiên. Ghim trong `config/phase1.yaml` → `step3`.
- Giảm chi phí: ~40 cặp/lần gọi, tắt MCP khi gọi judge.

## 2026-10-27 18:05 — Step 2: sửa luật sau pilot (chưa dịch toàn bộ)

**Đã làm**
- Glossary: thêm trường `abbr` (HLB, TYLCV, ToMV). Nếu câu EN chỉ nêu bằng viết tắt, câu VI giữ
  viết tắt cũng đạt; EN có tên đầy đủ thì VI vẫn phải có tên tiếng Việt. Thêm term `stress → căng thẳng`.
- Luật `yn_tag`: câu kết thúc bằng "phải không?" luôn là hỏi đuôi (có/không dấu phẩy);
  "đúng không?" là hỏi đuôi trừ khi là "… có đúng không?". (Bản đầu dùng lookbehind "có " nên bỏ
  sót đúng câu pilot "…không có phải không?" — đã sửa.)
- Prompt: cấm kết thúc bằng "phải không?/đúng không?"; ví dụ cách giữ mệnh đề phủ định ("absent")
  trong khung "có … không?".
- `step2_translate --recheck`: áp lại luật hiện tại lên bản dịch đã có, không gọi model, ghi thêm
  dòng mới (append-only, trường `recheck_of`), idempotent.
- Tests: thêm 3 test, `pytest -q`: 15 passed.

**Số liệu**
- `--recheck` trên 53 cặp pilot: 7 cặp đổi kết quả → 5 qua, 2 vẫn trượt (`untranslated:stress`,
  `yn_tag`) → 51/53 qua luật. Không có cặp nào khác bị luật mới báo sai.
- 2 cặp trượt theo thiết kế sẽ sang repair ở Step 3 (không dịch lại ở Step 2).

**Tiếp theo**
- Chờ người dùng cho phép dịch toàn bộ: `PYTHONPATH=src python3 -m pvvqa.step2_translate`.
- Push các commit lên GitHub.

## 2026-10-27 17:46 — Step 2: pilot 50 cặp (Claude Sonnet, gói Pro)

**Đã làm**
- `claude -p --model sonnet "Reply with exactly: pong"` → "pong" (không API key).
- `PYTHONPATH=src python3 -m pvvqa.step2_translate --pilot 50` (run `20261027-174543`, commit `b04000d`).

**Số liệu**
- 53 cặp, 2 lần gọi, 28,9 s thời gian model; 18.824 token vào, 4.089 token ra; 0 lỗi gọi.
- Qua luật 46/53, trượt 7/53.
- Ước lượng toàn bộ 7.522 cặp (×142): ~70 phút model, ~2,7M token vào, ~0,58M token ra.

**Phân tích 7 cặp trượt**
- 5 cặp là **luật báo nhầm**: câu gốc EN đã dùng viết tắt TYLCV/HLB, bản dịch giữ nguyên viết tắt
  (đúng), nhưng luật glossary đòi tên đầy đủ.
- 2 cặp lỗi thật ("Are both stress and disease indicators absent?"): còn từ "stress", và câu hỏi
  "… đều không có phải không?" là câu hỏi đuôi + phủ định. Luật `yn_tag` **không bắt** vì regex
  đòi dấu phẩy trước "phải không".

**Tiếp theo (chờ người dùng quyết)**
- Sửa luật: chấp nhận viết tắt khi EN dùng viết tắt; `yn_tag` bắt cả "phải không?" không có dấu phẩy.
  Thêm vào prompt: "stress" → "căng thẳng/stress sinh lý", tránh dạng "phải không?".
- Sau đó dịch toàn bộ.

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

# Bàn giao: Web demo "Hỏi Lá" (bản của Thịnh)

Ngày soạn: 2026-11-12. Soạn từ phiên Claude trên claude.ai (project "DSP_VQA_Final") để một phiên
Claude Code chạy **trực tiếp trên Mac** làm tiếp. Đọc hết file này trước khi làm gì.

Người dùng: Đặng Nguyễn Cường Thịnh (DSP391, Nhóm 1, AI1905). Trả lời người dùng bằng **tiếng Việt**.

---

## 1. Mục tiêu

Xây một web demo riêng của Thịnh, chức năng tương đương web demo của Khoa, gồm:

1. **Trang Hỏi đáp** (ưu tiên số 1): chọn ảnh mẫu hoặc **tải ảnh lên**, chọn câu hỏi gợi ý hoặc tự gõ,
   chạy **trực tiếp** Qwen3-VL-2B + adapter E1/E2/E3 (và E0 không adapter) **trên MacBook (MPS)**,
   hiện câu trả lời và so sánh các mô hình.
2. Các trang **Bộ dữ liệu**, **Phương pháp**, **Kết quả** (nội dung tương đương phần Overview /
   Methodology / Results của Khoa).
3. Sau đó: một bản **tĩnh có link chia sẻ** (không chạy model; phần hỏi đáp dùng câu trả lời đã lưu từ
   `predictions.*.jsonl`, ghi rõ là kết quả đã lưu). Bản này làm sau, có thể làm ở phiên claude.ai.

Yêu cầu giao diện đã chốt:
- **Toàn bộ giao diện tiếng Việt** (kể cả các trang nghiên cứu). Khác bản Khoa (tiếng Anh, kiểu bài báo).
- Phong cách: **chuyên nghiệp nhưng gần gũi nông dân**. Người dùng đã chọn **Hướng A · "Ruộng xanh"**
  (xem mục 4).
- Có chức năng **upload ảnh**, ngoài ảnh mẫu có sẵn.

Trước mắt làm bản "đầy đủ như của Khoa" theo giao diện mới, rồi người dùng sẽ chỉnh dần.

---

## 2. Máy và môi trường

- MacBook Pro **M1, 16 GB RAM, 256 GB SSD**. Kiểm tra dung lượng trống trước khi tải model
  (cần khoảng 8–10 GB cho PyTorch + model + adapter).
- Không có GPU NVIDIA → **không có CUDA**. Dùng `torch.device("mps")`.
- M1 không hỗ trợ bf16 tốt trên MPS → chạy **fp16** (nếu lỗi số học thì thử fp32 cho phần vision).
  Câu trả lời có thể lệch nhẹ so với benchmark (chạy bf16 trên RTX); giao diện phải ghi đây là demo,
  không phải số liệu báo cáo.
- Ứng dụng đang mở thường ngày: Chrome, Zalo, Discord, VS Code… nên nhắc người dùng đóng bớt khi chạy model.
- Phiên claude.ai trước đây **không** chạy được lệnh macOS thật (shell là máy ảo Linux), nên mọi thứ dưới
  đây **chưa được chạy thử trên Mac**. Cần tự kiểm chứng.

---

## 3. Mã nguồn để làm nền: web demo của Khoa

Repo model (private, cùng nhóm, người dùng đã đồng ý dùng lại):
`~/Documents/FPTU/FA26/DSP/DSP391_PlantVillageVQA_Final/Final_report/Model_Khoa/`
(github.com/DangKhoaAI/PlantVillage-VQA). Ngày 2026-11-11 đã fast-forward `main` tới `af47e08` (2026-11-05).
Chạy `git fetch` / `git pull --ff-only` lại để lấy bản mới nhất. **Không sửa trực tiếp repo của Khoa**
(trừ khi người dùng yêu cầu); copy sang chỗ làm của Thịnh.

Các phần liên quan trong repo Khoa:
| Đường dẫn | Nội dung |
|---|---|
| `web-demo/README.md` | Mô tả đầy đủ demo, API, quy tắc dữ liệu. **Đọc trước.** |
| `web-demo/frontend/` | React + Vite + TypeScript (+ Playwright tests). `src/live.tsx` = phần inference. |
| `web-demo/generated/*.json` | `results.json`, `samples.json`, `assets.json` sinh bởi `scripts/export_web_demo.py`. |
| `web-demo/content/translations.json` | Bản dịch tiếng Anh để hiển thị (bản Thịnh không cần). |
| `web-demo/samples/real-world/` | 5 ảnh ngoài thực tế + `manifest.json` (nguồn, tác giả, giấy phép CC) + 10 câu hỏi gợi ý. |
| `src/pvvqa/web/` | Backend FastAPI: `app.py`, `inference.py`, `worker.py`, `jobs.py`, `data.py`. |
| `configs/web_demo.yaml` | `device: cuda:0`, `dtype: bfloat16`, `attention: sdpa`, `max_new_tokens: 64`, registry 4 model. |
| `scripts/run_web_demo.sh` | Chạy uvicorn ở `127.0.0.1:8000`, offline. `PVVQA_DEMO_NO_GPU=1` = xem nội dung không cần model. |
| `vendor/` (`peft/`, `wheels/`, `manifest.json`) | **Bản PEFT tuỳ biến có NoRA**. PEFT thường không chạy được E2/E3. |
| `scripts/setup_offline.py`, `build_peft_wheel.py` | Bootstrap môi trường offline / build wheel PEFT. |

Các chỗ phụ thuộc CUDA cần sửa (đã tìm bằng grep, có thể còn nữa):
- `src/pvvqa/web/inference.py`: kiểm tra `torch.cuda.is_available()` (dòng ~25), bắt buộc mọi tham số ở
  `cuda` (~68), `get_device_name`, `cuda.synchronize`, `reset_peak_memory_stats`, `max_memory_allocated/reserved`.
- `src/pvvqa/web/worker.py`: `torch.cuda.mem_get_info()` (~13), bắt `torch.cuda.OutOfMemoryError` (~40).
- `configs/web_demo.yaml`: `device`, `dtype`.
- Loader kiểm tra **SHA-256 nguồn PEFT, chế độ `use_nora`, SHA-256 safetensors adapter, processor giống nhau**:
  giữ nguyên các kiểm tra này (chỉ đổi phần thiết bị).
- Thay số đo VRAM bằng thứ tương đương trên MPS (`torch.mps.current_allocated_memory()`,
  `torch.mps.synchronize()`) hoặc bỏ.

Model và adapter:
- Base: `Qwen/Qwen3-VL-2B-Instruct`, snapshot `89644892e4d85e24eaac8bacfd4f463576704203`
  (cần tải về cache HF; demo chạy offline).
- Adapter **không có trong git**. Cần 3 thư mục `output_perf_weight/E1_lora_r16_a16`, `E2_nora_init_r16_a16`,
  `E3_nora_r16_a16`, mỗi thư mục có `adapter/` và `processor/`. Nguồn: link Google Drive "Kho kết quả và model"
  trong `results/new/2026-10-30_01/README.md`. Người dùng phải tự tải (Drive cần đăng nhập) hoặc cho phép tải.
- Chỉ 1 model nền dùng chung 3 adapter (không merge), mỗi lúc 1 lượt sinh. Ước lượng RAM fp16 ~4,5 GB:
  vừa 16 GB. Tốc độ chưa đo; so sánh 4 model là chạy lần lượt.

---

## 4. Giao diện đã chọn: Hướng A · "Ruộng xanh"

Mockup (canvas Design trên claude.ai, riêng tư): https://claude.ai/artifact/EWi9Q72Ymx5F7j6U9eR3aE
(3 hướng A/B/C; người dùng chọn **A**). Mã nguồn artboard A lưu kèm file này:
`docs/web_demo_mockup/Main.dc.html` (định dạng `.dc.html` của canvas: `{{…}}`, `<x-dc>`, ảnh trỏ `/_blob/<id>`;
chỉ để tham khảo bố cục và CSS, không chạy trực tiếp được). Bảng ảnh `/_blob` → file thật ở mục 4.3.

### 4.1 Hệ màu, chữ
| Vai trò | Giá trị |
|---|---|
| Xanh lá đậm (header, hero, khối câu trả lời chính, chip đang chọn) | `#1E4A2C` (hover `#0F2A17`), ô thống kê `#2A5C38` |
| Nền trang | `#F4F6EF`; thẻ nội dung `#FFFFFF`, bo 20px, bóng nhẹ |
| Chữ chính / chữ phụ | `#17301F` / `#4F5F52`; chữ trên nền xanh `#FFFFFF`, phụ `#CFE0C8`, `#DDE9D6` |
| Vàng lúa chín (nút chính, số bước, điểm nhấn) | `#F2C14E` với chữ `#1E4A2C` |
| Viền | `#C9D5C1`, `#D9E0D2`, `#E1E7DA`; vùng upload viền đứt `#9DB394`, nền `#F8FAF4` |
| Hộp cảnh báo | nền `#FFF6DB`, viền `#EBCB75`, chữ `#5A3D0B`, icon `#8A5A12` |
| Font | **Be Vietnam Pro** 400–800 (Google Fonts), tiêu đề hero 44px/800 |

Icon: SVG nét (stroke), không dùng emoji. Nút/vùng bấm ≥ 44px. Trang co giãn, xuống hàng ở màn điện thoại.

### 4.2 Bố cục trang Hỏi đáp
1. **Header** xanh đậm: logo lá + "Hỏi Lá" / "Hỏi đáp bệnh lá cây bằng tiếng Việt"; menu viên thuốc:
   Hỏi đáp (đang chọn, nền vàng) · Bộ dữ liệu · Phương pháp · Kết quả.
2. **Hero** xanh đậm: "Chụp một chiếc lá, hỏi bằng lời của bạn." + mô tả; 3 ô số: **24.195** cặp hỏi–đáp ·
   **18.747** ảnh lá cây · **9** dạng câu hỏi.
3. Thân trang 2 cột (thẻ trắng đè lên hero −48px):
   - **Cột trái – Bước 1 "Chọn ảnh lá cây"**: ảnh đang chọn lớn (nhãn "Ảnh mẫu · Lá cà chua"); vùng
     **"Tải ảnh của bạn lên"** (JPG/PNG ≤10 MB, gợi ý "Chụp rõ một lá, đủ sáng"); lưới 4 cột ảnh mẫu
     (hàng trên ảnh PlantVillage, hàng dưới ảnh ngoài vườn có ghi nguồn/giấy phép).
   - **Cột phải – Bước 2 "Bạn muốn hỏi gì?"**: 9 chip câu hỏi gợi ý (mục 4.4) + ô câu hỏi + nút vàng
     "Hỏi ngay". **Bước 3 "Câu trả lời"**: nhãn trạng thái ("Đang chạy trên MacBook · 4 mô hình");
     khối xanh đậm = câu trả lời mô hình tốt nhất (NoRA · E3) + thời gian chạy + so với đáp án bộ dữ liệu
     (chỉ khi là ảnh mẫu có đáp án); bên dưới "So sánh với các mô hình khác" (E1, E2, E0; E0 nền `#FBF7EC`).
   - **Hộp cảnh báo** (luôn hiện): "Đây là mô hình nghiên cứu, học từ ảnh lá chụp trên nền trơn. Với ảnh chụp
     ngoài ruộng, câu trả lời có thể sai. Hãy hỏi thêm cán bộ khuyến nông trước khi phun thuốc."
4. **Footer**: "DSP391 · Nhóm 1 · Qwen3-VL-2B tinh chỉnh LoRA/NoRA trên PlantVillageVQA-Vie" + link phần nghiên cứu.

Mockup dùng câu trả lời thật của mẫu `row_017244` (`image_046993.JPG`, lá cà chua) trong
`Model_Khoa/results/new/2026-10-31_01/E*/predictions.normal.jsonl`; thời gian chạy để `[thời gian chạy]` vì chưa đo.

### 4.3 Ảnh trong mockup
| `/_blob/<id>` | File gốc (trong `Final_report/Model_Khoa/`) |
|---|---|
| `30e4c6c8…` | `reports/extracted/section_vi/review_images/image_046993.JPG` (cà chua, xoăn vàng lá) |
| `af78c187…` | `…/review_images/image_044461.JPG` (cam, vàng lá gân xanh) |
| `92b98f62…` | `…/review_images/image_046583.JPG` (táo) |
| `684c6ac2…` | `…/review_images/image_049476.JPG` (ớt chuông) |
| `079f9537…` | `…/review_images/image_045864.JPG` (lá khỏe) |
| `07abfac7…` | `…/review_images/image_044441.JPG` |
| `d4cb4bb7…` | `web-demo/samples/real-world/rw01_tomato_early_blight.jpg` (Dwight Sipler, CC BY 2.0) |
| `4a952bb8…` | `web-demo/samples/real-world/rw03_apple_scab.jpg` (James Lindsey, CC BY-SA 3.0) |
| `540ad484…` | `web-demo/samples/real-world/rw05_corn_common_rust.jpg` (Daren Mueller, Bugwood.org, CC BY 3.0 US) |

### 4.4 Chip câu hỏi gợi ý (ánh xạ 9 `question_type` của dataset)
| Chip | question_type |
|---|---|
| Lá có khỏe không? | General Health Assessment |
| Đây là cây gì? | Plant Species Identification |
| Lá bị bệnh gì? | Specific Disease Identification |
| Vì sao lá bị như vậy? | Causal Reasoning |
| Mô tả những gì thấy trên lá | Comprehensive Description |
| Có vết đốm đặc trưng không? | Visual Attribute Grounding |
| Có phải bệnh … không? | Detailed Verification |
| Nếu bị bệnh khác thì sao? | Counterfactual Reasoning |
| Ảnh có lá cây không? | Existence & Sanity Check |

Khi bấm chip, nên điền vào ô câu hỏi một câu theo **đúng văn phong câu hỏi trong dataset** (lấy ví dụ thật
từ dataset cho question_type đó, thay tên cây nếu biết) vì model chỉ học 9 dạng này.

---

## 5. Chức năng tải ảnh lên (mới so với bản Khoa)

- Chỉ chạy ở bản local (bản tĩnh chia sẻ: nút tải ảnh báo "chỉ dùng được khi chạy trên máy").
- Kiểm tra loại file (JPEG/PNG, kiểm tra nội dung chứ không chỉ đuôi), giới hạn dung lượng (~10 MB), resize
  hợp lý trước khi đưa vào processor. Xử lý xong thì **không lưu ảnh**; không ghi log nội dung ảnh.
- Ảnh tải lên không có đáp án → **không chấm điểm**, chỉ hiện câu trả lời.
- Không cho client chọn đường dẫn file trên máy hoặc đổi tham số sinh (giữ nguyên nguyên tắc của bản Khoa).
- Luôn hiện hộp cảnh báo: model học từ ảnh PlantVillage (lá đơn, nền trơn, chụp trong phòng); ảnh ngoài ruộng
  sẽ kém chính xác; không phải công cụ chẩn đoán.

---

## 6. Sự thật về dữ liệu và kết quả (không được viết sai)

Dữ liệu (pipeline mới, chạy xong 27–28/10/2026):
- Nguồn HF `SyedNazmusSakib/PlantVillageVQA`, revision `a025a438…`; 193.609 QA, chỉ train/test, 9 question_type.
- Step 1: lấy mẫu phân tầng split × question_type, 12,5%, seed 42 → 24.201 dòng, 18.751 ảnh, 7.522 cặp, 1.088 câu hỏi.
- Step 2: Claude Sonnet dịch theo cặp; chuẩn hoá viết tắt HLB/TYLCV/ToMV; luật: 7.508 cặp qua, 14 trượt (96 dòng).
- Step 3: smoke test 40/40 bắt, 0/10 báo nhầm; Codex gpt-6-luna chấm: 7.489 PASS, 19 NEEDS_REPAIR; Claude sửa 1 lần
  33 cặp → 30 PASS_AFTER_REPAIR (223 dòng), 3 UNRESOLVED (6 dòng).
- Kết quả: **24.195 dòng / 18.747 ảnh / 7.519 cặp / 1.088 câu hỏi; train 19.366, test 4.829.**
  4 bộ test: normal, blank, noimage, shuffled.
- Chỉ PASS + PASS_AFTER_REPAIR được gọi là **"automatically validated silver-standard"** (tiếng Việt: "đã kiểm định
  tự động, mức silver-standard"). **Không được nói "đã được người kiểm định".**

Model: Qwen3-VL-2B-Instruct; E0 zero-shot, E1 LoRA, E2 NoRA-init, E3 NoRA; adapter trên q/k/v/o của language
decoder, r=16, α=16; vision encoder đóng băng; AdamW lr 2e-4, 3 epoch, effective batch 16, bf16, seed 42,
answer-only loss. Chia tập theo ảnh: giữ test, ~10% ảnh train → validation (1.938 QA).

Kết quả trên dữ liệu mới (nguồn: `Model_Khoa/results/new/2026-10-31_01/comparison.csv`, test 4.829 QA;
BLEU-4/METEOR/ROUGE tính trên free-text):

| Run | Overall | Yes/No | Free-text | BLEU-4 | METEOR | ROUGE-L |
|---|---|---|---|---|---|---|
| E0 | 0,00 | 0,00 | 0,00 | 0,87 | 11,82 | 10,14 |
| E1 LoRA | 57,76 | 96,24 | 30,08 | 36,42 | 52,04 | 57,10 |
| E2 NoRA-init | 60,78 | 97,33 | 34,50 | 40,46 | 56,21 | 61,05 |
| E3 NoRA | 61,25 | 96,93 | 35,60 | 40,34 | 56,91 | 62,12 |

Ablation (overall, E3): normal 61,25 → blank 29,20 → noimage 31,75 → shuffled 35,80.
Kết quả trong `results/old/` là dữ liệu CŨ (20k QA, đã bỏ): **không trình bày như kết quả dữ liệu mới.**

Quy tắc khi viết nội dung web: số liệu phải lấy từ file trong repo, ghi rõ nguồn; không bịa question_type,
model, metric, kết quả; thiếu thì ghi "chưa có". Lưu ý: "exact match" — câu trả lời đúng bệnh nhưng khác câu chữ
vẫn bị tính sai, nên khi so với đáp án trên web dùng nhãn kiểu "Cùng bệnh với đáp án" hoặc hiện song song,
không ghi "khớp đáp án" nếu không khớp từng chữ.

---

## 7. Vị trí làm việc và quy tắc repo

- Repo dữ liệu của Thịnh (public): `~/Documents/FPTU/FA26/DSP/DSP391_PlantVillageVQA_Final/`
  (github.com/dnct2795/DSP_PlantVillageVQA_Vie_Final). Đề xuất đặt demo ở `web_demo_thinh/` trong repo này
  — **hỏi người dùng xác nhận** trước khi tạo, và hỏi trước khi commit/push.
- `Final_report/` (gồm `Model_Khoa/`) hiện là thư mục **untracked** trong repo dữ liệu; không `git add` nó.
- Repo dữ liệu public → không commit adapter, model, token, `kaggle.json`, ảnh người dùng tải lên.
  Ghi credit "dựa trên web demo của Khoa" trong README của demo.
- `CLAUDE.md` của repo dữ liệu có bảng trạng thái cũ (ghi Step 2–3 "chưa làm", sai): tin `PROGRESS.md` và mục 6
  của file này hơn. Không ghi đè/xoá file kết quả.
- Ghi tiến trình vào `PROGRESS.md` (mục mới ở đầu file) khi xong mỗi mốc.

---

## 8. Thứ tự làm đề xuất

1. Kiểm tra môi trường: `sw_vers`, `python3 --version`, `node --version`, dung lượng trống; `git pull --ff-only`
   ở `Model_Khoa`.
2. Đọc `Model_Khoa/web-demo/README.md`, `src/pvvqa/web/*.py`, `configs/web_demo.yaml`, `vendor/README.md`.
3. Tạo `web_demo_thinh/` (sau khi người dùng đồng ý), copy frontend + backend + config + vendor cần thiết.
4. Chạy chế độ `PVVQA_DEMO_NO_GPU=1` để xem frontend cũ chạy được trên Mac.
5. Cài PyTorch có MPS + bản PEFT trong `vendor/`; tải base model; người dùng tải adapter từ Drive.
6. Chuyển backend sang MPS/fp16, chạy thử E0 → E1 → E3 với 1 ảnh mẫu, đo thời gian và RAM; báo người dùng.
7. Dựng lại giao diện theo Hướng A, toàn bộ tiếng Việt; thêm upload ảnh + chip câu hỏi.
8. Làm các trang Bộ dữ liệu / Phương pháp / Kết quả bằng tiếng Việt, số liệu theo mục 6.
9. Chạy test (Playwright) và thử tay; ghi `PROGRESS.md`.

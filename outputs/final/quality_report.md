# Quality report — PlantVillageVQA tiếng Việt (Phase 1)

Tạo lúc 2026-10-27T17:11:18+00:00, commit `978faae`.

## 1. Nguồn

- HF `SyedNazmusSakib/PlantVillageVQA`, revision `a025a438308eff9a7289231ebc09e27e8ec6678c`, file QA `PlantVillageVQA/PlantVillageVQA.csv`.
- 193,609 dòng QA; split thực tế: test, train (không có val).
- Cột: `image_id, question_type, question, answer, image_path, split` — dataset tiếng Việt giữ đúng các cột và thứ tự này.

## Pipeline (một lần chạy, tự động hoàn toàn, có checkpoint)

1. **Step 1 — Lấy mẫu đại diện:** phân tầng tỷ lệ theo `split × question_type`, 12,5%, seed 42.
2. **Step 2 — Dịch EN→VI theo ngữ cảnh (Claude Sonnet):** 2.1 gom cặp QA trùng; 2.2 glossary cố định (tên khoa học giữ nguyên; viết tắt HLB/TYLCV/ToMV dịch thành tên tiếng Việt đầy đủ); 2.3 dịch theo batch câu hỏi, một `question_vi` dùng chung cho mỗi câu hỏi EN, quy tắc Yes/No; 2.5 chuẩn hoá thuật ngữ theo glossary bằng luật (thay viết tắt còn sót bằng tên tiếng Việt đầy đủ); 2.6 kiểm tra bằng luật.
3. **Step 3 — Đánh giá độc lập và sửa chọn lọc:** 3.1 smoke test judge; 3.2 Codex `gpt-6-luna` (reasoning `high`) chấm mọi cặp qua luật (lỗi kiểu MQM); 3.3 Claude sửa đúng một lần các cặp trượt luật hoặc NEEDS_REPAIR (bản sửa cũng qua 2.5 và 2.6), rồi chấm lại.
- Lần chạy bị ngắt (hết quota, lỗi gọi model) được chạy tiếp từ checkpoint. Thứ tự thực thi thực tế và mọi lần chấm được lưu trong `runs/` và `PROGRESS.md`.

## 2. Phân phối split × question_type

Subset: lấy mẫu phân tầng tỷ lệ 12.5%, seed 42.

| split | question_type | gốc | % | subset EN | % | VI cuối | % | mất |
|---|---|---|---|---|---|---|---|---|
| test | Causal Reasoning | 5,230 | 2.701 | 654 | 2.702 | 653 | 2.699 | 1 |
| test | Comprehensive Description | 5,573 | 2.878 | 697 | 2.880 | 697 | 2.881 | 0 |
| test | Counterfactual Reasoning | 2,021 | 1.044 | 253 | 1.045 | 253 | 1.046 | 0 |
| test | Detailed Verification | 2,848 | 1.471 | 356 | 1.471 | 356 | 1.471 | 0 |
| test | Existence & Sanity Check | 617 | 0.319 | 77 | 0.318 | 77 | 0.318 | 0 |
| test | General Health Assessment | 6,365 | 3.288 | 796 | 3.289 | 796 | 3.290 | 0 |
| test | Plant Species Identification | 6,794 | 3.509 | 849 | 3.508 | 849 | 3.509 | 0 |
| test | Specific Disease Identification | 5,979 | 3.088 | 747 | 3.087 | 747 | 3.087 | 0 |
| test | Visual Attribute Grounding | 3,205 | 1.655 | 401 | 1.657 | 401 | 1.657 | 0 |
| train | Causal Reasoning | 20,993 | 10.843 | 2,624 | 10.843 | 2,622 | 10.837 | 2 |
| train | Comprehensive Description | 22,236 | 11.485 | 2,779 | 11.483 | 2,776 | 11.473 | 3 |
| train | Counterfactual Reasoning | 7,960 | 4.111 | 995 | 4.111 | 995 | 4.112 | 0 |
| train | Detailed Verification | 11,241 | 5.806 | 1,405 | 5.806 | 1,405 | 5.807 | 0 |
| train | Existence & Sanity Check | 2,228 | 1.151 | 278 | 1.149 | 278 | 1.149 | 0 |
| train | General Health Assessment | 25,734 | 13.292 | 3,217 | 13.293 | 3,217 | 13.296 | 0 |
| train | Plant Species Identification | 27,357 | 14.130 | 3,420 | 14.132 | 3,420 | 14.135 | 0 |
| train | Specific Disease Identification | 23,947 | 12.369 | 2,993 | 12.367 | 2,993 | 12.370 | 0 |
| train | Visual Attribute Grounding | 13,281 | 6.860 | 1,660 | 6.859 | 1,660 | 6.861 | 0 |
| **tổng** | | **193,609** | | **24,201** | | **24,195** | | **6** |

## 3. Trạng thái kiểm định

| trạng thái | cặp | % cặp | dòng | % dòng |
|---|---|---|---|---|
| PASS | 7,489 | 99.56% | 23,972 | 99.05% |
| PASS_AFTER_REPAIR | 30 | 0.40% | 223 | 0.92% |
| UNRESOLVED | 3 | 0.04% | 6 | 0.02% |

- PASS = qua kiểm tra luật và judge không thấy lỗi major/critical ở lần chấm đầu.
- PASS_AFTER_REPAIR = trượt luật hoặc bị judge đánh NEEDS_REPAIR, Claude sửa đúng một lần, qua luật và judge chấm lại PASS. Trong đó 5 cặp không đổi chữ nào sau repair nhưng lần chấm lại cho PASS (xem mục 6).
- UNRESOLVED = không đạt sau repair; không sửa thêm, không thay mẫu.
- Chỉ PASS + PASS_AFTER_REPAIR có trong `PlantVillageVQA_vi.csv/.json`; mọi dòng (kể cả UNRESOLVED) có trong `PlantVillageVQA_vi_en_alignment.csv`.

## 4. Tính nhất quán câu hỏi

- Số câu hỏi EN có nhiều hơn một `question_vi`: **0** (mục tiêu 0).

## 5. Smoke test judge (`gpt-6-luna`, reasoning `high`)

Mục cố ý sai sinh tự động bằng thay chuỗi trên bản dịch đã qua luật. **Không phải hiệu chuẩn.**

- conditional: Codex bắt được 10/10
- control: báo nhầm 0/10
- crop: Codex bắt được 10/10
- disease: Codex bắt được 10/10
- polarity: Codex bắt được 10/10

Kiểm tra chéo với `gpt-6.1-sol high` trên 120 cặp ngẫu nhiên: đồng ý verdict 120/120; judge chính PASS nhưng model đối chiếu NEEDS_REPAIR: 0; ngược lại: 0. Vì tỷ lệ NEEDS_REPAIR thật chỉ ~0,2%, mẫu gần như toàn PASS: kết quả chỉ cho thấy model đối chiếu không tìm thêm lỗi major mà judge chính bỏ sót (tỷ lệ bỏ sót < ~2.5%, độ tin cậy 95%, quy tắc 3/n), không đo được độ nhạy với lỗi.

## 6. Giới hạn

Mỗi mục ghi vấn đề, số liệu, ảnh hưởng và cách xử lý hoặc khuyến nghị.

### 6.1 Kiểm định tự động, chưa có người kiểm tra

- Dữ liệu là *automatically validated silver-standard*: Codex là lớp đánh giá ngữ nghĩa duy nhất, chưa hiệu chuẩn với người chấm. Không gọi là "đã được người kiểm định".
- Bằng chứng đã có: smoke test (mục 5) và kiểm tra chéo với một model mạnh hơn. Mẫu kiểm tra chéo gần như toàn PASS nên chỉ chặn trên tỷ lệ bỏ sót lỗi nặng, không đo được độ nhạy với lỗi tinh tế.
- Judge không ổn định ở ca ranh giới: cùng một bản dịch có thể bị NEEDS_REPAIR lần này và PASS lần khác. Ví dụ "… hay còn gọi là bệnh vàng rồng cây có múi" bị đánh lỗi ở 3 cặp nhưng PASS ở 1 cặp khác (cặp đó vẫn còn trong dataset).
- Khuyến nghị: cho người chấm một mẫu ngẫu nhiên (ví dụ 200 cặp) để ước lượng tỷ lệ lỗi thật.

### 6.2 Lỗi minor không được sửa

- Theo thiết kế, PASS = không có lỗi major/critical; cặp chỉ có lỗi minor (nghĩa vẫn đúng, văn phong chưa mượt) giữ nguyên, không đi sửa.
- Dataset cuối còn **299 cặp / 1,277 dòng** có lỗi minor: fluency 253, terminology 34, addition 11, mistranslation 4.
- Ví dụ: "đốm lốm đốm" (cho *stippling*) lặp từ; câu hỏi tự thêm "trên lá"; "chẩn đoán chắc chắn" cho *authoritative diagnosis*.
- Lý do: nghĩa vẫn đúng; dịch lại có thể sinh lỗi mới; giữ pipeline đơn giản. Mọi lỗi minor nằm ở cột `judge_errors` / `rejudge_errors` của bản đối chiếu.

### 6.3 Dữ liệu gốc sinh từ template, độ đa dạng ngôn ngữ thấp

- Nguồn có 193,609 dòng nhưng chỉ **1,213 câu hỏi** và **125 câu trả lời** khác nhau; "No" lặp 48,453 lần, "Yes" 33,091 lần; bệnh mốc sương ở câu nhận diện bệnh chỉ có 4 cách nói, mỗi cách lặp khoảng 720 lần.
- Ảnh hưởng: model dễ đoán theo mẫu câu mà không nhìn ảnh, và có thể lúng túng với câu hỏi tự nhiên của người dùng thật. Bản tiếng Việt dịch sát nguồn nên giữ nguyên tính lặp này.
- Cách đo: 3 bộ test ablation (blank, noimage, shuffled) cho biết model dựa vào câu hỏi đến đâu.

### 6.4 Lỗi template trong nguồn: câu hỏi "What …?" có đáp án Yes/No

- File gốc có 3 câu hỏi dạng hỏi mở nhưng được trả lời Yes/No, tổng 434 dòng (đều là General Health Assessment). Ví dụ dòng 224: `image_000088.JPG`, *"What disease indicators appear on this vegetation?"* → "Yes".

| Câu hỏi gốc | Yes (nguồn) | No (nguồn) | Dòng trong dataset VI | Bản dịch |
|---|---|---|---|---|
| What disease indicators appear on this vegetation? | 104 | 28 | 21 | Thảm thực vật này có xuất hiện dấu hiệu bệnh không? |
| What pathological signs are visible on this leaf specimen? | 135 | 13 | 22 | Mẫu lá này có thấy được dấu hiệu bệnh lý nào không? |
| What symptomatic characteristics are present here? | 131 | 23 | 25 | Ở đây có xuất hiện các đặc điểm triệu chứng nào không? |

- Nguyên nhân có lẽ (phỏng đoán, paper không nói rõ): khi diễn đạt lại mẫu câu Yes/No, một vài câu bị đổi thành dạng "What …?" nhưng đáp án vẫn giữ nguyên.
- Cách xử lý: giữ đúng nhãn gốc, dịch câu hỏi sang dạng "… có … nào không?" cho khớp đáp án Có/Không. Bản tiếng Việt tự nhiên hơn bản gốc nhưng không sát từng chữ với câu EN; đây là lý do một số cặp PASS_AFTER_REPAIR không đổi chữ nào sau bước sửa.

### 6.5 Ảnh hưởng của việc lấy mẫu 12,5% theo dòng

| | Gốc | Dataset VI |
|---|---|---|
| QA trên mỗi ảnh | 3.87 | 1.29 |
| Cặp QA duy nhất | 15,065 | 7,519 |
| Cặp hỏi–đáp test đã có y hệt trong train | 98.2% | 79.9% |
| Câu hỏi test đã có trong train | 100% | 99.7% |

- Cặp bị mất chủ yếu là cặp hiếm (2,227 cặp chỉ xuất hiện 1 lần trong nguồn).
- Khoảng 20% cặp trong test có câu trả lời (thường là câu mở) chưa xuất hiện y hệt trong train. Khuyến nghị: chấm câu trả lời mở bằng độ tương đồng (BLEU, ROUGE, BERTScore) hoặc theo ý chính (tên bệnh, tên cây), không dùng so khớp chính xác. Câu Yes/No không bị ảnh hưởng.
- Mỗi ảnh ~1.3 câu hỏi: đổi lại có 18,747 ảnh khác nhau (lấy mẫu theo ảnh chỉ được khoảng 6,252), có lợi cho học hình ảnh. Hạn chế: không phân tích được tính nhất quán của model trên nhiều câu hỏi cùng một ảnh.

### 6.6 Mất cân bằng lớp và không có tập validation

- Mất cân bằng thừa hưởng từ PlantVillage: bệnh vàng lá gân xanh trên cam và virus xoăn vàng lá cà chua chiếm khoảng 35% số dòng; một số tổ hợp cây/bệnh hiếm chỉ còn vài đến vài chục dòng. Subset giữ đúng phân phối này vì mục tiêu là đại diện.
- Nguồn chỉ có train/test (README nhắc tới val nhưng dữ liệu không có). Khi cần val, tách từ train **theo ảnh** (không theo dòng) để một ảnh không nằm ở cả train và val.

## Chi phí (gói Claude Pro / ChatGPT Plus, không dùng API trả phí)

- Step 2 (Claude Sonnet): 2,359,115 token vào, 558,748 token ra, 75 phút model
- Step 3 (Codex judge, smoke test, kiểm tra chéo, Claude repair, chấm lại): 3,576,214 token vào, 287,623 token ra, 68 phút model

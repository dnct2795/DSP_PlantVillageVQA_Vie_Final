# Quality report — PlantVillageVQA tiếng Việt (Phase 1)

Tạo lúc 2026-10-27T16:46:47+00:00, commit `7efcd18`.

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

- Codex (một model) là lớp đánh giá ngữ nghĩa duy nhất; chưa hiệu chuẩn với người chấm. Nhãn chất lượng là *automatically validated silver-standard*, không phải đã được người kiểm định.
- Judge không ổn định ở ca ranh giới: cùng một bản dịch có thể bị chấm NEEDS_REPAIR lần đầu và PASS khi chấm lại.
- Dữ liệu gốc sinh từ template: câu hỏi/câu trả lời lặp nhiều, độ đa dạng ngôn ngữ thấp. Có lỗi template ở nguồn (ví dụ 3 câu hỏi dạng "What …?" nhưng đáp án Yes/No); bản dịch giữ đúng đáp án gốc.
- Mất cân bằng lớp thừa hưởng từ PlantVillage (HLB trên cam và TYLCV trên cà chua chiếm khoảng 35% số dòng); subset giữ nguyên phân phối này.
- Subset 12,5% theo dòng: còn khoảng 50% số cặp QA duy nhất của nguồn, mỗi ảnh trung bình ~1,3 câu hỏi.
- Lỗi minor (chủ yếu độ trôi chảy) không được sửa theo thiết kế.
## Chi phí (gói Claude Pro / ChatGPT Plus, không dùng API trả phí)

- Step 2 (Claude Sonnet): 2,359,115 token vào, 558,748 token ra, 75 phút model
- Step 3 (Codex judge, smoke test, kiểm tra chéo, Claude repair, chấm lại): 3,576,214 token vào, 287,623 token ra, 68 phút model

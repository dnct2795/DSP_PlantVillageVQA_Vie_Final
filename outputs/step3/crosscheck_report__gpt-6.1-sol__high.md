# Kiểm tra chéo judge (KHÔNG phải hiệu chuẩn)

- Judge chính: `gpt-6-luna high`; model đối chiếu: `gpt-6.1-sol high`; mẫu ngẫu nhiên 120 cặp đã qua luật (seed 42), chấm trên bản dịch Step 2 (trước repair).

- Đồng ý về verdict: **120/120**
- Judge chính PASS nhưng model đối chiếu NEEDS_REPAIR: **0**
- Judge chính NEEDS_REPAIR nhưng model đối chiếu PASS: **0**
- Có ít nhất một lỗi (kể cả minor): judge chính 5, đối chiếu 7

## Các cặp bất đồng


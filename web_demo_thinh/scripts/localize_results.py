"""Thay phần `qualitative` (bản dịch tiếng Anh của Khoa) trong generated/results.json bằng tiếng Việt gốc
lấy từ content/4_error_examples.csv (CSV trích từ báo cáo). Chạy một lần sau khi copy từ repo Khoa."""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NOTES_VI = {
    'row_017553': 'Cả đáp án lẫn dự đoán đều nói cây khỏe mạnh nhưng khác câu chữ, nên bị tính sai theo khớp chính xác. '
                  'Phân loại lỗi này là tạm thời, chưa có chuyên gia phân xử.',
    'row_017542': 'Ảnh đưa vào là ảnh tráo (ảnh của dòng khác); đáp án vẫn thuộc ảnh gốc. Dự đoán lệch đáp án gốc chưa chắc '
                  'đã sai với ảnh thật được đưa vào. Phân loại lỗi là tạm thời.',
}
CATEGORY_VI = {
    'semantically-correct-but-metric-mismatch': 'Đúng ý nhưng không khớp câu chữ',
    'visual misrecognition': 'Nhận dạng thị giác sai (ảnh tráo)',
}
path = ROOT / 'generated/results.json'
data = json.loads(path.read_text())
with (ROOT / 'content/4_error_examples.csv').open(encoding='utf-8-sig', newline='') as f:
    cases = {row['row_id']: row for row in csv.DictReader(f)}
for item in data['qualitative']:
    row = cases[item['row_id']]
    item.update(question=row['question'], reference=row['ground_truth'],
                predictions=[row['prediction_E1'], row['prediction_E2'], row['prediction_E3']],
                note=NOTES_VI.get(item['row_id'], item['note']),
                category_vi=CATEGORY_VI.get(item['category'], item['category']))
path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(data['qualitative'], ensure_ascii=False, indent=1))

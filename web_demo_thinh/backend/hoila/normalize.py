# Sao chép từ pvvqa/evaluation/normalize.py (repo model của Khoa) để demo không phụ thuộc package pvvqa.
import re
import unicodedata


def normalize_vi(text):
    text = unicodedata.normalize('NFC', text).strip().lower()
    text = re.sub(r'\s+', ' ', text)
    return re.sub(r'[.!?,;:]+$', '', text).strip()

import pandas as pd

from pvvqa.export_final import SOURCE_COLS, to_source_json


def test_to_source_json_matches_source_structure():
    df = pd.DataFrame([
        ["img1.jpg", "Detailed Verification", "Lá này có bệnh không?", "Có", "images/train/img1.jpg", "train"],
        ["img1.jpg", "Causal Reasoning", "Nguyên nhân là gì?", "Do nấm.", "images/train/img1.jpg", "train"],
        ["img2.JPG", "Detailed Verification", "Lá này có bệnh không?", "Không", "images/test/img2.JPG", "test"],
    ], columns=SOURCE_COLS)
    js = to_source_json(df)
    assert list(js) == ["img1.jpg", "img2.JPG"]
    assert js["img1.jpg"]["image_path"] == "images/train/img1.jpg" and js["img2.JPG"]["split"] == "test"
    assert js["img1.jpg"]["questions"] == [
        {"question_type": "Detailed Verification", "question": "Lá này có bệnh không?", "answer": "Có"},
        {"question_type": "Causal Reasoning", "question": "Nguyên nhân là gì?", "answer": "Do nấm."}]


def test_source_columns_order():
    assert SOURCE_COLS == ["image_id", "question_type", "question", "answer", "image_path", "split"]

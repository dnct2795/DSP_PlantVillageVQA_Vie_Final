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


def test_extract_images_places_files_at_image_path(tmp_path):
    import zipfile
    from pvvqa.package_kaggle import extract_images
    zp = tmp_path / "src.zip"
    with zipfile.ZipFile(zp, "w") as z:
        z.writestr("PlantVillageVQA/Images/image_000001.jpg", b"a")
        z.writestr("PlantVillageVQA/Images/image_000002.JPG", b"bb")
        z.writestr("PlantVillageVQA/Images/image_000003.jpg", b"c")  # không thuộc subset
    paths = pd.Series(["images/train/image_000001.jpg", "images/test/image_000002.JPG",
                       "images/train/image_000001.jpg", "images/train/image_999999.jpg"])
    out = tmp_path / "pkg"
    r = extract_images(zp, paths, out)
    assert r["missing"] == ["images/train/image_999999.jpg"] and r["images_extracted_now"] == 2
    assert (out / "images/test/image_000002.JPG").read_bytes() == b"bb"
    assert not (out / "images/train/image_000003.jpg").exists()
    assert extract_images(zp, paths, out)["images_extracted_now"] == 0  # chạy lại: không chép lại


def test_test_sets_derangement_and_shapes():
    import numpy as np
    from pvvqa.make_test_sets import BLANK_PATH, build, derange
    imgs = pd.Series(["a", "a", "b", "c", "c", "c", "d", "e"])
    out = derange(imgs, 1)
    assert (out != imgs.to_numpy()).all() and sorted(out) == sorted(imgs)
    vi = pd.DataFrame({"image_id": ["a", "b", "c", "x"], "question_type": ["t"] * 4,
                       "question": ["q1", "q2", "q3", "q4"], "answer": ["Có", "Không", "x", "y"],
                       "image_path": ["images/test/a", "images/test/b", "images/test/c", "images/train/x"],
                       "split": ["test", "test", "test", "train"]})
    s = build(vi, pd.Series(["i1", "i2", "i3", "i4"]))
    assert all(list(s[k].columns) == SOURCE_COLS for k in ("test_normal", "test_blank", "test_noimage", "test_shuffled"))
    assert len(s["test_normal"]) == 3 and (s["test_blank"].image_path == BLANK_PATH).all()
    assert (s["test_noimage"].image_path == "").all()
    sh = s["test_shuffled"]
    assert (sh.image_id != s["test_normal"].image_id).all()
    assert all(p == f"images/test/{i}" for i, p in zip(sh.image_id, sh.image_path))  # path khớp ảnh mới
    assert list(s["test_sets_map"].qa_id) == ["i1", "i2", "i3"]

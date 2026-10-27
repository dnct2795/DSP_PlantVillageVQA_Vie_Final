"""Bộ test cho ablation study: kiểm tra model có dùng ảnh hay chỉ dựa vào văn bản (text bias).

  PYTHONPATH=src python -m pvvqa.make_test_sets

Từ các dòng split == "test" của outputs/final/PlantVillageVQA_vi.csv, ghi vào outputs/final/test_sets/
4 bộ cùng QA, cùng thứ tự dòng, cùng cột với dataset gốc (image_id, question_type, question, answer,
image_path, split); chỉ khác phần ảnh:
  test_normal.csv     ảnh gốc
  test_blank.csv      mọi dòng dùng một ảnh trắng 256x256 (images/blank/blank.jpg)
  test_noimage.csv    image_id và image_path để trống
  test_shuffled.csv   hoán vị ảnh giữa các dòng (seed 42): không dòng nào nhận lại ảnh của chính nó
  test_sets_map.csv   qa_id + ảnh của từng bộ, để đối chiếu kết quả giữa các bộ
  blank.jpg           ảnh trắng
"""
from __future__ import annotations

import json
import sys

import numpy as np
import pandas as pd

from pvvqa.common import ROOT, load_config
from pvvqa.export_final import SOURCE_COLS

BLANK_ID, BLANK_PATH = "blank.jpg", "images/blank/blank.jpg"
BLANK_SIZE, BLANK_COLOR = (256, 256), (255, 255, 255)


def derange(images: pd.Series, seed: int = 42) -> np.ndarray:
    """Hoán vị các giá trị của `images` sao cho không vị trí nào giữ lại đúng giá trị của nó.
    Giữ nguyên tập ảnh (mỗi ảnh xuất hiện đúng số lần như bộ gốc)."""
    rng = np.random.default_rng(seed)
    src = images.to_numpy()
    out = src[rng.permutation(len(src))]
    for _ in range(100):
        bad = np.flatnonzero(out == src)
        if not len(bad):
            return out
        for i in bad:
            for j in rng.permutation(len(src)):  # đổi chỗ với j sao cho cả i và j đều hợp lệ
                if out[j] != src[i] and out[i] != src[j]:
                    out[i], out[j] = out[j], out[i]
                    break
    raise RuntimeError("không tìm được hoán vị hợp lệ")


def build(vi: pd.DataFrame, qa_ids: pd.Series, seed: int = 42) -> dict[str, pd.DataFrame]:
    test = vi[vi.split == "test"].reset_index(drop=True)
    ids = qa_ids[vi.split.to_numpy() == "test"].reset_index(drop=True)
    perm = derange(test.image_id, seed)
    path_of = dict(zip(test.image_id, test.image_path))
    sets = {"test_normal": test.copy(),
            "test_blank": test.assign(image_id=BLANK_ID, image_path=BLANK_PATH),
            "test_noimage": test.assign(image_id="", image_path=""),
            "test_shuffled": test.assign(image_id=perm, image_path=[path_of[i] for i in perm])}
    sets = {k: v[SOURCE_COLS] for k, v in sets.items()}
    sets["test_sets_map"] = pd.DataFrame({
        "qa_id": ids, "image_id_normal": test.image_id, "image_id_shuffled": perm,
        "image_path_shuffled": sets["test_shuffled"].image_path, "image_id_blank": BLANK_ID})
    return sets


def main() -> int:
    from PIL import Image
    cfg = load_config()
    final = ROOT / "outputs" / "final"
    out = final / "test_sets"
    out.mkdir(parents=True, exist_ok=True)
    vi = pd.read_csv(final / "PlantVillageVQA_vi.csv", keep_default_na=False)
    # qa_id của từng dòng dataset VI (cùng thứ tự): lấy từ bản đối chiếu, chỉ các dòng được giữ lại
    al = pd.read_csv(final / "PlantVillageVQA_vi_en_alignment.csv", keep_default_na=False)
    al = al[al.status.isin(["PASS", "PASS_AFTER_REPAIR"])].reset_index(drop=True)
    assert (al.image_id.to_numpy() == vi.image_id.to_numpy()).all() and len(al) == len(vi)
    sets = build(vi, al.qa_id, cfg["sampling"]["seed"])
    for name, d in sets.items():
        d.to_csv(out / f"{name}.csv", index=False, encoding="utf-8")
    Image.new("RGB", BLANK_SIZE, BLANK_COLOR).save(out / BLANK_ID, quality=95)
    sh, no = sets["test_shuffled"], sets["test_normal"]
    rep = {"rows_per_set": len(no), "images_normal": int(no.image_id.nunique()),
           "shuffled_same_image_as_original": int((sh.image_id == no.image_id).sum()),
           "shuffled_image_multiset_equal": bool(sorted(sh.image_id) == sorted(no.image_id)),
           "qa_identical_across_sets": all((d[["question_type", "question", "answer", "split"]]
                                            .equals(no[["question_type", "question", "answer", "split"]]))
                                           for k, d in sets.items() if k != "test_sets_map")}
    (out / "test_sets_report.json").write_text(json.dumps(rep, indent=1), encoding="utf-8")
    print(json.dumps(rep, ensure_ascii=False))
    return 0 if rep["shuffled_same_image_as_original"] == 0 and rep["qa_identical_across_sets"] else 1


if __name__ == "__main__":
    sys.exit(main())

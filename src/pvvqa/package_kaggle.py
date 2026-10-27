"""Đóng gói dataset tiếng Việt + ảnh để đưa lên Kaggle (không gọi model, không upload).

  PYTHONPATH=src python -m pvvqa.package_kaggle --zip data/raw/hf/PlantVillageVQA.zip

Ghi vào outputs/kaggle/ (git-ignored):
  PlantVillageVQA_vi.csv, PlantVillageVQA_vi.json, PlantVillageVQA_vi_en_alignment.csv, quality_report.md
  images/<split>/<file>   ảnh của subset, đặt đúng theo giá trị image_path gốc -> image_path dùng được ngay
  test_sets/*.csv, images/blank/blank.jpg   4 bộ test (normal + 3 ablation, xem pvvqa.make_test_sets)
  README.md               dataset card (docs/kaggle_dataset_card.md), cũng là mô tả trên Kaggle
  dataset-metadata.json   metadata cho `kaggle datasets create`
Ảnh lấy từ zip HF đã ghim revision (`PlantVillageVQA/Images/<file>`), khớp theo tên file.
Upload là bước riêng, chỉ làm khi người dùng đồng ý:
  kaggle datasets create -p outputs/kaggle --dir-mode zip        # mặc định private
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import zipfile
from pathlib import Path

import pandas as pd

from pvvqa.common import ROOT, load_config

FILES = ["PlantVillageVQA_vi.csv", "PlantVillageVQA_vi.json", "PlantVillageVQA_vi_en_alignment.csv",
         "quality_report.md"]


def extract_images(zip_path: Path, image_paths: pd.Series, out: Path) -> dict:
    """Giải nén ảnh cần dùng vào out/<image_path>. Trả số liệu kiểm tra."""
    with zipfile.ZipFile(zip_path) as z:
        by_name = {Path(m).name: m for m in z.namelist() if "/Images/" in m and not m.endswith("/")}
        missing, n_new = [], 0
        for ip in sorted(set(image_paths)):
            m = by_name.get(Path(ip).name)
            if m is None:
                missing.append(ip)
                continue
            dst = out / ip
            if dst.exists() and dst.stat().st_size == z.getinfo(m).file_size:
                continue  # đã có (chạy lại)
            dst.parent.mkdir(parents=True, exist_ok=True)
            with z.open(m) as src, open(dst, "wb") as f:
                shutil.copyfileobj(src, f)
            n_new += 1
    return {"images_needed": int(image_paths.nunique()), "images_extracted_now": n_new, "missing": missing}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--zip", default="data/raw/hf/PlantVillageVQA.zip")
    ap.add_argument("--slug", default="plantvillagevqa-vietnamese")
    ap.add_argument("--title", default="PlantVillageVQA Vietnamese Subset")
    args = ap.parse_args(argv)
    cfg = load_config()
    final, out = ROOT / "outputs" / "final", ROOT / "outputs" / "kaggle"
    out.mkdir(parents=True, exist_ok=True)
    for f in FILES:
        shutil.copy2(final / f, out / f)
    # bộ test cho ablation study (pvvqa.make_test_sets): CSV vào test_sets/, ảnh trắng vào images/blank/
    ts = final / "test_sets"
    (out / "test_sets").mkdir(exist_ok=True)
    for f in ("test_normal.csv", "test_blank.csv", "test_noimage.csv", "test_shuffled.csv", "test_sets_map.csv"):
        shutil.copy2(ts / f, out / "test_sets" / f)
    (out / "images" / "blank").mkdir(parents=True, exist_ok=True)
    shutil.copy2(ts / "blank.jpg", out / "images" / "blank" / "blank.jpg")
    vi = pd.read_csv(final / "PlantVillageVQA_vi.csv")
    chk = extract_images(ROOT / args.zip, vi.image_path, out)
    unresolved = [p for p in vi.image_path.unique() if not (out / p).is_file()]
    on_disk = sum(1 for _ in (out / "images").rglob("*") if _.is_file() and _.parent.name != "blank")
    chk.update({"image_paths_unresolved": len(unresolved), "image_files_on_disk": on_disk})
    import subprocess
    user = subprocess.run(["kaggle", "config", "view"], capture_output=True, text=True).stdout
    owner = next((l.split(":", 1)[1].strip() for l in user.splitlines() if "username" in l), "USERNAME")
    card = (ROOT / "docs" / "kaggle_dataset_card.md").read_text(encoding="utf-8")
    shutil.copy2(ROOT / "docs" / "kaggle_dataset_card.md", out / "README.md")
    meta = {"title": args.title, "id": f"{owner}/{args.slug}", "licenses": [{"name": "CC-BY-4.0"}],
            "subtitle": "Vietnamese plant-disease VQA: 24k QA rows, images, ablation test sets",
            "description": card,
            "keywords": ["agriculture", "plants", "nlp", "computer vision"]}
    (out / "dataset-metadata.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    size = sum(p.stat().st_size for p in out.rglob("*") if p.is_file())
    print(json.dumps({**chk, "missing": len(chk["missing"]), "package_bytes": size, "id": meta["id"]},
                     ensure_ascii=False))
    ok = not chk["missing"] and not unresolved and on_disk == chk["images_needed"]
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

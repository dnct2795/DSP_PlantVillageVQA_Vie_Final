"""Đóng gói dataset tiếng Việt + ảnh để đưa lên Kaggle (không gọi model, không upload).

  PYTHONPATH=src python -m pvvqa.package_kaggle --zip data/raw/hf/PlantVillageVQA.zip

Ghi vào outputs/kaggle/ (git-ignored):
  PlantVillageVQA_vi.csv, PlantVillageVQA_vi.json, PlantVillageVQA_vi_en_alignment.csv, quality_report.md
  images/<split>/<file>   ảnh của subset, đặt đúng theo giá trị image_path gốc -> image_path dùng được ngay
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


def description(rep: dict, slug_note: str) -> str:
    s, st = rep["source"], rep["status"]
    return f"""# PlantVillageVQA — Vietnamese subset (silver-standard)

Vietnamese translation of a **representative 12.5% subset** of
[PlantVillageVQA](https://huggingface.co/datasets/{s['repo_id']}) (Sakib et al., arXiv:2508.17117,
CC BY 4.0), built for the DSP391 course project (FPT University). Source revision `{s['revision']}`.

## Contents
- `PlantVillageVQA_vi.csv` / `PlantVillageVQA_vi.json` — **same columns and JSON structure as the original**:
  `image_id, question_type, question, answer, image_path, split`. `question`/`answer` are Vietnamese;
  `image_id`, `question_type`, `image_path`, `split` are unchanged. Yes/No answers are `Có`/`Không`.
  {rep['final_rows_trainable']:,} QA rows, {rep['subset']['pairs']:,} unique QA pairs.
- `images/<split>/<file>` — the images used by the subset, placed exactly at the original `image_path`.
- `PlantVillageVQA_vi_en_alignment.csv` — EN↔VI alignment with `qa_id` (= `pvqa_<source row>`), `pair_id`,
  `answer_label` (original English answer), validation status, judge errors and repair log.
- `quality_report.md` — sampling, distributions, validation results and limitations.

## How it was built (fully automatic, no human in the loop)
1. Proportional stratified random sampling by `split × question_type` (12.5%, seed 42).
2. Context-aware EN→VI translation with Claude Sonnet (fixed glossary, one shared Vietnamese question per
   English question, Yes/No polarity rules), plus rule-based checks.
3. Independent LLM evaluation (OpenAI Codex `gpt-6-luna`, MQM-style errors) and one-shot repair.

Status: PASS {st['pairs'].get('PASS', 0):,} pairs / {st['rows'].get('PASS', 0):,} rows;
PASS_AFTER_REPAIR {st['pairs'].get('PASS_AFTER_REPAIR', 0):,} pairs / {st['rows'].get('PASS_AFTER_REPAIR', 0):,} rows;
UNRESOLVED {st['pairs'].get('UNRESOLVED', 0)}. English questions with more than one Vietnamese translation:
{st['questions_with_multiple_question_vi']}.

## Limitations
Labels are **automatically validated silver-standard**, not human-verified; a single LLM judge is the only
semantic check and it is not calibrated against human raters. The source is template-generated and
inherits PlantVillage class imbalance. See `quality_report.md`.

## License and attribution
CC BY 4.0, inherited from PlantVillageVQA. Please cite the original dataset and paper (arXiv:2508.17117)
and the PlantVillage image corpus.{slug_note}
"""


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
    vi = pd.read_csv(final / "PlantVillageVQA_vi.csv")
    chk = extract_images(ROOT / args.zip, vi.image_path, out)
    unresolved = [p for p in vi.image_path.unique() if not (out / p).is_file()]
    on_disk = sum(1 for _ in (out / "images").rglob("*") if _.is_file())
    chk.update({"image_paths_unresolved": len(unresolved), "image_files_on_disk": on_disk})
    rep = json.loads((final / "quality_report.json").read_text())
    import subprocess
    user = subprocess.run(["kaggle", "config", "view"], capture_output=True, text=True).stdout
    owner = next((l.split(":", 1)[1].strip() for l in user.splitlines() if "username" in l), "USERNAME")
    meta = {"title": args.title, "id": f"{owner}/{args.slug}", "licenses": [{"name": "CC-BY-4.0"}],
            "subtitle": "Vietnamese VQA for plant pathology: 24k QA rows + images, LLM-validated",
            "description": description(rep, ""),
            "keywords": ["agriculture", "plants", "image", "nlp", "multimodal"]}
    (out / "dataset-metadata.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    size = sum(p.stat().st_size for p in out.rglob("*") if p.is_file())
    print(json.dumps({**chk, "missing": len(chk["missing"]), "package_bytes": size, "id": meta["id"]},
                     ensure_ascii=False))
    ok = not chk["missing"] and not unresolved and on_disk == chk["images_needed"]
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

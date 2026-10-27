"""Step 1.1 — Inspect the source dataset before sampling.

Records: HF commit sha, file list + sizes, the QA table's schema, actual split values,
row / image counts, question_type list, unique QA pairs, and differences vs. the paper.
Downloads ONLY tabular metadata files, never images.

Usage:  python -m pvvqa.step1_inspect [--qa-file PATH_IN_REPO] [--local FILE]
  --local lets you inspect an already-downloaded table (no network).
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from .common import (ROOT, TABULAR_EXT, detect_columns, image_ref, load_config,
                     read_table, write_json)

PAPER = {  # PlantVillageVQA arXiv:2508.17117 v1 / HF README
    "qa_rows": 193_609,
    "images": 55_448,
    "splits_paper": ["train", "test"],
    "splits_readme": ["train", "val", "test"],
}
IMAGE_EXT = (".jpg", ".jpeg", ".png", ".bmp", ".webp")


def hf_listing(repo_id: str, revision: str | None):
    from huggingface_hub import HfApi
    info = HfApi().dataset_info(repo_id, revision=revision, files_metadata=True)
    files = [{"path": s.rfilename, "size": s.size} for s in info.siblings]
    return info.sha, files


def zip_extract_tabular(repo_id: str, sha: str, zip_path: str, raw_dir: Path):
    import zipfile
    from huggingface_hub import HfFileSystem
    fs = HfFileSystem()
    with fs.open(f"datasets/{repo_id}@{sha}/{zip_path}", "rb", block_size=1 << 20) as f:
        z = zipfile.ZipFile(f)
        members = [i.filename for i in z.infolist() if not i.is_dir()]
        tab = [m for m in members if m.lower().endswith(TABULAR_EXT)]
        for m in tab:
            z.extract(m, raw_dir)
    return members, tab


def pick_qa_file(files: list[dict]) -> str:
    tab = [f for f in files if f["path"].lower().endswith(TABULAR_EXT)]
    if not tab:
        raise SystemExit("No tabular file in repo; set dataset.qa_file in config.")
    # Prefer names mentioning qa/question, then the largest.
    tab.sort(key=lambda f: (("qa" in f["path"].lower() or "question" in f["path"].lower()),
                            f["size"] or 0), reverse=True)
    return tab[0]["path"]


def profile(df: pd.DataFrame, cols: dict) -> dict:
    rep: dict = {"n_rows": int(len(df)), "columns": {}}
    for c in df.columns:
        s = df[c]
        sample = s.iloc[0] if len(s) else None
        if isinstance(sample, dict) and "bytes" in sample:
            sample = {"path": sample.get("path"), "bytes": "<binary>"}
        rep["columns"][c] = {"dtype": str(s.dtype), "n_null": int(s.isna().sum()),
                             "example": str(sample)[:200]}
    rep["detected_columns"] = cols
    missing = [k for k in ("split", "question_type", "question", "answer", "image") if not cols[k]]
    rep["missing_logical_columns"] = missing
    if cols["split"]:
        rep["split_counts"] = df[cols["split"]].value_counts().sort_index().to_dict()
    if cols["question_type"]:
        rep["question_type_counts"] = df[cols["question_type"]].value_counts().to_dict()
    if cols["split"] and cols["question_type"]:
        ct = pd.crosstab(df[cols["split"]], df[cols["question_type"]])
        rep["split_x_question_type"] = {s: {q: int(v) for q, v in row.items()}
                                        for s, row in ct.iterrows()}
        rep["n_strata_nonempty"] = int((ct > 0).sum().sum())
    if cols["image"]:
        imgs = df[cols["image"]].map(image_ref)
        rep["n_unique_images"] = int(imgs.nunique())
        rep["n_null_image"] = int(imgs.isna().sum())
        if cols["split"]:
            per = df.assign(_img=imgs).groupby("_img")[cols["split"]].nunique()
            rep["images_in_multiple_splits"] = int((per > 1).sum())
    if cols["id"]:
        rep["id_unique"] = bool(df[cols["id"]].is_unique)
    keys = [cols[k] for k in ("question_type", "question", "answer") if cols[k]]
    if len(keys) == 3:
        pairs = df.groupby(keys).size()
        rep["n_unique_qa_pairs"] = int(len(pairs))
        rep["n_unique_questions"] = int(df.groupby(keys[:2]).ngroups)
        rep["top10_pairs_row_share"] = round(float(pairs.nlargest(10).sum() / len(df)), 4)
    dup_cols = [c for c in df.columns if df[c].map(lambda v: isinstance(v, (dict, list))).any()]
    hashable = df.drop(columns=dup_cols)
    rep["n_exact_duplicate_rows"] = int(hashable.duplicated().sum())
    return rep


def compare_with_paper(rep: dict, n_image_files: int | None) -> list[str]:
    notes = []
    if rep["n_rows"] != PAPER["qa_rows"]:
        notes.append(f"QA rows {rep['n_rows']:,} != paper {PAPER['qa_rows']:,}")
    if rep.get("n_unique_images") is not None and rep["n_unique_images"] != PAPER["images"]:
        notes.append(f"unique images in QA table {rep['n_unique_images']:,} != paper {PAPER['images']:,}")
    if n_image_files is not None and n_image_files != PAPER["images"]:
        notes.append(f"image files in repo {n_image_files:,} != paper {PAPER['images']:,}")
    if "split_counts" in rep:
        actual = sorted(map(str, rep["split_counts"]))
        notes.append(f"actual split values: {actual} (paper: {PAPER['splits_paper']}, "
                     f"README: {PAPER['splits_readme']})")
    return notes or ["no differences found"]


def extra_consistency(df: pd.DataFrame, cols: dict, raw_dir: Path, result: dict) -> list[str]:
    """Cross-checks between the shipped files: CSV vs JSON copy, image paths vs archive."""
    notes = []
    jsons = [m for m in result.get("archive_tabular_members", []) if m.lower().endswith(".json")]
    if jsons and str(result["qa_file"]).lower().endswith(".csv"):
        import json
        obj = json.loads((raw_dir / jsons[0]).read_text(encoding="utf-8"))
        rows = [{"image_id": k, "image_path": v.get("image_path"), "split": v.get("split"), **q}
                for k, v in obj.items() for q in v.get("questions", [])]
        jd = pd.DataFrame(rows)
        key = [c for c in jd.columns if c in df.columns]
        m = df[key].merge(jd[key], on=key, how="outer", indicator=True)["_merge"].value_counts()
        same = int(m.get("left_only", 0)) == 0 and int(m.get("right_only", 0)) == 0
        result["csv_vs_json"] = {k: int(v) for k, v in m.items()}
        notes.append(f"CSV vs JSON copy ({jsons[0]}): {'identical rows' if same else 'DIFFER'} "
                     f"{result['csv_vs_json']}")
    img_list = raw_dir / "image_files.txt"
    if cols["image"] and img_list.exists():
        files = img_list.read_text(encoding="utf-8").splitlines()
        names = {f.rsplit("/", 1)[-1] for f in files}
        refs = df[cols["image"]].map(image_ref).dropna()
        exact = refs.isin(set(files)).mean()
        by_name = refs.map(lambda p: p.rsplit("/", 1)[-1] in names).mean()
        unused = len(names - set(refs.map(lambda p: p.rsplit("/", 1)[-1])))
        result["image_path_resolution"] = {"exact_path_match": round(float(exact), 4),
                                           "file_name_match": round(float(by_name), 4),
                                           "archive_images_without_qa": unused}
        notes.append(f"image_path resolves by exact path {exact:.2%}, by file name {by_name:.2%} "
                     f"(QA table uses images/<split>/<file>; archive example: {files[0]!r})")
        notes.append(f"{unused:,} archive images have no QA row")
    return notes


def to_markdown(r: dict) -> str:
    p = r["profile"]
    L = ["# Step 1.1 — Source report", "",
         f"- Repo: `{r['repo_id']}`  revision (commit sha): `{r['revision_sha']}`",
         f"- QA file: `{r['qa_file']}`", f"- QA rows: {p['n_rows']:,}",
         f"- Unique images (QA table): {p.get('n_unique_images', 'n/a')}",
         f"- Image files in repo: {r.get('n_image_files_in_repo', 'n/a')}",
         f"- Unique QA pairs: {p.get('n_unique_qa_pairs', 'n/a')}; unique questions: "
         f"{p.get('n_unique_questions', 'n/a')}; top-10 pairs cover "
         f"{p.get('top10_pairs_row_share', 'n/a')} of rows",
         f"- Non-empty strata (split × question_type): {p.get('n_strata_nonempty', 'n/a')}",
         f"- Images appearing in >1 split: {p.get('images_in_multiple_splits', 'n/a')}",
         "", "## Detected columns", ""]
    L += [f"- {k}: `{v}`" for k, v in p["detected_columns"].items()]
    L += ["", "## Schema", "", "| column | dtype | nulls | example |", "|---|---|---|---|"]
    for c, d in p["columns"].items():
        ex = d["example"].replace("|", "\\|").replace("\n", " ")[:80]
        L.append(f"| {c} | {d['dtype']} | {d['n_null']} | {ex} |")
    if "split_x_question_type" in p:
        qts = sorted({q for row in p["split_x_question_type"].values() for q in row})
        L += ["", "## split × question_type (rows)", "",
              "| split | " + " | ".join(qts) + " | total |", "|---" * (len(qts) + 2) + "|"]
        for s, row in p["split_x_question_type"].items():
            L.append(f"| {s} | " + " | ".join(str(row.get(q, 0)) for q in qts)
                     + f" | {sum(row.values())} |")
    L += ["", "## Differences vs paper / README", ""] + [f"- {n}" for n in r["vs_paper"]]
    return "\n".join(L) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--qa-file")
    ap.add_argument("--local", help="inspect a local table instead of downloading")
    a = ap.parse_args(argv)
    cfg = load_config()
    ds = cfg["dataset"]
    out_dir = ROOT / cfg["paths"]["step1_dir"]
    raw_dir = ROOT / cfg["paths"]["raw_dir"]
    result: dict = {"repo_id": ds["repo_id"]}

    n_img_files = None
    if a.local:
        local, result["revision_sha"], result["qa_file"] = Path(a.local), "local", a.local
    else:
        sha, files = hf_listing(ds["repo_id"], ds.get("revision"))
        result["revision_sha"] = sha
        result["repo_files"] = files
        result["repo_files_total_bytes"] = sum(f["size"] or 0 for f in files)
        raw_dir.mkdir(parents=True, exist_ok=True)
        zips = [f["path"] for f in files if f["path"].lower().endswith(".zip")]
        if zips and not any(f["path"].lower().endswith(TABULAR_EXT) for f in files):
            # Dataset ships as one archive: read its directory via HTTP range requests and
            # extract only the tabular members (images are NOT downloaded).
            members, extracted = zip_extract_tabular(ds["repo_id"], sha, zips[0], raw_dir)
            result["archive"] = zips[0]
            result["archive_tabular_members"] = extracted
            imgs = [m for m in members if m.lower().endswith(IMAGE_EXT)]
            qa_member = a.qa_file or ds.get("qa_file") or pick_qa_file(
                [{"path": m, "size": 0} for m in extracted if m.lower().endswith(".csv")]
                or [{"path": m, "size": 0} for m in extracted])
            result["qa_file"] = qa_member
            local = raw_dir / qa_member
        else:
            from huggingface_hub import hf_hub_download
            imgs = [f["path"] for f in files if f["path"].lower().endswith(IMAGE_EXT)]
            qa_file = a.qa_file or ds.get("qa_file") or pick_qa_file(files)
            result["qa_file"] = qa_file
            local = Path(hf_hub_download(ds["repo_id"], qa_file, repo_type="dataset",
                                         revision=sha, local_dir=raw_dir))
        n_img_files = len(imgs)
        result["n_image_files_in_repo"] = n_img_files
        (raw_dir / "image_files.txt").write_text("\n".join(imgs), encoding="utf-8")

    df = read_table(local)
    cols = detect_columns(df, cfg.get("columns"))
    result["profile"] = profile(df, cols)
    result["vs_paper"] = compare_with_paper(result["profile"], n_img_files)
    result["vs_paper"] += extra_consistency(df, cols, raw_dir, result)
    write_json(result, out_dir / "source_report.json")
    (out_dir / "source_report.md").write_text(to_markdown(result), encoding="utf-8")
    print(to_markdown(result))


if __name__ == "__main__":
    main()

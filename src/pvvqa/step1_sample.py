"""Step 1.2–1.3 — Proportional stratified random sampling + acceptance checks.

Strata: split × question_type. Fraction 12.5%, seed 42. Quotas by largest remainder,
at least 1 row per non-empty stratum, total fixed at round(N * fraction).
Within each stratum: simple random sampling without replacement (rows ranked by a
seeded uniform key drawn once per source row, in source-file order).

Usage:  python -m pvvqa.step1_sample [--local FILE]
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from .common import (ROOT, detect_columns, ids_digest, image_ref, load_config,
                     read_table, write_json)


def allocate(sizes: pd.Series, fraction: float, min_per: int = 1) -> pd.Series:
    """Largest-remainder proportional allocation with a per-stratum minimum.

    sizes: index = stratum key (sorted), values = N_h > 0.
    Returns n_h with sum == round(N * fraction) (unless the minimum forces more).
    """
    sizes = sizes.sort_index()
    N = int(sizes.sum())
    n = int(round(N * fraction))
    exact = sizes * n / N
    q = np.floor(exact).astype(int)
    rem = exact - q
    q = q.clip(lower=np.minimum(min_per, sizes))
    diff = n - int(q.sum())
    # stable tie-break by stratum key order
    order_add = rem.sort_values(ascending=False, kind="mergesort").index
    order_sub = rem.sort_values(ascending=True, kind="mergesort").index
    i = 0
    while diff > 0:
        k = order_add[i % len(order_add)]
        if q[k] < sizes[k]:
            q[k] += 1
            diff -= 1
        i += 1
    i = 0
    guard = 0
    while diff < 0 and guard < 10 * len(q):
        k = order_sub[i % len(order_sub)]
        if q[k] > min_per:
            q[k] -= 1
            diff += 1
        i += 1
        guard += 1
    return q.astype(int)


def prepare(df: pd.DataFrame, cols: dict) -> pd.DataFrame:
    df = df.copy()
    df.insert(0, "source_row", np.arange(len(df)))
    if cols["id"]:
        df["qa_id"] = df[cols["id"]].astype(str)
    else:
        df["qa_id"] = [f"pvqa_{i:06d}" for i in range(len(df))]
    if cols["image"]:
        df["image_path"] = df[cols["image"]].map(image_ref)
        if df[cols["image"]].map(lambda v: isinstance(v, dict)).any():
            df = df.drop(columns=[cols["image"]])  # drop embedded bytes, keep path
    df["split"] = df[cols["split"]].astype(str)
    df["question_type"] = df[cols["question_type"]].astype(str)
    return df


def sample(df: pd.DataFrame, fraction: float, seed: int, min_per: int):
    rng = np.random.default_rng(seed)
    df = df.assign(_u=rng.random(len(df)))
    df["perm_rank"] = (df.groupby(["split", "question_type"])["_u"]
                       .rank(method="first").astype(int))
    sizes = df.groupby(["split", "question_type"]).size()
    quotas = allocate(sizes, fraction, min_per)
    qmap = df.set_index(["split", "question_type"]).index.map(quotas.to_dict())
    sub = df[df["perm_rank"].to_numpy() <= np.asarray(qmap)].drop(columns="_u")
    sub = sub.sort_values("source_row").reset_index(drop=True)
    return sub, sizes, quotas


def strata_table(sizes: pd.Series, quotas: pd.Series, fraction: float) -> pd.DataFrame:
    t = pd.DataFrame({"N_h": sizes, "n_h": quotas})
    t["share_source_%"] = 100 * t["N_h"] / t["N_h"].sum()
    t["share_subset_%"] = 100 * t["n_h"] / t["n_h"].sum()
    t["diff_pp"] = t["share_subset_%"] - t["share_source_%"]
    t["exact_quota"] = t["N_h"] * fraction
    return t.reset_index()


def acceptance(raw: pd.DataFrame, src: pd.DataFrame, sub: pd.DataFrame, table: pd.DataFrame, fraction: float,
               min_per: int, image_files: set[str] | None, rerun_digest: str) -> dict:
    checks = {}
    n_target = int(round(len(src) * fraction))
    checks["total_matches_target"] = {"ok": len(sub) == n_target or bool((table["n_h"] == min_per).any()),
                                      "n_subset": len(sub), "n_target": n_target}
    dev = (table["n_h"] - table["exact_quota"]).abs()
    forced = table["n_h"] == min_per
    checks["quota_within_rounding"] = {"ok": bool(((dev < 1) | forced).all()),
                                       "max_abs_dev_rows": round(float(dev.max()), 3),
                                       "n_strata_forced_to_min": int((forced & (table["exact_quota"] < min_per)).sum())}
    checks["max_share_diff_pp"] = round(float(table["diff_pp"].abs().max()), 4)
    checks["every_nonempty_stratum_present"] = {"ok": bool((table["n_h"] >= 1).all())}
    checks["no_duplicate_qa_id"] = {"ok": bool(sub["qa_id"].is_unique)}
    # original columns unchanged: compare against source rows
    s = raw.iloc[sub["source_row"].to_numpy()]
    common = [c for c in raw.columns if c in sub.columns]
    same = all(s[c].reset_index(drop=True).equals(sub[c].reset_index(drop=True)) for c in common
               if not sub[c].map(lambda v: isinstance(v, (dict, list, np.ndarray))).any())
    checks["original_columns_unchanged"] = {"ok": bool(same)}
    if image_files is not None and "image_path" in sub:
        # Match by file name: the QA table says images/<split>/<file> while the archive
        # stores a flat Images/<file> folder (see source_report).
        names = {f.rsplit("/", 1)[-1] for f in image_files}
        missing = sorted({p for p in sub["image_path"].dropna() if p.rsplit("/", 1)[-1] not in names})
        checks["image_path_exists_in_repo"] = {"ok": not missing, "n_missing": len(missing),
                                               "examples": missing[:10]}
    else:
        checks["image_path_exists_in_repo"] = {"ok": None, "note": "skipped: no repo image list"}
    checks["reproducible_seed_rerun"] = {"ok": rerun_digest == ids_digest(sub["qa_id"]),
                                         "qa_id_sha256": ids_digest(sub["qa_id"])}
    checks["all_passed"] = all(v.get("ok") in (True, None) for v in checks.values()
                               if isinstance(v, dict))
    return checks


def to_markdown(meta: dict, table: pd.DataFrame, checks: dict) -> str:
    L = ["# Step 1.2–1.3 — Sampling report", "",
         f"- Method: proportional stratified random sampling; strata = split × question_type",
         f"- Fraction {meta['fraction']}, seed {meta['seed']}, min {meta['min_per']}/stratum, "
         "largest-remainder rounding, no replacement",
         f"- Source rows: {meta['N']:,} → subset rows: {meta['n']:,}; strata: {meta['H']}",
         f"- Source revision: `{meta.get('revision_sha')}`",
         f"- Unique images in subset: {meta.get('n_images_subset')}", "",
         "## Acceptance checks", ""]
    for k, v in checks.items():
        if isinstance(v, dict):
            mark = {True: "PASS", False: "FAIL", None: "SKIP"}[v.get("ok")]
            extra = {kk: vv for kk, vv in v.items() if kk != "ok"}
            L.append(f"- **{mark}** {k} {extra if extra else ''}")
        elif k != "all_passed":
            L.append(f"- {k}: {v}")
    L.append(f"- **ALL PASSED: {checks['all_passed']}**")
    L += ["", "## Strata", "", "| split | question_type | N_h | n_h | source % | subset % | diff pp |",
          "|---|---|---|---|---|---|---|"]
    for _, r in table.iterrows():
        L.append(f"| {r['split']} | {r['question_type']} | {r['N_h']} | {r['n_h']} | "
                 f"{r['share_source_%']:.3f} | {r['share_subset_%']:.3f} | {r['diff_pp']:+.3f} |")
    return "\n".join(L) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--local", help="QA table path (default: file recorded by step1_inspect)")
    a = ap.parse_args(argv)
    cfg = load_config()
    sp = cfg["sampling"]
    out_dir = ROOT / cfg["paths"]["step1_dir"]
    raw_dir = ROOT / cfg["paths"]["raw_dir"]
    src_rep_path = out_dir / "source_report.json"
    src_rep = pd.read_json(src_rep_path, typ="series") if src_rep_path.exists() else {}
    path = Path(a.local) if a.local else raw_dir / src_rep["qa_file"]

    raw = read_table(path)
    cols = detect_columns(raw, cfg.get("columns"))
    for k in ("split", "question_type"):
        if not cols[k]:
            raise SystemExit(f"Column for {k!r} not found; set it in config/phase1.yaml")
    src = prepare(raw, cols)

    sub, sizes, quotas = sample(src, sp["fraction"], sp["seed"], sp["min_per_stratum"])
    rerun, _, _ = sample(src, sp["fraction"], sp["seed"], sp["min_per_stratum"])
    table = strata_table(sizes, quotas, sp["fraction"])

    img_list = raw_dir / "image_files.txt"
    image_files = None
    if img_list.exists():
        image_files = set(img_list.read_text(encoding="utf-8").splitlines())
    checks = acceptance(raw, src, sub, table, sp["fraction"], sp["min_per_stratum"],
                        image_files, ids_digest(rerun["qa_id"]))

    meta = {"fraction": sp["fraction"], "seed": sp["seed"], "min_per": sp["min_per_stratum"],
            "N": len(src), "n": len(sub), "H": len(table),
            "revision_sha": src_rep.get("revision_sha") if len(src_rep) else None,
            "detected_columns": cols,
            "n_images_subset": int(sub["image_path"].nunique()) if "image_path" in sub else None}
    out_dir.mkdir(parents=True, exist_ok=True)
    sub.to_parquet(out_dir / "subset_en.parquet", index=False)
    sub[["qa_id", "source_row", "split", "question_type", "perm_rank"]].to_csv(
        out_dir / "subset_manifest.csv", index=False)
    table.to_csv(out_dir / "strata.csv", index=False)
    write_json({"meta": meta, "checks": checks}, out_dir / "sampling_report.json")
    (out_dir / "sampling_report.md").write_text(to_markdown(meta, table, checks), encoding="utf-8")
    print(to_markdown(meta, table, checks))
    if not checks["all_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

"""Shared helpers: config loading, QA table loading, column detection."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[2]

# Candidate names for each logical column, in priority order (lower-cased match).
COLUMN_CANDIDATES = {
    "id": ["qa_id", "id", "question_id", "qid", "uid"],
    "split": ["split", "subset", "partition", "set"],
    "question_type": ["question_type", "qtype", "type", "question_category", "category"],
    "question": ["question", "question_en", "q"],
    "answer": ["answer", "answer_en", "a"],
    "image": ["image_path", "image", "img_path", "image_file", "file_name", "filename", "img"],
}

TABULAR_EXT = (".csv", ".tsv", ".json", ".jsonl", ".parquet")


def load_config(path: str | Path = ROOT / "config" / "phase1.yaml") -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def read_table(path: str | Path) -> pd.DataFrame:
    p = str(path).lower()
    if p.endswith(".parquet"):
        return pd.read_parquet(path)
    if p.endswith(".csv"):
        return pd.read_csv(path, keep_default_na=False)
    if p.endswith(".tsv"):
        return pd.read_csv(path, sep="\t", keep_default_na=False)
    if p.endswith(".jsonl"):
        return pd.read_json(path, lines=True)
    if p.endswith(".json"):
        with open(path, encoding="utf-8") as f:
            obj = json.load(f)
        if isinstance(obj, dict):  # e.g. {"data": [...]} or {"train": [...], "test": [...]}
            lists = {k: v for k, v in obj.items() if isinstance(v, list)}
            if len(lists) == 1:
                return pd.DataFrame(next(iter(lists.values())))
            frames = []
            for k, v in lists.items():
                df = pd.DataFrame(v)
                if "split" not in df.columns:
                    df["split"] = k
                frames.append(df)
            return pd.concat(frames, ignore_index=True)
        return pd.DataFrame(obj)
    raise ValueError(f"Unsupported table format: {path}")


def detect_columns(df: pd.DataFrame, overrides: dict | None = None) -> dict:
    """Map logical names -> actual column names. Config overrides win."""
    overrides = overrides or {}
    lower = {c.lower(): c for c in df.columns}
    out = {}
    for logical, cands in COLUMN_CANDIDATES.items():
        if overrides.get(logical):
            if overrides[logical] not in df.columns:
                raise KeyError(f"Configured column {overrides[logical]!r} not in table")
            out[logical] = overrides[logical]
            continue
        out[logical] = next((lower[c] for c in cands if c in lower), None)
    return out


def image_ref(value) -> str | None:
    """Image column may be a path string or an HF Image struct {'path','bytes'}."""
    if isinstance(value, dict):
        return value.get("path")
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    return str(value)


def ids_digest(ids) -> str:
    h = hashlib.sha256()
    for i in ids:
        h.update(str(i).encode("utf-8"))
        h.update(b"\n")
    return h.hexdigest()


def write_json(obj, path: str | Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, default=str)

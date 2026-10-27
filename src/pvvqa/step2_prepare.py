"""Step 2.1 — gom cặp QA duy nhất, bảng câu hỏi, chia batch theo câu hỏi.

Đầu vào : outputs/step1/subset_en.parquet (đã đóng băng)
Đầu ra  : outputs/step2/
  pairs.parquet        pair_id, question_key, question_type, question_en, answer_en,
                       is_yes_no, answer_label, n_rows
  pair_qa_map.parquet  pair_id, qa_id   (mỗi dòng QA thuộc đúng một cặp)
  questions.csv        question_key, question_type, question_en, n_pairs, n_rows
  batches.jsonl        {"batch_id", "questions":[{question_key, question_type, question_en,
                        pairs:[{pair_id, answer_en, is_yes_no}]}]}
  prepare_report.json  số liệu
Chạy: PYTHONPATH=src python -m pvvqa.step2_prepare
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

from pvvqa.common import ROOT, load_config

YES_NO = {"Yes", "No"}
SEP = "\x1f"


def _h(*parts: str, n: int = 16) -> str:
    return hashlib.sha256(SEP.join(parts).encode("utf-8")).hexdigest()[:n]


def pair_id(question_type: str, question: str, answer: str) -> str:
    return "p_" + _h(question_type, question, answer)


def question_key(question_type: str, question: str) -> str:
    return "q_" + _h(question_type, question, n=12)


def build_pairs(sub: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    df = sub[["qa_id", "question_type", "question", "answer"]].copy()
    df["pair_id"] = [pair_id(t, q, a) for t, q, a in
                     zip(df.question_type, df.question, df.answer)]
    df["question_key"] = [question_key(t, q) for t, q in zip(df.question_type, df.question)]
    pairs = (df.groupby("pair_id", sort=False)
               .agg(question_key=("question_key", "first"),
                    question_type=("question_type", "first"),
                    question_en=("question", "first"),
                    answer_en=("answer", "first"),
                    n_rows=("qa_id", "size"))
               .reset_index())
    pairs["is_yes_no"] = pairs["answer_en"].isin(YES_NO)
    # answer_label: sao chép nguyên văn câu trả lời gốc, không bao giờ qua dịch.
    pairs["answer_label"] = pairs["answer_en"]
    pairs = pairs.sort_values(["question_type", "question_en", "answer_en"]).reset_index(drop=True)
    qmap = df[["pair_id", "qa_id"]].sort_values("qa_id").reset_index(drop=True)
    questions = (pairs.groupby(["question_key", "question_type", "question_en"], sort=False)
                      .agg(n_pairs=("pair_id", "size"), n_rows=("n_rows", "sum"))
                      .reset_index())
    return pairs, qmap, questions


def make_batches(pairs: pd.DataFrame, max_pairs: int = 40) -> list[dict]:
    """Đóng gói nguyên nhóm câu hỏi vào batch (một câu hỏi không bao giờ bị tách),
    tối đa max_pairs cặp/batch; nhóm lớn hơn max_pairs đứng riêng một batch."""
    batches, cur, cur_n = [], [], 0
    for (qk, qt, qen), g in pairs.groupby(["question_key", "question_type", "question_en"],
                                          sort=False):
        item = {"question_key": qk, "question_type": qt, "question_en": qen,
                "pairs": [{"pair_id": r.pair_id, "answer_en": r.answer_en,
                           "is_yes_no": bool(r.is_yes_no)} for r in g.itertuples()]}
        if cur and cur_n + len(g) > max_pairs:
            batches.append(cur)
            cur, cur_n = [], 0
        cur.append(item)
        cur_n += len(g)
    if cur:
        batches.append(cur)
    return [{"batch_id": f"b{i:04d}", "questions": b} for i, b in enumerate(batches)]


def main() -> None:
    cfg = load_config()
    s2 = cfg.get("step2", {})
    out = ROOT / s2.get("out_dir", "outputs/step2")
    out.mkdir(parents=True, exist_ok=True)
    sub = pd.read_parquet(ROOT / cfg["paths"]["step1_dir"] / "subset_en.parquet")
    pairs, qmap, questions = build_pairs(sub)
    batches = make_batches(pairs, s2.get("max_pairs_per_batch", 40))

    assert qmap.qa_id.is_unique and len(qmap) == len(sub)
    assert pairs.n_rows.sum() == len(sub)
    assert sum(len(q["pairs"]) for b in batches for q in b["questions"]) == len(pairs)

    pairs.to_parquet(out / "pairs.parquet", index=False)
    qmap.to_parquet(out / "pair_qa_map.parquet", index=False)
    questions.to_csv(out / "questions.csv", index=False)
    with open(out / "batches.jsonl", "w", encoding="utf-8") as f:
        for b in batches:
            f.write(json.dumps(b, ensure_ascii=False) + "\n")
    report = {
        "rows": int(len(sub)), "pairs": int(len(pairs)), "questions": int(len(questions)),
        "yes_no_pairs": int(pairs.is_yes_no.sum()), "open_pairs": int((~pairs.is_yes_no).sum()),
        "max_rows_per_pair": int(pairs.n_rows.max()),
        "max_pairs_per_question": int(questions.n_pairs.max()),
        "batches": len(batches),
        "pairs_per_batch_max": max(sum(len(q["pairs"]) for q in b["questions"]) for b in batches),
        "pairs_by_type": pairs.groupby("question_type").size().to_dict(),
    }
    (out / "prepare_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

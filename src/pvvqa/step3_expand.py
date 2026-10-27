"""Step 3.4 — viết đầy đủ tên tiếng Việt thay cho viết tắt HLB / TYLCV / ToMV (yêu cầu người dùng 2026-10-27).

Thay thế bằng luật cố định (không gọi model dịch) trên bản dịch cuối của Step 3, rồi kiểm tra luật và
Codex CHẤM LẠI các cặp bị đổi. Cặp không đạt khi chấm lại -> UNRESOLVED (không sửa thêm).
  PYTHONPATH=src python -m pvvqa.step3_expand
Checkpoint append-only trong runs/step3/:
  expansions.jsonl             {pair_id, question_vi, answer_vi, old_question_vi, old_answer_vi, rule_errors, ...}
  expansion_judgments.jsonl    kết quả chấm lại (cùng định dạng judgments.jsonl)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime

import pandas as pd

from pvvqa.common import ROOT, load_config
from pvvqa.step2_rules import check_question, load_glossary
from pvvqa.step2_translate import append_jsonl, git_commit, now, read_jsonl
from pvvqa.step3_judge import FIELDS, judge_batches, judge_ctx, latest_valid
from pvvqa.step3_repair import resolve, summary

# Thứ tự quan trọng: bỏ viết tắt trong ngoặc sau tên đầy đủ trước, rồi mới thay viết tắt đứng riêng.
EXPAND_RULES = [
    (r"\s*\((TYLCV|ToMV|HLB)\)", ""),
    (r"\(Huanglongbing, HLB\)", "(Huanglongbing)"),
    (r"\bbệnh (nhiễm|do) virus: TYLCV\b", r"bệnh \1 virus xoăn vàng lá cà chua"),
    (r"\bbệnh (nhiễm|do) virus: ToMV\b", r"bệnh \1 virus khảm cà chua"),
    (r"\bbệnh HLB\b", "bệnh vàng lá gân xanh"),
    (r"\bvirus TYLCV\b", "virus xoăn vàng lá cà chua"),
    (r"\bvirus ToMV\b", "virus khảm cà chua"),
    (r"\bTYLCV\b", "virus xoăn vàng lá cà chua"),
    (r"\bToMV\b", "virus khảm cà chua"),
    (r"\bHLB\b", "bệnh vàng lá gân xanh"),
]
ABBR = re.compile(r"\b(HLB|TYLCV|ToMV)\b")


def expand(text: str) -> str:
    for pat, rep in EXPAND_RULES:
        text = re.sub(pat, rep, text)
    return text


def apply_expansions(cfg: dict, res: pd.DataFrame | None = None) -> pd.DataFrame:
    """Kết quả cuối sau Step 3.4: bản dịch đã viết đầy đủ; cặp bị đổi phải qua luật + chấm lại PASS."""
    run_dir = ROOT / cfg["step3"]["run_dir"]
    res = resolve(cfg) if res is None else res
    exp = {}
    for r in read_jsonl(run_dir / "expansions.jsonl"):
        exp[r["pair_id"]] = r
    if not exp:
        return res.assign(expanded=False, expansion_judge=None, pre_expansion_question_vi="",
                          pre_expansion_answer_vi="")
    ej = latest_valid(run_dir / "expansion_judgments.jsonl")
    res = res.copy()
    res["expanded"] = res.pair_id.isin(exp)
    res["expansion_judge"] = res.pair_id.map(lambda p: (ej.get(p) or {}).get("verdict"))
    res["pre_expansion_question_vi"] = res.pair_id.map(lambda p: exp[p]["old_question_vi"] if p in exp else "")
    res["pre_expansion_answer_vi"] = res.pair_id.map(lambda p: exp[p]["old_answer_vi"] if p in exp else "")
    m = res.expanded
    res.loc[m, "question_vi"] = res.loc[m, "pair_id"].map(lambda p: exp[p]["question_vi"])
    res.loc[m, "answer_vi"] = res.loc[m, "pair_id"].map(lambda p: exp[p]["answer_vi"])
    ok = res.pair_id.map(lambda p: p not in exp or (not exp[p]["rule_errors"] and ej.get(p, {}).get("verdict") == "PASS"))
    res.loc[~ok, "status"] = "UNRESOLVED"
    return res


def run(args) -> int:
    cfg = load_config()
    run_dir = ROOT / cfg["step3"]["run_dir"]
    glossary = load_glossary(ROOT / cfg["step2"]["glossary"])
    run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    res = resolve(cfg)
    exp_p = run_dir / "expansions.jsonl"
    done = {r["pair_id"] for r in read_jsonl(exp_p)}
    rows = []
    for qk, g in res.groupby("question_key"):
        new_q = expand(g.question_vi.iloc[0])  # cùng câu hỏi -> cùng question_vi mới
        new_a = {r.pair_id: expand(r.answer_vi) for r in g.itertuples()}
        changed = [r for r in g.itertuples() if new_q != r.question_vi or new_a[r.pair_id] != r.answer_vi]
        if not changed:
            continue
        item_in = {"question_key": qk, "question_en": g.question_en.iloc[0],
                   "pairs": [{"pair_id": r.pair_id, "answer_en": r.answer_en, "is_yes_no": bool(r.is_yes_no)}
                             for r in g.itertuples()]}
        chk = check_question(item_in, {"question_vi": new_q, "pairs": [
            {"pair_id": p, "answer_vi": a} for p, a in new_a.items()]}, glossary)
        for r in changed:
            if r.pair_id in done:
                continue
            errs = chk.get(r.pair_id, []) + (["abbreviation_left"] if ABBR.search(new_q + " " + new_a[r.pair_id]) else [])
            rows.append({"pair_id": r.pair_id, "question_key": qk, "question_vi": new_q,
                         "answer_vi": new_a[r.pair_id], "old_question_vi": r.question_vi,
                         "old_answer_vi": r.answer_vi, "rule_errors": errs, "ts": now(), "run_id": run_id})
    append_jsonl(exp_p, rows)
    exp = {r["pair_id"]: r for r in read_jsonl(exp_p)}
    print(f"[{run_id}] viết đầy đủ: {len(exp)} cặp bị đổi ({len(rows)} mới), "
          f"trượt luật {sum(bool(r['rule_errors']) for r in exp.values())}.")

    ej_p = run_dir / "expansion_judgments.jsonl"
    judged = set(latest_valid(ej_p))
    idx = res.set_index("pair_id")
    size = cfg["step3"].get("max_pairs_per_call", 40)
    items = [{"id": p, **{f: idx.loc[p, f] for f in FIELDS}, "question_vi": e["question_vi"],
              "answer_vi": e["answer_vi"]}
             for p, e in sorted(exp.items(), key=lambda kv: (kv[1]["question_key"], kv[0]))
             if not e["rule_errors"] and p not in judged]
    for k, it in enumerate(items):
        it["batch_id"] = f"expand{k // size}"
    batches = [items[k:k + size] for k in range(0, len(items), size)]
    print(f"[{run_id}] chấm lại: {len(items)} cặp.")
    jres = judge_batches(batches, ej_p, judge_ctx(cfg, args.model, args.reasoning, args.codex_cmd, run_id))
    final = summary(apply_expansions(cfg, res))
    append_jsonl(run_dir / "run_log.jsonl", [{
        "run_id": run_id, "started": now(), "cmd": " ".join(sys.argv), "git_commit": git_commit(),
        "mode": "expand_abbreviations", "pairs_expanded": len(exp), **jres, "final": final, "finished": now()}])
    print(json.dumps(final, ensure_ascii=False))
    if jres["stop_reason"] != "completed":
        print("Dừng sớm. Chạy tiếp bằng: PYTHONPATH=src python -m pvvqa.step3_expand")
        return 3
    return 0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model")
    ap.add_argument("--reasoning")
    ap.add_argument("--codex-cmd", help="ghi đè lệnh codex (dùng cho test)")
    sys.exit(run(ap.parse_args()))


if __name__ == "__main__":
    main()

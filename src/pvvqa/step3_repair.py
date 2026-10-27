"""Step 3.3 — repair đúng một lần (Claude) rồi chấm lại (Codex).

Chạy sau khi đã chấm toàn bộ (`python -m pvvqa.step3_judge`):
  export PYTHONPATH=src
  unset ANTHROPIC_API_KEY OPENAI_API_KEY
  python -m pvvqa.step3_repair             # repair mọi cặp cần sửa, rồi chấm lại
  python -m pvvqa.step3_repair --status

Cặp cần sửa = trượt luật ở Step 2 + verdict NEEDS_REPAIR ở lần chấm đầu.
- Claude dịch lại kèm nhận xét (lỗi luật / lỗi judge) → chuẩn hoá thuật ngữ (2.5) → kiểm tra luật → Codex chấm lại.
- Nếu repair đổi question_vi dùng chung: áp cho mọi cặp cùng câu hỏi; các cặp không cần sửa của
  câu hỏi đó được kiểm tra luật và CHẤM LẠI (không dịch lại).
Trạng thái cuối (resolve): PASS / PASS_AFTER_REPAIR / UNRESOLVED. Không sửa lần thứ hai.

Checkpoint append-only trong runs/step3/:
  repairs.jsonl            mỗi dòng một cặp được sửa {pair_id, question_key, question_vi, answer_vi,
                           old_question_vi, old_answer_vi, feedback, rule_errors, rule_pass, error, ...}
  question_updates.jsonl   câu hỏi bị đổi question_vi {question_key, old/new_question_vi, sibling_rule_errors}
  rejudgments.jsonl        kết quả chấm lại (cùng định dạng judgments.jsonl)
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime

import pandas as pd

from pvvqa.common import ROOT, load_config
from pvvqa.step2_rules import check_question, load_glossary, normalize_terms
from pvvqa.step2_translate import (QuotaStop, append_jsonl, call_claude_retry, git_commit, now,
                                   read_jsonl, render_system_prompt, sha)
from pvvqa.step3_judge import (FIELDS, MAX_CONSEC_FAIL, judge_batches, judge_ctx, latest_valid,
                               load_translations, status as judge_status)


def _latest(path, key="pair_id") -> dict[str, dict]:
    out = {}
    for r in read_jsonl(path):
        out[r[key]] = r
    return out


def feedback_for(df: pd.DataFrame, judged: dict[str, dict]) -> dict[str, list[str]]:
    """pair_id -> nhận xét cho repair. Cặp trượt luật: mã lỗi luật; cặp NEEDS_REPAIR: lỗi của judge."""
    fb = {}
    for r in df.itertuples():
        if r.rule_pass != True:  # noqa: E712 (gồm cả NaN)
            fb[r.pair_id] = [f"rule check failed: {e}" for e in (r.rule_errors or [])] or ["rule check failed"]
        elif r.pair_id in judged and judged[r.pair_id]["verdict"] != "PASS":
            fb[r.pair_id] = [f"{e['severity']}/{e['category']}: {e['explanation']}"
                             for e in judged[r.pair_id]["errors"]]
    return fb


def repair_batches(df: pd.DataFrame, fb: dict[str, list[str]], done: set[str], max_pairs: int) -> list[list[dict]]:
    """Gom cặp cần sửa theo câu hỏi (một câu hỏi không bị tách), đóng batch ≤ max_pairs cặp."""
    todo = df[df.pair_id.isin(set(fb) - done)]
    out, cur, n = [], [], 0
    for qk, g in todo.groupby("question_key", sort=True):
        q = {"question_key": qk, "question_type": g.question_type.iloc[0],
             "question_en": g.question_en.iloc[0], "current_question_vi": g.question_vi.iloc[0],
             "pairs": [{"pair_id": r.pair_id, "answer_en": r.answer_en, "is_yes_no": bool(r.is_yes_no),
                        "current_answer_vi": r.answer_vi, "feedback": fb[r.pair_id]}
                       for r in g.itertuples()]}
        if cur and n + len(q["pairs"]) > max_pairs:
            out.append(cur)
            cur, n = [], 0
        cur.append(q)
        n += len(q["pairs"])
    if cur:
        out.append(cur)
    return out


def run_repair(cfg, df, fb, args, run_id) -> dict:
    s2, s3 = cfg["step2"], cfg["step3"]
    run_dir = ROOT / s3["run_dir"]
    glossary = load_glossary(ROOT / s2["glossary"])
    sys_file = run_dir / "repair_system.md"
    sys_file.write_text(render_system_prompt(ROOT / "prompts" / "translator.md", ROOT / s2["glossary"])
                        + (ROOT / "prompts" / "repair.md").read_text(encoding="utf-8"), encoding="utf-8")
    schema = json.dumps(json.loads((ROOT / "schemas" / "translation.json").read_text()))
    cmd = args.claude_cmd.split() if args.claude_cmd else s2["claude_cmd"]
    rep_p, qu_p = run_dir / "repairs.jsonl", run_dir / "question_updates.jsonl"
    done = {k for k, r in _latest(rep_p).items() if not r.get("error")}
    batches = repair_batches(df, fb, done, s2.get("max_pairs_per_batch", 40))
    by_q = {k: g for k, g in df.groupby("question_key")}
    print(f"[{run_id}] repair: {len(batches)} batch, {sum(len(q['pairs']) for b in batches for q in b)} cặp.")
    n_ok = n_err = consec = 0
    stop = "completed"
    for i, b in enumerate(batches, 1):
        payload = {"questions": b}
        rows, qrows = [], []
        try:
            out, meta = call_claude_retry(cmd, sys_file, schema, payload, s2.get("timeout_s", 600))
            consec = 0
            (run_dir / "raw" / f"repair{i:03d}__{run_id}.json").write_text(
                json.dumps({"input": payload, "output": out, "meta": meta}, ensure_ascii=False, indent=1),
                encoding="utf-8")
            got = {q.get("question_key"): q for q in out.get("questions", [])}
            for q in b:
                qo = got.get(q["question_key"]) or {}
                # bản sửa đi qua cùng bước 2.5 (chuẩn hoá thuật ngữ) như bản dịch lần đầu
                answers = {p.get("pair_id"): normalize_terms((p.get("answer_vi") or "").strip())
                           for p in qo.get("pairs", [])}
                new_q = normalize_terms((qo.get("question_vi") or "").strip())
                if not new_q or any(not answers.get(p["pair_id"]) for p in q["pairs"]):
                    for p in q["pairs"]:  # câu hỏi không trọn vẹn -> thử lại cả câu hỏi
                        rows.append({"pair_id": p["pair_id"], "question_key": q["question_key"], "ts": now(),
                                     "run_id": run_id, "error": "incomplete_output"})
                        n_err += 1
                    continue
                # Kiểm tra luật trên CẢ câu hỏi: cặp được sửa (câu trả lời mới) + cặp khác (câu trả lời cũ).
                g = by_q[q["question_key"]]
                item_in = {"question_key": q["question_key"], "question_en": q["question_en"],
                           "pairs": [{"pair_id": r.pair_id, "answer_en": r.answer_en,
                                      "is_yes_no": bool(r.is_yes_no)} for r in g.itertuples()]}
                item_out = {"question_vi": new_q, "pairs": [
                    {"pair_id": r.pair_id, "answer_vi": answers.get(r.pair_id, r.answer_vi)} for r in g.itertuples()]}
                res = check_question(item_in, item_out, glossary)
                for p in q["pairs"]:
                    errs = res.get(p["pair_id"], [])
                    rows.append({"pair_id": p["pair_id"], "question_key": q["question_key"],
                                 "question_vi": new_q, "answer_vi": answers[p["pair_id"]],
                                 "old_question_vi": q["current_question_vi"],
                                 "old_answer_vi": p["current_answer_vi"], "feedback": p["feedback"],
                                 "rule_errors": errs, "rule_pass": not errs, "ts": now(), "run_id": run_id,
                                 "error": None})
                    n_ok += 1
                if new_q != q["current_question_vi"]:
                    sib = {r.pair_id: res.get(r.pair_id, []) for r in g.itertuples() if r.pair_id not in fb}
                    qrows.append({"question_key": q["question_key"], "old_question_vi": q["current_question_vi"],
                                  "new_question_vi": new_q, "sibling_rule_errors": sib, "ts": now(),
                                  "run_id": run_id})
        except QuotaStop as e:
            stop = f"quota: {e}"
            break
        except (RuntimeError, json.JSONDecodeError, subprocess.TimeoutExpired, OSError) as e:
            consec += 1
            for q in b:
                for p in q["pairs"]:
                    rows.append({"pair_id": p["pair_id"], "question_key": q["question_key"], "ts": now(),
                                 "run_id": run_id, "error": f"{type(e).__name__}: {str(e)[:300]}"})
                    n_err += 1
            if consec >= MAX_CONSEC_FAIL:
                append_jsonl(rep_p, rows)
                stop = f"{MAX_CONSEC_FAIL} lỗi liên tiếp: {str(e)[:200]}"
                break
        append_jsonl(qu_p, qrows)
        append_jsonl(rep_p, rows)  # ghi ngay sau mỗi batch
        print(f"  [{i}/{len(batches)}] repair: ok={n_ok} err={n_err}", flush=True)
    return {"stop_reason": stop, "repaired_ok_this_run": n_ok, "repair_error_this_run": n_err}


def rejudge_items(df: pd.DataFrame, fb: dict, repairs: dict, qupd: dict) -> list[dict]:
    """Mục cần chấm lại: cặp đã sửa và qua luật + cặp khác của câu hỏi bị đổi question_vi (qua luật)."""
    items = []
    for pid, r in repairs.items():
        if r.get("error") is None and r["rule_pass"]:
            src = df.loc[pid]
            items.append({"id": pid, "question_type": src.question_type, "question_en": src.question_en,
                          "answer_en": src.answer_en, "question_vi": r["question_vi"], "answer_vi": r["answer_vi"]})
    for qk, u in qupd.items():
        for pid, errs in u["sibling_rule_errors"].items():
            if not errs:
                src = df.loc[pid]
                items.append({"id": pid, **{f: src[f] for f in FIELDS}, "question_vi": u["new_question_vi"]})
    return items


def resolve(cfg: dict) -> pd.DataFrame:
    """Trạng thái cuối và bản dịch cuối của mọi cặp."""
    run_dir = ROOT / cfg["step3"]["run_dir"]
    df = load_translations(cfg)
    judged = latest_valid(run_dir / "judgments.jsonl")
    fb = feedback_for(df, judged)
    repairs = {k: r for k, r in _latest(run_dir / "repairs.jsonl").items() if not r.get("error")}
    qupd = _latest(run_dir / "question_updates.jsonl", key="question_key")
    rej = latest_valid(run_dir / "rejudgments.jsonl")
    out = []
    for r in df.itertuples():
        q_vi, a_vi = r.question_vi, r.answer_vi
        rec = {"pair_id": r.pair_id, "judge_first": (judged.get(r.pair_id) or {}).get("verdict"),
               "repaired": r.pair_id in repairs, "rejudge": (rej.get(r.pair_id) or {}).get("verdict")}
        if r.pair_id in fb:
            rp = repairs.get(r.pair_id)
            if rp:
                q_vi, a_vi = rp["question_vi"], rp["answer_vi"]
            ok = bool(rp) and rp["rule_pass"] and rec["rejudge"] == "PASS"
            st = "PASS_AFTER_REPAIR" if ok else "UNRESOLVED"
        elif r.question_key in qupd:  # câu hỏi dùng chung bị đổi: cần qua luật + chấm lại
            u = qupd[r.question_key]
            q_vi = u["new_question_vi"]
            ok = not u["sibling_rule_errors"].get(r.pair_id) and rec["rejudge"] == "PASS"
            st = "PASS" if ok else "UNRESOLVED"
        else:
            st = "PASS" if rec["judge_first"] == "PASS" else "UNRESOLVED"  # chưa chấm -> chưa xác nhận
        out.append({**rec, "question_vi": q_vi, "answer_vi": a_vi, "status": st})
    return df.drop(columns=["question_vi", "answer_vi"]).merge(pd.DataFrame(out), on="pair_id")


def summary(res: pd.DataFrame) -> dict:
    by_pair = res.status.value_counts().to_dict()
    by_row = res.groupby("status").n_rows.sum().to_dict()
    multi = res.groupby(["question_type", "question_en"]).question_vi.nunique()
    return {"pairs": by_pair, "rows": {k: int(v) for k, v in by_row.items()},
            "questions_with_multiple_question_vi": int((multi > 1).sum())}


def run(args) -> int:
    cfg = load_config()
    s3 = cfg["step3"]
    run_dir = ROOT / s3["run_dir"]
    df = load_translations(cfg)
    js = judge_status(cfg, df)
    if args.status:
        print(json.dumps({"judge": js, "final": summary(resolve(cfg))}, indent=2, ensure_ascii=False))
        return 0
    if js["pairs_judged"] < js["pairs_to_judge"]:
        print(f"Chưa chấm xong ({js['pairs_judged']}/{js['pairs_to_judge']}). "
              "Chạy trước: PYTHONPATH=src python -m pvvqa.step3_judge")
        return 2
    run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    judged = latest_valid(run_dir / "judgments.jsonl")
    fb = feedback_for(df, judged)
    log = {"run_id": run_id, "started": now(), "cmd": " ".join(sys.argv), "git_commit": git_commit(),
           "config_hash": sha(ROOT / "config" / "phase1.yaml", ROOT / "prompts" / "repair.md",
                              ROOT / "prompts" / "translator.md", ROOT / "prompts" / "judge.md"),
           "mode": "repair", "pairs_to_repair": len(fb)}
    res = run_repair(cfg, df, fb, args, run_id)
    log.update(res)
    if res["stop_reason"] == "completed":
        repairs = {k: r for k, r in _latest(run_dir / "repairs.jsonl").items() if not r.get("error")}
        qupd = _latest(run_dir / "question_updates.jsonl", key="question_key")
        rej_p = run_dir / "rejudgments.jsonl"
        done = set(latest_valid(rej_p))
        items = [it for it in rejudge_items(df.set_index("pair_id"), fb, repairs, qupd) if it["id"] not in done]
        size = s3.get("max_pairs_per_call", 40)
        for k, it in enumerate(items):
            it["batch_id"] = f"rejudge{k // size}"
        batches = [items[k:k + size] for k in range(0, len(items), size)]
        print(f"[{run_id}] chấm lại: {len(items)} cặp.")
        jres = judge_batches(batches, rej_p, judge_ctx(cfg, args.model, args.reasoning, args.codex_cmd, run_id))
        log.update({f"rejudge_{k}": v for k, v in jres.items()})
        log["stop_reason"] = jres["stop_reason"]
    log.update({"finished": now(), "final": summary(resolve(cfg))})
    append_jsonl(run_dir / "run_log.jsonl", [log])
    print(json.dumps(log["final"], ensure_ascii=False))
    if log["stop_reason"] != "completed":
        print("Dừng sớm. Chạy tiếp bằng: PYTHONPATH=src python -m pvvqa.step3_repair")
        return 3
    return 0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--model", help="ghi đè judge_model khi chấm lại")
    ap.add_argument("--reasoning", help="ghi đè judge_reasoning khi chấm lại")
    ap.add_argument("--claude-cmd", help="ghi đè lệnh claude (dùng cho test)")
    ap.add_argument("--codex-cmd", help="ghi đè lệnh codex (dùng cho test)")
    sys.exit(run(ap.parse_args()))


if __name__ == "__main__":
    main()

"""Step 2 — dịch EN→VI bằng Claude (`claude -p`, gói Pro), checkpoint append-only, chạy tiếp được.

Chạy trên Terminal của Mac (nơi đã đăng nhập Claude):
  export PYTHONPATH=src
  unset ANTHROPIC_API_KEY
  python -m pvvqa.step2_translate --pilot 50     # dịch thử ~50 cặp
  python -m pvvqa.step2_translate                # dịch toàn bộ phần còn lại
  python -m pvvqa.step2_translate --status       # xem tiến độ
  python -m pvvqa.step2_translate --recheck      # áp lại luật mới, không gọi model

Kết quả: runs/step2/translations.jsonl — mỗi dòng một cặp:
  {pair_id, question_key, batch_id, question_vi, answer_vi, rule_errors, rule_pass, error, ts, run_id}
  error != null  -> lần sau thử lại; rule_pass=false -> chuyển sang repair ở Step 3.
  Đơn vị ghi là cả câu hỏi: hoặc mọi cặp của câu hỏi được ghi cùng một question_vi, hoặc không.
Raw output mỗi batch: runs/step2/raw/<batch_id>__<run_id>.json
Nhật ký: runs/step2/run_log.jsonl
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from pvvqa.common import ROOT, load_config
from pvvqa.step2_rules import check_question, load_glossary

QUOTA_PAT = re.compile(r"usage limit|rate.?limit|quota|limit reached|too many requests|\b429\b|"
                       r"overloaded|credit balance|out of (usage|credits)|resets? at", re.I)
MAX_CONSEC_FAIL = 3


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha(*paths: Path) -> str:
    h = hashlib.sha256()
    for p in paths:
        h.update(Path(p).read_bytes())
    return h.hexdigest()[:16]


def git_commit() -> str | None:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                              capture_output=True, text=True, timeout=10).stdout.strip() or None
    except Exception:
        return None


def render_system_prompt(prompt_path: Path, glossary_path: Path) -> str:
    import yaml
    g = yaml.safe_load(glossary_path.read_text(encoding="utf-8"))
    lines = [prompt_path.read_text(encoding="utf-8").rstrip(), "", "## Glossary", "", "### Crops"]
    lines += [f"- {e['en']} → {e['vi']}" for e in g["crops"]]
    lines += ["", "### Diseases / pests"] + [f"- {e['en']} → {e['vi']}" for e in g["diseases"]]
    lines += ["", "### Symptom terms (preferred)"] + [f"- {k} → {v}" for k, v in g["terms"].items()]
    lines += ["", "### Keep as written"] + [f"- {k}" for k in g["keep"]]
    return "\n".join(lines) + "\n"


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue  # dòng ghi dở khi bị ngắt: bỏ qua, cặp đó sẽ được thử lại
    return out


def done_pairs(records: list[dict]) -> set[str]:
    """Cặp đã có bản dịch hợp lệ (bản ghi mới nhất không có lỗi hệ thống)."""
    latest = {}
    for r in records:
        latest[r["pair_id"]] = r
    return {pid for pid, r in latest.items() if not r.get("error")}


def append_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())


def extract_json(text: str) -> dict:
    t = text.strip()
    m = re.search(r"```(?:json)?\s*(.*?)```", t, re.S)
    if m:
        t = m.group(1).strip()
    if not t.startswith("{"):
        i, j = t.find("{"), t.rfind("}")
        t = t[i:j + 1] if i >= 0 else t
    return json.loads(t)


class QuotaStop(Exception):
    pass


def call_claude(cmd: list[str], system_prompt_file: Path, schema: str | None, payload: dict,
                timeout: int) -> tuple[dict, dict]:
    """Trả (parsed_output, meta). Ném QuotaStop khi hết quota / rate limit."""
    full = list(cmd) + ["--system-prompt-file", str(system_prompt_file)]
    if schema:
        full += ["--json-schema", schema]
    user_msg = ("Translate this batch following the instructions. Return only the JSON object.\n\n"
                + json.dumps(payload, ensure_ascii=False, indent=1))
    env = {k: v for k, v in os.environ.items() if k not in ("ANTHROPIC_API_KEY",)}
    # cwd rỗng: để claude -p không nạp CLAUDE.md của dự án vào ngữ cảnh dịch.
    with tempfile.TemporaryDirectory() as tmp:
        t0 = time.time()
        proc = subprocess.run(full, input=user_msg, capture_output=True, text=True, cwd=tmp,
                              env=env, timeout=timeout)
    meta = {"returncode": proc.returncode, "elapsed_s": round(time.time() - t0, 1)}
    blob = proc.stdout.strip()
    try:
        wrapper = json.loads(blob) if blob else {}
    except json.JSONDecodeError:
        wrapper = {"result": blob}
    if isinstance(wrapper, dict):
        for k in ("usage", "total_cost_usd", "duration_ms", "num_turns", "session_id", "model"):
            if k in wrapper:
                meta[k] = wrapper[k]
    text_all = " ".join([proc.stderr or "", str(wrapper.get("result", ""))
                         if isinstance(wrapper, dict) else blob])
    is_err = proc.returncode != 0 or (isinstance(wrapper, dict) and wrapper.get("is_error"))
    if is_err:
        meta["error_text"] = text_all.strip()[:500]
        if QUOTA_PAT.search(text_all):
            raise QuotaStop(meta["error_text"])
        raise RuntimeError(meta["error_text"] or f"claude exited {proc.returncode}")
    if isinstance(wrapper, dict) and isinstance(wrapper.get("structured_output"), dict):
        return wrapper["structured_output"], meta
    result = wrapper.get("result", blob) if isinstance(wrapper, dict) else blob
    return extract_json(result), meta


def pending_batches(batches: list[dict], done: set[str]) -> list[dict]:
    out = []
    for b in batches:
        qs = [q for q in b["questions"] if not all(p["pair_id"] in done for p in q["pairs"])]
        if qs:
            out.append({"batch_id": b["batch_id"], "questions": qs})
    return out


def pilot_batches(todo: list[dict], n_target: int, max_q_pairs: int = 12,
                  max_pairs: int = 40) -> list[dict]:
    """Chọn ~n_target cặp rải đều mọi question_type (lần lượt từng câu hỏi, bỏ qua câu hỏi
    quá lớn), giữ nguyên batch_id gốc của mỗi câu hỏi; đóng lại thành batch ≤ max_pairs."""
    by_type: dict[str, list] = {}
    for b in todo:
        for q in b["questions"]:
            by_type.setdefault(q["question_type"], []).append((b["batch_id"], q))
    for t in by_type:  # ưu tiên câu hỏi ≤ max_q_pairs cặp, nhưng loại nào cũng có mặt
        by_type[t].sort(key=lambda x: (len(x[1]["pairs"]) > max_q_pairs, len(x[1]["pairs"]) == 1))
    picked, n, rnd = [], 0, 0
    while (n < n_target or rnd == 0) and any(by_type.values()):
        for t in sorted(by_type):
            if by_type[t] and (n < n_target or rnd == 0):  # vòng đầu: đủ mọi loại
                picked.append(by_type[t].pop(0))
                n += len(picked[-1][1]["pairs"])
        rnd += 1
    out, cur, cur_n = [], [], 0
    for bid, q in picked:
        if cur and cur_n + len(q["pairs"]) > max_pairs:
            out.append({"batch_id": "pilot", "questions": cur})
            cur, cur_n = [], 0
        cur.append({**q, "_orig_batch": bid})
        cur_n += len(q["pairs"])
    if cur:
        out.append({"batch_id": "pilot", "questions": cur})
    for i, b in enumerate(out):
        b["batch_id"] = f"pilot{i}"
    return out


def status(run_dir: Path, batches: list[dict]) -> dict:
    recs = read_jsonl(run_dir / "translations.jsonl")
    total = sum(len(q["pairs"]) for b in batches for q in b["questions"])
    latest = {}
    for r in recs:
        latest[r["pair_id"]] = r
    ok = [r for r in latest.values() if not r.get("error")]
    return {"pairs_total": total, "pairs_translated": len(ok),
            "pairs_rule_pass": sum(1 for r in ok if r.get("rule_pass")),
            "pairs_rule_fail": sum(1 for r in ok if not r.get("rule_pass")),
            "pairs_error_pending": sum(1 for r in latest.values() if r.get("error")),
            "batches_pending": len(pending_batches(batches, done_pairs(recs)))}


def recheck(run_dir: Path, batches: list[dict], glossary: dict, run_id: str) -> dict:
    """Áp lại luật hiện tại lên bản dịch đã có (không gọi model). Chỉ ghi thêm dòng mới
    (append-only) cho cặp có kết quả luật thay đổi; bản dịch giữ nguyên."""
    trans_p = run_dir / "translations.jsonl"
    latest = {}
    for r in read_jsonl(trans_p):
        latest[r["pair_id"]] = r
    rows, n_checked = [], 0
    for b in batches:
        for q in b["questions"]:
            recs = [latest.get(p["pair_id"]) for p in q["pairs"]]
            if not all(r and not r.get("error") for r in recs):
                continue
            qo = {"question_key": q["question_key"], "question_vi": recs[0]["question_vi"],
                  "pairs": [{"pair_id": r["pair_id"], "answer_vi": r["answer_vi"]} for r in recs]}
            res = check_question(q, qo, glossary)
            for r in recs:
                n_checked += 1
                errs = res.get(r["pair_id"], [])
                if errs != r.get("rule_errors"):
                    rows.append({**r, "ts": now(), "run_id": run_id, "recheck_of": r["run_id"],
                                 "rule_errors": errs, "rule_pass": not errs})
    append_jsonl(trans_p, rows)
    return {"pairs_rechecked": n_checked, "pairs_changed": len(rows),
            "now_pass": sum(1 for r in rows if r["rule_pass"]),
            "now_fail": sum(1 for r in rows if not r["rule_pass"])}


def run(args) -> int:
    cfg = load_config()
    s2 = cfg["step2"]
    out_dir, run_dir = ROOT / s2["out_dir"], ROOT / s2["run_dir"]
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "raw").mkdir(exist_ok=True)
    batches = read_jsonl(out_dir / "batches.jsonl")
    if not batches:
        print("Chưa có outputs/step2/batches.jsonl — chạy: python -m pvvqa.step2_prepare")
        return 2
    if args.status:
        print(json.dumps(status(run_dir, batches), indent=2, ensure_ascii=False))
        return 0

    prompt_p, gloss_p = ROOT / "prompts" / "translator.md", ROOT / s2["glossary"]
    schema_p = ROOT / "schemas" / "translation.json"
    glossary = load_glossary(gloss_p)
    sys_prompt = render_system_prompt(prompt_p, gloss_p)
    sys_file = run_dir / "system_prompt.md"
    sys_file.write_text(sys_prompt, encoding="utf-8")
    schema = json.dumps(json.loads(schema_p.read_text())) if s2.get("use_json_schema", True) else None
    cmd = args.claude_cmd.split() if args.claude_cmd else s2["claude_cmd"]
    config_hash = sha(ROOT / "config" / "phase1.yaml", gloss_p, prompt_p, schema_p)

    trans_p = run_dir / "translations.jsonl"
    if args.recheck:
        run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
        res = recheck(run_dir, batches, glossary, run_id)
        append_jsonl(run_dir / "run_log.jsonl", [{
            "run_id": run_id, "started": now(), "cmd": " ".join(sys.argv), "git_commit": git_commit(),
            "config_hash": config_hash, "mode": "recheck", **res, "stop_reason": "completed",
            **status(run_dir, batches)}])
        print(json.dumps(res, ensure_ascii=False))
        return 0
    todo = pending_batches(batches, done_pairs(read_jsonl(trans_p)))
    if args.batches:
        want = set(args.batches.split(","))
        todo = [b for b in todo if b["batch_id"] in want]
    if args.pilot:
        todo = pilot_batches(todo, args.pilot)
    if args.max_batches:
        todo = todo[:args.max_batches]

    run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    log = {"run_id": run_id, "started": now(), "cmd": " ".join(sys.argv), "git_commit": git_commit(),
           "config_hash": config_hash, "claude_cmd": cmd, "batches_planned": len(todo),
           "pairs_planned": sum(len(q["pairs"]) for b in todo for q in b["questions"])}
    print(f"[{run_id}] {log['batches_planned']} batch, {log['pairs_planned']} cặp cần dịch.")
    if args.dry_run:
        print(sys_prompt[:1500], "\n...\n", json.dumps(todo[:1], ensure_ascii=False)[:1500])
        return 0

    n_ok = n_rule_fail = n_err = consec = 0
    usage_in = usage_out = 0
    elapsed = 0.0
    stop_reason = "completed"
    for i, b in enumerate(todo, 1):
        payload = {"questions": [{"question_key": q["question_key"],
                                  "question_type": q["question_type"],
                                  "question_en": q["question_en"], "pairs": q["pairs"]}
                                 for q in b["questions"]]}
        rows = []
        try:
            out, meta = call_claude(cmd, sys_file, schema, payload, s2.get("timeout_s", 600))
            consec = 0
            u = meta.get("usage") or {}
            usage_in += int(u.get("input_tokens", 0)) + int(u.get("cache_read_input_tokens", 0)) \
                + int(u.get("cache_creation_input_tokens", 0))
            usage_out += int(u.get("output_tokens", 0))
            elapsed += meta.get("elapsed_s", 0)
            (run_dir / "raw" / f"{b['batch_id']}__{run_id}.json").write_text(
                json.dumps({"input": payload, "output": out, "meta": meta}, ensure_ascii=False,
                           indent=1), encoding="utf-8")
            by_key = {}
            for q in out.get("questions", []):
                by_key.setdefault(q.get("question_key"), q)
            for q in b["questions"]:
                qo = by_key.get(q["question_key"])
                res = check_question(q, qo, glossary)
                structural = any(e in ("missing_question", "missing_pair", "empty")
                                 for p in q["pairs"] for e in res.get(p["pair_id"], []))
                answers = {p.get("pair_id"): p.get("answer_vi") for p in (qo or {}).get("pairs", [])}
                for p in q["pairs"]:
                    errs = res.get(p["pair_id"], [])
                    rec = {"pair_id": p["pair_id"], "question_key": q["question_key"],
                           "batch_id": b["batch_id"], "ts": now(), "run_id": run_id}
                    if structural:  # câu hỏi không trọn vẹn -> thử lại cả câu hỏi
                        rec.update({"error": "incomplete_output:" + ",".join(errs or ["sibling"]),
                                    "question_vi": None, "answer_vi": None})
                        n_err += 1
                    else:
                        rec.update({"question_vi": (qo["question_vi"] or "").strip(),
                                    "answer_vi": (answers.get(p["pair_id"]) or "").strip(),
                                    "rule_errors": errs, "rule_pass": not errs, "error": None})
                        n_ok += 1
                        n_rule_fail += bool(errs)
                    rows.append(rec)
        except QuotaStop as e:
            stop_reason = f"quota: {e}"
            break
        except (RuntimeError, json.JSONDecodeError, subprocess.TimeoutExpired, OSError) as e:
            consec += 1
            for q in b["questions"]:
                for p in q["pairs"]:
                    rows.append({"pair_id": p["pair_id"], "question_key": q["question_key"],
                                 "batch_id": b["batch_id"], "ts": now(), "run_id": run_id,
                                 "question_vi": None, "answer_vi": None,
                                 "error": f"{type(e).__name__}: {str(e)[:300]}"})
                    n_err += 1
            if consec >= MAX_CONSEC_FAIL:
                append_jsonl(trans_p, rows)
                stop_reason = f"{MAX_CONSEC_FAIL} lỗi liên tiếp: {str(e)[:200]}"
                break
        append_jsonl(trans_p, rows)  # ghi ngay sau mỗi batch
        print(f"  [{i}/{len(todo)}] {b['batch_id']}: ok={n_ok} rule_fail={n_rule_fail} err={n_err}",
              flush=True)

    log.update({"finished": now(), "stop_reason": stop_reason, "pairs_ok_this_run": n_ok,
                "pairs_rule_fail_this_run": n_rule_fail, "pairs_error_this_run": n_err,
                "model_elapsed_s": round(elapsed, 1), "usage_input_tokens": usage_in,
                "usage_output_tokens": usage_out, **status(run_dir, batches)})
    append_jsonl(run_dir / "run_log.jsonl", [log])
    print(json.dumps({k: log[k] for k in ("stop_reason", "pairs_ok_this_run",
                                          "pairs_rule_fail_this_run", "pairs_error_this_run",
                                          "pairs_translated", "pairs_total")}, ensure_ascii=False))
    if stop_reason != "completed":
        print("Dừng sớm. Chạy tiếp bằng: PYTHONPATH=src python -m pvvqa.step2_translate")
        return 3
    return 0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pilot", type=int, help="dịch thử khoảng N cặp, rải theo question_type")
    ap.add_argument("--batches", help="danh sách batch_id, cách nhau bởi dấu phẩy")
    ap.add_argument("--max-batches", type=int)
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--recheck", action="store_true",
                    help="áp lại luật hiện tại lên bản dịch đã có, không gọi model")
    ap.add_argument("--claude-cmd", help="ghi đè lệnh claude (dùng cho test)")
    sys.exit(run(ap.parse_args()))


if __name__ == "__main__":
    main()

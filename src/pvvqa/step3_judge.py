"""Step 3.1–3.2 — chấm bản dịch EN↔VI bằng Codex (`codex exec`, gói ChatGPT), checkpoint append-only.

Chạy trên Terminal của Mac (nơi đã đăng nhập Codex):
  export PYTHONPATH=src
  unset OPENAI_API_KEY
  python -m pvvqa.step3_judge --smoke        # smoke test bắt buộc trước khi chấm toàn bộ
  python -m pvvqa.step3_judge --pilot 80     # chấm thử ~80 cặp thật, đo quota
  python -m pvvqa.step3_judge                # chấm toàn bộ phần còn lại
  python -m pvvqa.step3_judge --status
  python -m pvvqa.step3_judge --crosscheck 120 --model gpt-6.1-sol --reasoning high  # kiểm tra chéo

Chỉ chấm cặp đã qua luật ở Step 2; cặp trượt luật chuyển thẳng sang repair.
Kết quả: runs/step3/judgments.jsonl (smoke: runs/step3/smoke_judgments.jsonl) — mỗi dòng một mục:
  {id, errors:[{category, severity, explanation}], verdict, model, reasoning, batch_id, ts, run_id, error}
  verdict = PASS nếu không có lỗi major/critical, ngược lại NEEDS_REPAIR.
  error != null -> lần sau chấm lại.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import yaml

from pvvqa.common import ROOT, load_config
from pvvqa.step2_translate import (QUOTA_PAT, QuotaStop, append_jsonl, extract_json, git_commit,
                                   now, pilot_batches, read_jsonl, sha)

MAX_CONSEC_FAIL = 3
SILENT_RETRY_WAIT_S = 30
BLOCKING = {"major", "critical"}
FIELDS = ("question_type", "question_en", "answer_en", "question_vi", "answer_vi")


def verdict(errors: list[dict]) -> str:
    return "NEEDS_REPAIR" if any(e.get("severity") in BLOCKING for e in errors) else "PASS"


def load_translations(cfg: dict) -> pd.DataFrame:
    """Bản dịch mới nhất của mỗi cặp (Step 2) ghép với bảng cặp."""
    latest = {}
    for r in read_jsonl(ROOT / cfg["step2"]["run_dir"] / "translations.jsonl"):
        latest[r["pair_id"]] = r
    tr = pd.DataFrame([r for r in latest.values() if not r.get("error")])
    pairs = pd.read_parquet(ROOT / cfg["step2"]["out_dir"] / "pairs.parquet")
    return pairs.merge(tr[["pair_id", "question_vi", "answer_vi", "rule_errors", "rule_pass"]],
                       on="pair_id", how="left")


def render_judge_prompt(prompt_path: Path, glossary_path: Path) -> str:
    g = yaml.safe_load(glossary_path.read_text(encoding="utf-8"))
    lines = [prompt_path.read_text(encoding="utf-8").rstrip(), "", "## Glossary (EN → VI)", "", "### Crops"]
    lines += [f"- {e['en']} → {e['vi']}" for e in g["crops"]]
    lines += ["", "### Diseases / pests"] + [f"- {e['en']} → {e['vi']}" for e in g["diseases"]]
    lines += ["", "### Keep as written"] + [f"- {k}" for k in g["keep"]]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- smoke test (3.1)
POLARITY_SWAPS = [("khỏe mạnh", "bị bệnh"), ("sạch bệnh", "nhiễm bệnh"), ("bị nhiễm bệnh", "khỏe mạnh"),
                  ("bị bệnh", "khỏe mạnh"), ("không có", "có")]
CROP_SWAPS = {"cà chua": "khoai tây", "khoai tây": "cà chua", "đậu nành": "ngô", "ngô": "đậu nành",
              "ớt chuông": "cà chua", "dâu tây": "việt quất", "việt quất": "dâu tây", "táo": "đào",
              "đào": "táo", "nho": "táo", "anh đào": "mâm xôi", "mâm xôi": "anh đào"}
DISEASE_SWAPS = {"mốc sương": "đốm vòng", "đốm vòng": "mốc sương", "đốm vi khuẩn": "mốc lá",
                 "mốc lá": "đốm vi khuẩn", "đốm hình bia": "phấn trắng", "vàng lá gân xanh": "khảm",
                 "xoăn vàng lá": "đốm vi khuẩn", "nhện đỏ": "rệp sáp", "Septoria": "Cercospora",
                 "phấn trắng": "gỉ sắt", "thối đen": "ghẻ"}


def _word(s: str) -> re.Pattern:
    return re.compile(rf"(?<!\w){re.escape(s)}(?!\w)", re.IGNORECASE)


def _swap_all(text: str, swaps: dict) -> str:
    """Đổi đồng thời (không đổi chồng) mọi khoá trong swaps, khớp nguyên từ."""
    keys = sorted(swaps, key=len, reverse=True)
    pat = re.compile(r"(?<!\w)(" + "|".join(re.escape(k) for k in keys) + r")(?!\w)", re.IGNORECASE)
    return pat.sub(lambda m: swaps[next(k for k in keys if k.lower() == m.group(0).lower())], text)


def _drop_condition(a: str) -> str | None:
    m = re.match(r"^Nếu ([^,]+), (.+)$", a)
    if m:
        rest = m.group(2).replace("sẽ ", "")
        return rest[0].upper() + rest[1:]
    m = re.match(r"^Một (cây|chiếc lá|lá) khỏe mạnh( thuộc loại này)? sẽ (.+)$", a)
    if m:
        return "Lá này " + m.group(3)
    return None


def build_smoke(df: pd.DataFrame, n: int = 10, seed: int = 42) -> list[dict]:
    """~n mục cố ý sai cho mỗi loại (polarity, crop, disease, conditional) + n mục đúng (control).
    Chỉ lấy từ cặp đã qua luật; mỗi question_en dùng tối đa một lần mỗi loại."""
    ok = df[df.rule_pass == True].sample(frac=1, random_state=seed)  # noqa: E712
    items: list[dict] = []

    def count(kind):
        return sum(i["kind"] == kind for i in items)

    def take(kind, rows, fn, limit=n):
        seen = {i["question_en"] for i in items if i["kind"] == kind}
        start = count(kind)
        for r in rows.itertuples():
            if count(kind) >= n or count(kind) - start >= limit:
                break
            out = fn(r) if r.question_en not in seen else None
            if out and (kind == "control" or out != (r.question_vi, r.answer_vi)):
                seen.add(r.question_en)
                items.append({"id": f"smoke_{kind}_{count(kind):02d}", "kind": kind,
                              "pair_id": r.pair_id, "question_type": r.question_type,
                              "question_en": r.question_en, "answer_en": r.answer_en,
                              "question_vi": out[0], "answer_vi": out[1],
                              "orig_question_vi": r.question_vi, "orig_answer_vi": r.answer_vi})

    # control: bản dịch nguyên vẹn, rải theo question_type
    take("control", ok.groupby("question_type", group_keys=False).head(2),
         lambda r: (r.question_vi, r.answer_vi))
    # polarity: Yes/No, đảo mệnh đề trong câu hỏi, giữ nguyên câu trả lời -> sai nghĩa
    yn = ok[ok.is_yes_no]
    for a, b in POLARITY_SWAPS * 2:  # vòng 1: chia đều các kiểu đảo; vòng 2: lấp cho đủ n
        take("polarity", yn[yn.question_vi.str.contains(_word(a))],
             lambda r: (_word(a).sub(b, r.question_vi, count=1), r.answer_vi),
             limit=max(1, n // len(POLARITY_SWAPS)))

    crop_re = re.compile("|".join(_word(k).pattern for k in CROP_SWAPS), re.IGNORECASE)
    take("crop", ok[ok.question_vi.str.contains(crop_re) | ok.answer_vi.str.contains(crop_re)],
         lambda r: (_swap_all(r.question_vi, CROP_SWAPS), _swap_all(r.answer_vi, CROP_SWAPS)))

    dis_re = re.compile("|".join(_word(k).pattern for k in DISEASE_SWAPS), re.IGNORECASE)
    take("disease", ok[ok.answer_vi.str.contains(dis_re) & ~ok.is_yes_no],
         lambda r: (r.question_vi, _swap_all(r.answer_vi, DISEASE_SWAPS)))

    cf = ok[ok.answer_vi.map(lambda a: _drop_condition(a) is not None)]
    take("conditional", cf, lambda r: (r.question_vi, _drop_condition(r.answer_vi)))

    random.Random(seed).shuffle(items)
    return items


def smoke_report(items: list[dict], judged: dict[str, dict]) -> dict:
    kinds = sorted({i["kind"] for i in items})
    out = {}
    for k in kinds:
        its = [i for i in items if i["kind"] == k]
        got = [judged.get(i["id"]) for i in its]
        flagged = sum(1 for g in got if g and g["verdict"] == "NEEDS_REPAIR")
        out[k] = {"n": len(its), "judged": sum(1 for g in got if g),
                  ("false_alarm" if k == "control" else "caught"): flagged,
                  "any_error": sum(1 for g in got if g and g["errors"])}
    return out


def smoke_markdown(items: list[dict], judged: dict[str, dict], rep: dict, meta: dict) -> str:
    L = ["# Step 3.1 — Smoke test cho judge (KHÔNG phải hiệu chuẩn)", "",
         f"- Judge: `{meta['model']}`, reasoning `{meta['reasoning']}`; run `{meta['run_id']}`",
         "- Mục cố ý sai sinh tự động bằng thay thế chuỗi trên bản dịch đã qua luật (seed 42).",
         "- \"Bắt được\" = judge cho ít nhất một lỗi major/critical (verdict NEEDS_REPAIR).", "",
         "| loại | n | bắt được / báo nhầm | có ít nhất 1 lỗi (kể cả minor) |", "|---|---|---|---|"]
    for k, v in rep.items():
        hit = v.get("caught", v.get("false_alarm"))
        lab = "báo nhầm" if k == "control" else "bắt được"
        L.append(f"| {k} | {v['n']} | {lab} {hit}/{v['n']} | {v['any_error']}/{v['n']} |")
    L += ["", "## Chi tiết", ""]
    for i in sorted(items, key=lambda x: x["id"]):
        j = judged.get(i["id"]) or {}
        L.append(f"- **{i['id']}** ({i['question_type']}) → **{j.get('verdict', '—')}**")
        L.append(f"  - EN: {i['question_en']} | {i['answer_en']}")
        if i["kind"] != "control":
            L.append(f"  - VI gốc: {i['orig_question_vi']} | {i['orig_answer_vi']}")
        L.append(f"  - VI chấm: {i['question_vi']} | {i['answer_vi']}")
        for e in j.get("errors", []):
            L.append(f"  - [{e['severity']}/{e['category']}] {e['explanation']}")
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------- kiểm tra chéo
def crosscheck_report(ids: list[str], first: dict[str, dict], other: dict[str, dict], meta: dict) -> tuple[dict, str]:
    """So verdict của judge chính (first) với một model khác (other) trên cùng bản dịch gốc."""
    both = [i for i in ids if i in first and i in other]
    agree = sum(first[i]["verdict"] == other[i]["verdict"] for i in both)
    only_other = [i for i in both if other[i]["verdict"] != "PASS" and first[i]["verdict"] == "PASS"]
    only_first = [i for i in both if first[i]["verdict"] != "PASS" and other[i]["verdict"] == "PASS"]
    rep = {"n": len(both), "agree": agree, "main_pass_other_needs_repair": len(only_other),
           "main_needs_repair_other_pass": len(only_first),
           "main_any_error": sum(bool(first[i]["errors"]) for i in both),
           "other_any_error": sum(bool(other[i]["errors"]) for i in both)}
    L = [f"# Kiểm tra chéo judge (KHÔNG phải hiệu chuẩn)", "",
         f"- Judge chính: `{meta['main']}`; model đối chiếu: `{meta['other']}`; mẫu ngẫu nhiên {len(both)} cặp "
         "đã qua luật (seed 42), chấm trên bản dịch Step 2 (trước repair).", "",
         f"- Đồng ý về verdict: **{agree}/{len(both)}**",
         f"- Judge chính PASS nhưng model đối chiếu NEEDS_REPAIR: **{len(only_other)}**",
         f"- Judge chính NEEDS_REPAIR nhưng model đối chiếu PASS: **{len(only_first)}**",
         f"- Có ít nhất một lỗi (kể cả minor): judge chính {rep['main_any_error']}, đối chiếu {rep['other_any_error']}",
         "", "## Các cặp bất đồng", ""]
    for i in only_other + only_first:
        L.append(f"- `{i}`: chính **{first[i]['verdict']}**, đối chiếu **{other[i]['verdict']}**")
        for who, d in (("chính", first[i]), ("đối chiếu", other[i])):
            for e in d["errors"]:
                L.append(f"  - {who} [{e['severity']}/{e['category']}] {e['explanation']}")
    return rep, "\n".join(L) + "\n"


# ---------------------------------------------------------------- gọi Codex
def call_codex(cmd: list[str], model: str, effort: str, instr_file: Path, schema_file: Path,
               payload: dict, timeout: int) -> tuple[dict, dict]:
    """Trả (parsed_output, meta). Ném QuotaStop khi hết quota / rate limit."""
    user_msg = ("Evaluate these translations following your instructions. Return only the JSON object.\n\n"
                + json.dumps(payload, ensure_ascii=False, indent=1))
    env = {k: v for k, v in os.environ.items() if k != "OPENAI_API_KEY"}
    with tempfile.TemporaryDirectory() as tmp:  # cwd rỗng: không nạp AGENTS.md / file dự án
        last = Path(tmp) / "last.json"
        full = list(cmd) + ["-m", model, "-c", f"model_reasoning_effort={effort}",
                            "-c", f'model_instructions_file="{instr_file}"',
                            "--output-schema", str(schema_file), "-o", str(last), "--json", "-"]
        t0 = time.time()
        proc = subprocess.run(full, input=user_msg, capture_output=True, text=True, cwd=tmp,
                              env=env, timeout=timeout)
        meta = {"returncode": proc.returncode, "elapsed_s": round(time.time() - t0, 1)}
        errs = []
        for line in proc.stdout.splitlines():
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            if ev.get("type") == "turn.completed" and ev.get("usage"):
                meta["usage"] = ev["usage"]
            if "error" in ev.get("type", "") or ev.get("error"):
                errs.append(json.dumps(ev, ensure_ascii=False)[:300])
        text = last.read_text(encoding="utf-8") if last.exists() else ""
    err_text = " ".join(errs + [proc.stderr[-500:] if proc.returncode else ""]).strip()
    if proc.returncode != 0 or not text.strip():
        meta["error_text"] = err_text[:500]
        if QUOTA_PAT.search(err_text):
            raise QuotaStop(meta["error_text"])
        raise RuntimeError(meta["error_text"] or f"codex exited {proc.returncode}")
    return extract_json(text), meta


def call_codex_retry(*a, **kw) -> tuple[dict, dict]:
    try:
        return call_codex(*a, **kw)
    except RuntimeError as e:
        if not str(e).startswith("codex exited"):
            raise
        time.sleep(SILENT_RETRY_WAIT_S)
        return call_codex(*a, **kw)


def judge_batches(batches: list[list[dict]], out_p: Path, ctx: dict) -> dict:
    """batches: danh sách batch, mỗi batch là list mục {id, batch_id, FIELDS...}. Ghi sau mỗi batch."""
    n_ok = n_flag = n_err = consec = 0
    usage_in = usage_out = 0
    elapsed = 0.0
    stop = "completed"
    for i, b in enumerate(batches, 1):
        payload = {"items": [{"id": it["id"], **{f: it[f] for f in FIELDS}} for it in b]}
        rows = []
        base = {"batch_id": b[0].get("batch_id"), "run_id": ctx["run_id"], "model": ctx["model"],
                "reasoning": ctx["reasoning"]}
        try:
            out, meta = call_codex_retry(ctx["cmd"], ctx["model"], ctx["reasoning"], ctx["instr"],
                                         ctx["schema"], payload, ctx["timeout"])
            consec = 0
            u = meta.get("usage") or {}
            usage_in += int(u.get("input_tokens", 0))
            usage_out += int(u.get("output_tokens", 0))
            elapsed += meta.get("elapsed_s", 0)
            (ctx["raw_dir"] / f"{base['batch_id']}__{ctx['run_id']}.json").write_text(
                json.dumps({"input": payload, "output": out, "meta": meta}, ensure_ascii=False, indent=1),
                encoding="utf-8")
            got = {o.get("id"): o for o in out.get("items", [])}
            for it in b:
                o = got.get(it["id"])
                rec = {"id": it["id"], **base, "ts": now()}
                if o is None:
                    rec.update({"errors": None, "verdict": None, "error": "missing_item"})
                    n_err += 1
                else:
                    errs = o.get("errors") or []
                    rec.update({"errors": errs, "verdict": verdict(errs), "error": None})
                    n_ok += 1
                    n_flag += rec["verdict"] != "PASS"
                rows.append(rec)
        except QuotaStop as e:
            stop = f"quota: {e}"
            break
        except (RuntimeError, json.JSONDecodeError, subprocess.TimeoutExpired, OSError) as e:
            consec += 1
            for it in b:
                rows.append({"id": it["id"], **base, "ts": now(), "errors": None, "verdict": None,
                             "error": f"{type(e).__name__}: {str(e)[:300]}"})
                n_err += 1
            if consec >= MAX_CONSEC_FAIL:
                append_jsonl(out_p, rows)
                stop = f"{MAX_CONSEC_FAIL} lỗi liên tiếp: {str(e)[:200]}"
                break
        append_jsonl(out_p, rows)  # ghi ngay sau mỗi batch
        print(f"  [{i}/{len(batches)}] {base['batch_id']}: ok={n_ok} needs_repair={n_flag} err={n_err}",
              flush=True)
    return {"stop_reason": stop, "items_ok_this_run": n_ok, "items_needs_repair_this_run": n_flag,
            "items_error_this_run": n_err, "model_elapsed_s": round(elapsed, 1),
            "usage_input_tokens": usage_in, "usage_output_tokens": usage_out}


def latest_valid(path: Path) -> dict[str, dict]:
    latest = {}
    for r in read_jsonl(path):
        latest[r["id"]] = r
    return {k: r for k, r in latest.items() if not r.get("error")}


def real_batches(cfg: dict, df: pd.DataFrame, done: set[str]) -> list[dict]:
    """Batch của Step 2 (giữ nhóm theo câu hỏi), chỉ gồm cặp đã qua luật và chưa được chấm."""
    ok = df[df.rule_pass == True].set_index("pair_id")  # noqa: E712
    out = []
    for b in read_jsonl(ROOT / cfg["step2"]["out_dir"] / "batches.jsonl"):
        qs = []
        for q in b["questions"]:
            ps = [p for p in q["pairs"] if p["pair_id"] in ok.index and p["pair_id"] not in done]
            if ps:
                qs.append({**q, "pairs": ps})
        if qs:
            out.append({"batch_id": b["batch_id"], "questions": qs})
    return out


def to_items(batch: dict, df_idx: pd.DataFrame) -> list[dict]:
    items = []
    for q in batch["questions"]:
        for p in q["pairs"]:
            r = df_idx.loc[p["pair_id"]]
            items.append({"id": p["pair_id"], "batch_id": batch["batch_id"],
                          **{f: r[f] for f in FIELDS}})
    return items


def status(cfg: dict, df: pd.DataFrame) -> dict:
    run_dir = ROOT / cfg["step3"]["run_dir"]
    j = latest_valid(run_dir / "judgments.jsonl")
    ok_ids = set(df.loc[df.rule_pass == True, "pair_id"])  # noqa: E712
    jj = [r for k, r in j.items() if k in ok_ids]
    n_rows = df.set_index("pair_id").n_rows
    flagged = [r["id"] for r in jj if r["verdict"] != "PASS"]
    return {"pairs_total": len(df), "pairs_rule_fail": int((df.rule_pass != True).sum()),  # noqa: E712
            "pairs_to_judge": len(ok_ids), "pairs_judged": len(jj),
            "pairs_pass": len(jj) - len(flagged), "pairs_needs_repair": len(flagged),
            "rows_needs_repair": int(n_rows.loc[flagged].sum()) if flagged else 0}


def judge_ctx(cfg: dict, model: str | None, reasoning: str | None, codex_cmd: str | None,
              run_id: str) -> dict:
    """Cấu hình một lần chạy judge (dùng chung cho chấm lần đầu và chấm lại sau repair)."""
    s3 = cfg["step3"]
    run_dir = ROOT / s3["run_dir"]
    (run_dir / "raw").mkdir(parents=True, exist_ok=True)
    instr = run_dir / "judge_system.md"
    instr.write_text(render_judge_prompt(ROOT / "prompts" / "judge.md", ROOT / cfg["step2"]["glossary"]),
                     encoding="utf-8")
    return {"cmd": codex_cmd.split() if codex_cmd else s3["codex_cmd"],
            "model": model or s3["judge_model"], "reasoning": reasoning or s3["judge_reasoning"],
            "instr": instr.resolve(), "schema": (ROOT / "schemas" / "judge.json").resolve(),
            "timeout": s3.get("timeout_s", 600), "raw_dir": run_dir / "raw", "run_id": run_id}


def run(args) -> int:
    cfg = load_config()
    s3 = cfg["step3"]
    run_dir = ROOT / s3["run_dir"]
    (run_dir / "raw").mkdir(parents=True, exist_ok=True)
    out_dir = ROOT / "outputs" / "step3"
    out_dir.mkdir(parents=True, exist_ok=True)
    df = load_translations(cfg)
    if args.status:
        print(json.dumps(status(cfg, df), indent=2, ensure_ascii=False))
        return 0

    prompt_p, gloss_p = ROOT / "prompts" / "judge.md", ROOT / cfg["step2"]["glossary"]
    schema_p = ROOT / "schemas" / "judge.json"
    run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    ctx = judge_ctx(cfg, args.model, args.reasoning, args.codex_cmd, run_id)
    model, reasoning, instr = ctx["model"], ctx["reasoning"], ctx["instr"]
    size = s3.get("max_pairs_per_call", 40)
    log = {"run_id": run_id, "started": now(), "cmd": " ".join(sys.argv), "git_commit": git_commit(),
           "config_hash": sha(ROOT / "config" / "phase1.yaml", gloss_p, prompt_p, schema_p),
           "model": model, "reasoning": reasoning}

    if args.smoke:
        items = build_smoke(df, s3.get("smoke_per_type", 10))
        tag = f"{model}__{reasoning}"
        set_p = out_dir / "smoke_set.jsonl"
        if not set_p.exists():
            append_jsonl(set_p, items)
        items = read_jsonl(set_p)  # bộ smoke cố định, dùng lại cho mọi lần chạy
        out_p = run_dir / f"smoke_judgments__{tag}.jsonl"
        done = set(latest_valid(out_p)) if not args.fresh else set()
        todo = [dict(it, batch_id=f"smoke{k // size}") for k, it in enumerate(items) if it["id"] not in done]
        batches = [todo[k:k + size] for k in range(0, len(todo), size)]
        print(f"[{run_id}] smoke: {len(items)} mục, {len(todo)} cần chấm ({model}, {reasoning}).")
        res = judge_batches(batches, out_p, ctx)
        judged = latest_valid(out_p)
        rep = smoke_report(items, judged)
        meta = {"model": model, "reasoning": reasoning, "run_id": run_id}
        (out_dir / f"smoke_report__{tag}.md").write_text(smoke_markdown(items, judged, rep, meta),
                                                         encoding="utf-8")
        (out_dir / f"smoke_report__{tag}.json").write_text(json.dumps(rep, indent=1), encoding="utf-8")
        log.update({"mode": "smoke", **res, "smoke": rep, "finished": now()})
        append_jsonl(run_dir / "run_log.jsonl", [log])
        print(json.dumps(rep, ensure_ascii=False))
        return 0 if res["stop_reason"] == "completed" else 3

    if args.crosscheck:
        main = latest_valid(run_dir / "judgments.jsonl")
        ids = sorted(df.loc[df.rule_pass == True, "pair_id"])  # noqa: E712
        ids = random.Random(42).sample(ids, min(args.crosscheck, len(ids)))
        tag = f"{model}__{reasoning}"
        out_p = run_dir / f"crosscheck__{tag}.jsonl"
        done = set(latest_valid(out_p))
        idx = df.set_index("pair_id")
        todo = [{"id": i, "batch_id": f"cross{k // size}", **{f: idx.loc[i, f] for f in FIELDS}}
                for k, i in enumerate(ids) if i not in done]
        batches = [todo[k:k + size] for k in range(0, len(todo), size)]
        print(f"[{run_id}] kiểm tra chéo: {len(ids)} cặp, {len(todo)} cần chấm ({model}, {reasoning}).")
        res = judge_batches(batches, out_p, ctx)
        rep, md = crosscheck_report(ids, main, latest_valid(out_p),
                                    {"main": f"{s3['judge_model']} {s3['judge_reasoning']}", "other": f"{model} {reasoning}"})
        (out_dir / f"crosscheck_report__{tag}.md").write_text(md, encoding="utf-8")
        (out_dir / f"crosscheck_report__{tag}.json").write_text(json.dumps(rep, indent=1), encoding="utf-8")
        log.update({"mode": "crosscheck", **res, "crosscheck": rep, "finished": now()})
        append_jsonl(run_dir / "run_log.jsonl", [log])
        print(json.dumps(rep, ensure_ascii=False))
        return 0 if res["stop_reason"] == "completed" else 3

    out_p = run_dir / "judgments.jsonl"
    todo = real_batches(cfg, df, set(latest_valid(out_p)))
    if args.pilot:
        todo = pilot_batches(todo, args.pilot, max_pairs=size)
    if args.max_batches:
        todo = todo[:args.max_batches]
    idx = df.set_index("pair_id")
    batches = []
    for b in todo:  # batch Step 2 ≤ 40 cặp; cắt lại theo max_pairs_per_call nếu cần
        its = to_items(b, idx)
        batches += [its[k:k + size] for k in range(0, len(its), size)]
    log.update({"mode": "pilot" if args.pilot else "judge", "batches_planned": len(batches),
                "items_planned": sum(len(b) for b in batches)})
    print(f"[{run_id}] {len(batches)} batch, {log['items_planned']} cặp cần chấm ({model}, {reasoning}).")
    if args.dry_run:
        print(instr.read_text()[:1500])
        return 0
    res = judge_batches(batches, out_p, ctx)
    log.update({**res, "finished": now(), **status(cfg, df)})
    append_jsonl(run_dir / "run_log.jsonl", [log])
    print(json.dumps({k: log[k] for k in ("stop_reason", "items_ok_this_run", "items_needs_repair_this_run",
                                          "items_error_this_run", "pairs_judged", "pairs_to_judge")},
                     ensure_ascii=False))
    if res["stop_reason"] != "completed":
        print("Dừng sớm. Chạy tiếp bằng: PYTHONPATH=src python -m pvvqa.step3_judge")
        return 3
    return 0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true", help="smoke test (bắt buộc trước khi chấm toàn bộ)")
    ap.add_argument("--fresh", action="store_true", help="smoke: chấm lại toàn bộ (vd. sau khi sửa prompt)")
    ap.add_argument("--pilot", type=int, help="chấm thử khoảng N cặp, rải theo question_type")
    ap.add_argument("--crosscheck", type=int,
                    help="chấm lại N cặp ngẫu nhiên bằng --model/--reasoning khác, so với judge chính")
    ap.add_argument("--max-batches", type=int)
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--model", help="ghi đè judge_model (vd. phương án dự phòng)")
    ap.add_argument("--reasoning", help="ghi đè judge_reasoning")
    ap.add_argument("--codex-cmd", help="ghi đè lệnh codex (dùng cho test)")
    sys.exit(run(ap.parse_args()))


if __name__ == "__main__":
    main()

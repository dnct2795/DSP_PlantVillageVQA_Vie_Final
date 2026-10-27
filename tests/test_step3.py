import json
import sys
from pathlib import Path

import pandas as pd
import pytest

from pvvqa import step3_judge as sj
from pvvqa.common import ROOT
from pvvqa.step2_prepare import build_pairs, make_batches

FAKE = Path(__file__).with_name("fake_codex.py")

VI = {  # bản dịch giả cho từng (question, answer) nguồn
    ("Is this Tomato leaf infected with Late blight?", "Yes"): ("Lá cà chua này có bị nhiễm bệnh mốc sương không?", "Có"),
    ("Is this Tomato leaf infected with Late blight?", "No"): ("Lá cà chua này có bị nhiễm bệnh mốc sương không?", "Không"),
    ("What disease is this?", "The condition is identified as Late Blight."): ("Đây là bệnh gì?", "Tình trạng được xác định là bệnh mốc sương."),
    ("What disease is this?", "This is a healthy plant leaf."): ("Đây là bệnh gì?", "Đây là lá cây khỏe mạnh."),
    ("What disease is this?", "Diagnosis: Leaf Mold."): ("Đây là bệnh gì?", "Chẩn đoán: bệnh mốc lá."),
    ("Is this foliage completely symptom-free?", "Yes"): ("Lá này có hoàn toàn sạch bệnh không?", "Có"),
    ("Is this foliage completely symptom-free?", "No"): ("Lá này có hoàn toàn sạch bệnh không?", "Không"),
    ("What would a healthy leaf look like?", "If the plant were healthy, the spots would be absent."):
        ("Một chiếc lá khỏe mạnh trông như thế nào?", "Nếu cây khỏe mạnh, các đốm sẽ không có."),
}


@pytest.fixture
def project(tmp_path, monkeypatch):
    root = tmp_path
    for d in ("config", "prompts", "schemas", "outputs/step2", "runs/step2"):
        (root / d).mkdir(parents=True)
    for f in ("config/glossary.yaml", "prompts/judge.md", "schemas/judge.json"):
        (root / f).write_text((ROOT / f).read_text(encoding="utf-8"), encoding="utf-8")
    (root / "config/phase1.yaml").write_text(
        "step2: {out_dir: outputs/step2, run_dir: runs/step2, glossary: config/glossary.yaml}\n"
        "step3: {run_dir: runs/step3, max_pairs_per_call: 3, judge_model: m, judge_reasoning: high,\n"
        "        codex_cmd: [x], timeout_s: 30, smoke_per_type: 2}\n", encoding="utf-8")
    rows, k = [], 0
    for (q, a) in VI:
        qt = "Counterfactual Reasoning" if q.startswith("What would") else "Detailed Verification"
        for _ in range(2):
            rows.append({"qa_id": f"pvqa_{k:06d}", "question_type": qt, "question": q, "answer": a})
            k += 1
    pairs, _, _ = build_pairs(pd.DataFrame(rows))
    pairs.to_parquet(root / "outputs/step2/pairs.parquet")
    with open(root / "outputs/step2/batches.jsonl", "w", encoding="utf-8") as f:
        for b in make_batches(pairs, max_pairs=4):
            f.write(json.dumps(b) + "\n")
    with open(root / "runs/step2/translations.jsonl", "w", encoding="utf-8") as f:
        for i, p in enumerate(pairs.itertuples()):
            q_vi, a_vi = VI[(p.question_en, p.answer_en)]
            fail = p.answer_en == "Diagnosis: Leaf Mold."  # một cặp trượt luật -> không được chấm
            f.write(json.dumps({"pair_id": p.pair_id, "question_vi": q_vi, "answer_vi": a_vi,
                                "rule_errors": ["x"] if fail else [], "rule_pass": not fail,
                                "error": None}, ensure_ascii=False) + "\n")
    import pvvqa.common as common
    for mod in (sj, common):
        monkeypatch.setattr(mod, "ROOT", root)
    monkeypatch.setattr(sj, "load_config", lambda: common.load_config(root / "config/phase1.yaml"))
    monkeypatch.setattr(sj, "SILENT_RETRY_WAIT_S", 0)
    return root


def _args(**kw):
    import argparse
    d = dict(smoke=False, fresh=False, pilot=None, max_batches=None, status=False, dry_run=False,
             model=None, reasoning=None, codex_cmd=f"{sys.executable} {FAKE}")
    d.update(kw)
    return argparse.Namespace(**d)


def test_verdict():
    assert sj.verdict([]) == "PASS"
    assert sj.verdict([{"severity": "minor"}]) == "PASS"
    assert sj.verdict([{"severity": "minor"}, {"severity": "major"}]) == "NEEDS_REPAIR"


def test_corruptions():
    assert sj._swap_all("Lá cà chua bị mốc sương", sj.DISEASE_SWAPS) == "Lá cà chua bị đốm vòng"
    assert sj._swap_all("lá cà chua, không phải khoai tây", sj.CROP_SWAPS) == "lá khoai tây, không phải cà chua"
    assert sj._swap_all("màu cam", sj.CROP_SWAPS) == "màu cam"  # "cam" (màu) không bị đổi
    assert sj._drop_condition("Nếu cây khỏe mạnh, các đốm sẽ không có.") == "Các đốm không có."
    assert sj._drop_condition("Đây là bệnh mốc sương.") is None


def test_build_smoke_deterministic_and_only_rule_pass(project):
    df = sj.load_translations(sj.load_config())
    a, b = sj.build_smoke(df, 2), sj.build_smoke(df, 2)
    assert a == b
    kinds = {i["kind"] for i in a}
    assert {"control", "polarity", "disease", "conditional"} <= kinds
    bad_pid = df.loc[df.rule_pass == False, "pair_id"].iloc[0]  # noqa: E712
    assert all(i["pair_id"] != bad_pid for i in a)
    for i in a:
        changed = (i["question_vi"], i["answer_vi"]) != (i["orig_question_vi"], i["orig_answer_vi"])
        assert changed == (i["kind"] != "control")


def test_smoke_run_reports_caught(project, monkeypatch):
    monkeypatch.setenv("FAKE_MODE", "good")
    assert sj.run(_args(smoke=True)) == 0
    rep = json.loads((project / "outputs/step3/smoke_report__m__high.json").read_text())
    assert rep["control"]["false_alarm"] == 0
    assert all(v["caught"] == v["n"] for k, v in rep.items() if k != "control")
    assert (project / "outputs/step3/smoke_report__m__high.md").exists()


def test_judge_skips_rule_fail_resume_and_idempotent(project, monkeypatch):
    monkeypatch.setenv("FAKE_MODE", "good")
    assert sj.run(_args()) == 0
    df = sj.load_translations(sj.load_config())
    s = sj.status(sj.load_config(), df)
    assert s["pairs_judged"] == s["pairs_to_judge"] == len(df) - 1 and s["pairs_needs_repair"] == 0
    n = len(sj.read_jsonl(project / "runs/step3/judgments.jsonl"))
    assert sj.run(_args()) == 0  # chạy lại: không chấm lại
    assert len(sj.read_jsonl(project / "runs/step3/judgments.jsonl")) == n


def test_quota_stops_cleanly(project, monkeypatch):
    monkeypatch.setenv("FAKE_MODE", "quota")
    assert sj.run(_args()) == 3
    log = sj.read_jsonl(project / "runs/step3/run_log.jsonl")[-1]
    assert log["stop_reason"].startswith("quota") and log["pairs_judged"] == 0


def test_broken_output_stops_after_3_then_retried(project, monkeypatch):
    monkeypatch.setenv("FAKE_MODE", "broken")
    assert sj.run(_args()) == 3
    monkeypatch.setenv("FAKE_MODE", "good")
    assert sj.run(_args()) == 0
    s = sj.status(sj.load_config(), sj.load_translations(sj.load_config()))
    assert s["pairs_judged"] == s["pairs_to_judge"]


FAKE_CLAUDE = Path(__file__).with_name("fake_claude.py")


def test_repair_flow_statuses(project, monkeypatch):
    from pvvqa import step3_repair as sr
    import pvvqa.step2_translate as st2
    monkeypatch.setattr(sr, "ROOT", project)
    monkeypatch.setattr(sr, "load_config", sj.load_config)
    monkeypatch.setattr(st2, "SILENT_RETRY_WAIT_S", 0)
    for f in ("prompts/translator.md", "prompts/repair.md", "schemas/translation.json"):
        (project / f).write_text((ROOT / f).read_text(encoding="utf-8"), encoding="utf-8")
    cfg_text = (project / "config/phase1.yaml").read_text()
    (project / "config/phase1.yaml").write_text(cfg_text.replace(
        "step2: {", "step2: {claude_cmd: [x], max_pairs_per_batch: 40, "), encoding="utf-8")
    # lần chấm đầu: cặp "khỏe mạnh" bị judge cho NEEDS_REPAIR
    monkeypatch.setenv("FAKE_MODE", "good")
    monkeypatch.setenv("FAKE_FLAG_TEXT", "khỏe mạnh")
    args = argparse_ns(claude_cmd=f"{sys.executable} {FAKE_CLAUDE}", codex_cmd=f"{sys.executable} {FAKE}")
    assert sr.run(args) == 2  # chưa chấm -> từ chối repair
    assert sj.run(_args()) == 0
    monkeypatch.delenv("FAKE_FLAG_TEXT")
    assert sr.run(args) == 0
    res = sr.resolve(sj.load_config())
    st = dict(zip(res.answer_en, res.status))
    # trượt luật -> sửa nhưng bản sửa (giả) vẫn thiếu "mốc lá" -> UNRESOLVED, không sửa lần 2
    assert st["Diagnosis: Leaf Mold."] == "UNRESOLVED"
    assert st["This is a healthy plant leaf."] == "PASS_AFTER_REPAIR"  # judge NEEDS_REPAIR -> sửa -> đạt
    # câu hỏi dùng chung bị đổi: cặp anh em được chấm lại, vẫn đạt, dùng question_vi mới
    sib = res[res.answer_en == "The condition is identified as Late Blight."].iloc[0]
    assert sib.status == "PASS" and sib.rejudge == "PASS" and sib.question_vi == "Lá cà chua này có bệnh không?"
    s = sr.summary(res)
    assert s["questions_with_multiple_question_vi"] == 0 and s["pairs"]["UNRESOLVED"] == 1
    n = len(sj.read_jsonl(project / "runs/step3/repairs.jsonl"))
    assert sr.run(args) == 0 and len(sj.read_jsonl(project / "runs/step3/repairs.jsonl")) == n  # không sửa lần 2


def argparse_ns(**kw):
    import argparse
    d = dict(status=False, model=None, reasoning=None, claude_cmd=None, codex_cmd=None)
    d.update(kw)
    return argparse.Namespace(**d)

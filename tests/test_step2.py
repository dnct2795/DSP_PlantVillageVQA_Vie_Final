import json
import sys
from pathlib import Path

import pandas as pd
import pytest

from pvvqa import step2_translate as st
from pvvqa.common import ROOT
from pvvqa.step2_prepare import build_pairs, make_batches
from pvvqa.step2_rules import check_question, load_glossary

G = load_glossary(ROOT / "config" / "glossary.yaml")
FAKE = Path(__file__).with_name("fake_claude.py")


def synth():
    rows = []
    qs = [("Detailed Verification", "Is this Tomato leaf infected with Late blight?", ["Yes", "No"]),
          ("Specific Disease Identification", "What disease is this?",
           ["The condition is identified as Late Blight.", "This is a healthy plant leaf.",
            "Diagnosis: Leaf Mold."]),
          ("General Health Assessment", "Is this foliage completely symptom-free?", ["Yes", "No"])]
    k = 0
    for qt, q, answers in qs:
        for a in answers:
            for _ in range(3):
                rows.append({"qa_id": f"pvqa_{k:06d}", "question_type": qt, "question": q, "answer": a})
                k += 1
    return pd.DataFrame(rows)


def test_build_pairs_and_batches():
    sub = synth()
    pairs, qmap, questions = build_pairs(sub)
    assert len(pairs) == 7 and len(questions) == 3
    assert pairs.n_rows.sum() == len(sub) and qmap.qa_id.is_unique
    assert (pairs.answer_label == pairs.answer_en).all()
    assert pairs.is_yes_no.sum() == 4
    b = make_batches(pairs, max_pairs=2)
    # không câu hỏi nào bị tách giữa các batch
    seen = [q["question_key"] for x in b for q in x["questions"]]
    assert len(seen) == len(set(seen)) == 3
    assert sum(len(q["pairs"]) for x in b for q in x["questions"]) == 7


def _item(q, answers, qt="Detailed Verification"):
    return {"question_key": "q1", "question_type": qt, "question_en": q,
            "pairs": [{"pair_id": f"p{i}", "answer_en": a, "is_yes_no": a in ("Yes", "No")}
                      for i, a in enumerate(answers)]}


def test_rules_yes_no():
    item = _item("Is this Tomato leaf infected with Late blight?", ["Yes", "No"])
    good = {"question_key": "q1", "question_vi": "Lá cà chua này có bị nhiễm bệnh mốc sương không?",
            "pairs": [{"pair_id": "p0", "answer_vi": "Có"}, {"pair_id": "p1", "answer_vi": "Không"}]}
    assert check_question(item, good, G) == {"p0": [], "p1": []}
    bad = json.loads(json.dumps(good))
    bad["pairs"][0]["answer_vi"] = "Không"
    bad["question_vi"] = "Lá cà chua này bị nhiễm bệnh mốc sương, phải không?"
    r = check_question(item, bad, G)
    assert "yn_answer" in r["p0"] and "yn_tag" in r["p0"] and "yn_form" in r["p1"]


def test_rules_glossary_and_untranslated():
    item = _item("What disease is this?", ["The condition is identified as Late Blight."],
                 qt="Specific Disease Identification")
    out = {"question_key": "q1", "question_vi": "Đây là bệnh gì?",
           "pairs": [{"pair_id": "p0", "answer_vi": "Tình trạng được xác định là Late Blight."}]}
    r = check_question(item, out, G)["p0"]
    assert "gloss:Late blight" in r and "untranslated:late" in r
    out["pairs"][0]["answer_vi"] = "Tình trạng được xác định là bệnh mốc sương."
    assert check_question(item, out, G)["p0"] == []


def test_rules_keep_scientific_names():
    item = _item("What causes this?", ["This is Late Blight, caused by the oomycete Phytophthora infestans."],
                 qt="Causal Reasoning")
    out = {"question_key": "q1", "question_vi": "Nguyên nhân là gì?",
           "pairs": [{"pair_id": "p0", "answer_vi":
                      "Đây là bệnh mốc sương, do nấm noãn Phytophthora infestans gây ra."}]}
    assert check_question(item, out, G)["p0"] == []


def test_rules_missing_pair_and_orange_color():
    item = _item("Can you observe orange or brown raised lesions on this foliage?", ["Yes", "No"])
    out = {"question_key": "q1", "question_vi": "Có thể thấy vết bệnh nổi màu cam hoặc nâu trên lá này không?",
           "pairs": [{"pair_id": "p0", "answer_vi": "Có"}]}
    r = check_question(item, out, G)
    assert r["p0"] == [] and r["p1"] == ["missing_pair"]


@pytest.fixture
def project(tmp_path, monkeypatch):
    """Dựng một ROOT tạm với cấu hình, prompt, schema, glossary và batches giả."""
    root = tmp_path
    for d in ("config", "prompts", "schemas", "outputs/step2"):
        (root / d).mkdir(parents=True)
    for f in ("config/glossary.yaml", "prompts/translator.md", "schemas/translation.json"):
        (root / f).write_text((ROOT / f).read_text(encoding="utf-8"), encoding="utf-8")
    (root / "config/phase1.yaml").write_text(
        "paths: {step1_dir: outputs/step1}\nstep2:\n  out_dir: outputs/step2\n  run_dir: runs/step2\n"
        "  glossary: config/glossary.yaml\n  claude_cmd: [x]\n  timeout_s: 30\n", encoding="utf-8")
    pairs, _, _ = build_pairs(synth())
    with open(root / "outputs/step2/batches.jsonl", "w", encoding="utf-8") as f:
        for b in make_batches(pairs, max_pairs=3):
            f.write(json.dumps(b) + "\n")
    monkeypatch.setattr(st, "ROOT", root)
    import pvvqa.common as common
    monkeypatch.setattr(common, "ROOT", root)
    monkeypatch.setattr(st, "load_config",
                        lambda: common.load_config(root / "config/phase1.yaml"))
    return root


def _args(**kw):
    import argparse
    d = dict(pilot=None, batches=None, max_batches=None, status=False, dry_run=False, recheck=False,
             claude_cmd=f"{sys.executable} {FAKE}")
    d.update(kw)
    return argparse.Namespace(**d)


def test_runner_resume_and_idempotent(project, monkeypatch):
    monkeypatch.setenv("FAKE_MODE", "good")
    assert st.run(_args()) == 0
    recs = st.read_jsonl(project / "runs/step2/translations.jsonl")
    assert len(recs) == 7 and all(r["error"] is None for r in recs)
    # cùng câu hỏi -> cùng question_vi
    qv = {}
    for r in recs:
        qv.setdefault(r["question_key"], set()).add(r["question_vi"])
    assert all(len(v) == 1 for v in qv.values())
    assert st.run(_args()) == 0  # chạy lại: không gọi model, không thêm dòng
    assert len(st.read_jsonl(project / "runs/step2/translations.jsonl")) == 7
    log = st.read_jsonl(project / "runs/step2/run_log.jsonl")
    assert log[-1]["pairs_translated"] == 7 and log[-1]["batches_planned"] == 0


def test_runner_quota_stops_cleanly_then_resumes(project, monkeypatch, tmp_path):
    monkeypatch.setenv("FAKE_MODE", "quota_after_1")
    monkeypatch.setenv("FAKE_COUNTER", str(tmp_path / "count"))
    assert st.run(_args()) == 3
    log = st.read_jsonl(project / "runs/step2/run_log.jsonl")[-1]
    assert log["stop_reason"].startswith("quota") and 0 < log["pairs_translated"] < 7
    monkeypatch.setenv("FAKE_MODE", "good")
    assert st.run(_args()) == 0
    assert st.status(project / "runs/step2",
                     st.read_jsonl(project / "outputs/step2/batches.jsonl"))["pairs_translated"] == 7


def test_runner_incomplete_question_is_retried(project, monkeypatch):
    monkeypatch.setenv("FAKE_MODE", "drop_pair")
    st.run(_args())
    s = st.status(project / "runs/step2", st.read_jsonl(project / "outputs/step2/batches.jsonl"))
    assert s["pairs_error_pending"] > 0  # câu hỏi thiếu cặp -> cả câu hỏi chờ thử lại
    monkeypatch.setenv("FAKE_MODE", "good")
    st.run(_args())
    s = st.status(project / "runs/step2", st.read_jsonl(project / "outputs/step2/batches.jsonl"))
    assert s["pairs_translated"] == 7 and s["pairs_error_pending"] == 0


def test_runner_broken_output_stops_after_3(project, monkeypatch):
    monkeypatch.setenv("FAKE_MODE", "broken")
    assert st.run(_args()) == 3
    log = st.read_jsonl(project / "runs/step2/run_log.jsonl")[-1]
    assert "liên tiếp" in log["stop_reason"] and log["pairs_translated"] == 0


def test_rules_abbreviation_only_when_source_uses_it():
    item = _item("What is this?", ["This tomato leaf shows classic signs of TYLCV."],
                 qt="Causal Reasoning")
    out = {"question_key": "q1", "question_vi": "Đây là gì?",
           "pairs": [{"pair_id": "p0", "answer_vi": "Lá cà chua này có dấu hiệu điển hình của TYLCV."}]}
    assert check_question(item, out, G)["p0"] == []
    # EN có tên đầy đủ -> VI vẫn phải có tên tiếng Việt, chỉ viết tắt thì trượt
    item["pairs"][0]["answer_en"] = "This leaf shows Tomato Yellow Leaf Curl Virus (TYLCV)."
    assert "gloss:Tomato Yellow Leaf Curl Virus (TYLCV)" in check_question(item, out, G)["p0"]


def test_rules_tag_question_without_comma():
    item = _item("Are both stress and disease indicators absent?", ["Yes", "No"],
                 qt="General Health Assessment")
    out = {"question_key": "q1",
           "question_vi": "Cả dấu hiệu căng thẳng lẫn dấu hiệu bệnh đều không có phải không?",
           "pairs": [{"pair_id": "p0", "answer_vi": "Có"}, {"pair_id": "p1", "answer_vi": "Không"}]}
    assert "yn_tag" in check_question(item, out, G)["p0"]
    out["question_vi"] = "Lá có hoàn toàn không có cả dấu hiệu căng thẳng lẫn dấu hiệu bệnh không?"
    assert check_question(item, out, G)["p0"] == []
    out["question_vi"] = "Nhận định lá này bị bệnh có đúng không?"  # dạng "có … không?", hợp lệ
    assert "yn_tag" not in check_question(item, out, G)["p0"]


def test_recheck_appends_without_calling_model(project, monkeypatch):
    monkeypatch.setenv("FAKE_MODE", "good")
    assert st.run(_args()) == 0
    trans = project / "runs/step2/translations.jsonl"
    recs = st.read_jsonl(trans)
    i = next(k for k, r in enumerate(recs) if r["rule_pass"])
    recs[i]["rule_errors"], recs[i]["rule_pass"] = ["gloss:stale"], False  # kết quả luật cũ
    trans.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in recs), encoding="utf-8")
    monkeypatch.setenv("FAKE_MODE", "broken")  # nếu gọi model thì sẽ hỏng
    assert st.run(_args(recheck=True)) == 0
    after = st.read_jsonl(trans)
    assert len(after) == 8 and after[-1]["pair_id"] == recs[i]["pair_id"]
    assert after[-1]["rule_pass"] and after[-1]["question_vi"] == recs[i]["question_vi"]
    assert st.run(_args(recheck=True)) == 0 and len(st.read_jsonl(trans)) == 8  # idempotent


def test_quota_pattern_matches_session_limit():
    assert st.QUOTA_PAT.search("You've hit your session limit · resets 9:10pm (Asia/Saigon)")
    assert not st.QUOTA_PAT.search("claude exited 1")

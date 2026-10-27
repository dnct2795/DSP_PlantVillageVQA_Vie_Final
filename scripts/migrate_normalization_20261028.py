"""Chuyển tiếp một lần (2026-10-28): đưa chuẩn hoá thuật ngữ về Step 2 (bước 2.5).

Bối cảnh: chuẩn hoá viết tắt HLB/TYLCV/ToMV ban đầu được chạy sau Step 3 (module step3_expand, đã bỏ);
các cặp bị đổi đã được Codex chấm lại trên đúng văn bản đã chuẩn hoá (runs/step3/expansion_judgments.jsonl).
Sau khi đưa chuẩn hoá về Step 2 (`step2_translate --recheck` đã ghi bản dịch chuẩn hoá), script này ghi thêm
(append-only, có trường `carried_from`) các kết quả chấm đó vào đúng vị trí trong pipeline:
  - cặp không thuộc diện sửa: lần chấm trên văn bản chuẩn hoá -> judgments.jsonl (kết quả 3.2);
  - cặp đã sửa ở 3.3: bản sửa chuẩn hoá -> repairs.jsonl, lần chấm -> rejudgments.jsonl;
  - câu hỏi dùng chung bị đổi ở 3.3: question_vi chuẩn hoá -> question_updates.jsonl.
Mỗi kết quả chỉ được dùng nếu văn bản đã chấm trùng khớp từng ký tự với văn bản hiện tại. Không xoá gì.
  PYTHONPATH=src python scripts/migrate_normalization_20261028.py
"""
import json
import sys

from pvvqa.common import ROOT, load_config
from pvvqa.step2_rules import normalize_terms
from pvvqa.step2_translate import append_jsonl, now, read_jsonl
from pvvqa.step3_judge import latest_valid, load_translations


def latest(path, key="pair_id"):
    out = {}
    for r in read_jsonl(path):
        out[r[key]] = r
    return out


def main() -> int:
    cfg = load_config()
    rd = ROOT / cfg["step3"]["run_dir"]
    if any(r.get("carried_from") for r in read_jsonl(rd / "judgments.jsonl")):
        print("Đã chuyển tiếp trước đó, không làm lại.")
        return 0
    df = load_translations(cfg).set_index("pair_id")  # bản dịch Step 2 đã chuẩn hoá (2.5)
    exp = latest(rd / "expansions.jsonl")
    ej = latest_valid(rd / "expansion_judgments.jsonl")
    repairs = {k: r for k, r in latest(rd / "repairs.jsonl").items() if not r.get("error")}
    ts, tag = now(), "expansion_judgments"
    jrows, rrows, rjrows, mism = [], [], [], []
    for pid, e in exp.items():
        j = ej.get(pid)
        if pid in repairs:
            rp = repairs[pid]
            text = (normalize_terms(rp["question_vi"]), normalize_terms(rp["answer_vi"]))
            if text != (e["question_vi"], e["answer_vi"]):
                mism.append(pid)
                continue
            rrows.append({**rp, "question_vi": text[0], "answer_vi": text[1], "rule_errors": e["rule_errors"],
                          "rule_pass": not e["rule_errors"], "normalized": True, "ts": ts,
                          "carried_from": "expansions"})
            if j:
                rjrows.append({**j, "ts": ts, "carried_from": tag})
        else:
            cur = (df.loc[pid, "question_vi"], df.loc[pid, "answer_vi"])
            if cur != (e["question_vi"], e["answer_vi"]):
                mism.append(pid)
                continue
            if j:
                jrows.append({**j, "ts": ts, "carried_from": tag})
    qrows = []
    for qk, u in latest(rd / "question_updates.jsonl", key="question_key").items():
        nq = normalize_terms(u["new_question_vi"])
        if nq != u["new_question_vi"]:
            qrows.append({**u, "new_question_vi": nq, "ts": ts, "carried_from": "normalization"})
    if mism:
        print(f"DỪNG: {len(mism)} cặp có văn bản không khớp, ví dụ {mism[:5]}. Không ghi gì.")
        return 1
    append_jsonl(rd / "judgments.jsonl", jrows)
    append_jsonl(rd / "repairs.jsonl", rrows)
    append_jsonl(rd / "rejudgments.jsonl", rjrows)
    append_jsonl(rd / "question_updates.jsonl", qrows)
    print(json.dumps({"judgments_carried": len(jrows), "repairs_normalized": len(rrows),
                      "rejudgments_carried": len(rjrows), "question_updates_normalized": len(qrows),
                      "needs_repair_now": sum(r["verdict"] != "PASS" for r in jrows)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())

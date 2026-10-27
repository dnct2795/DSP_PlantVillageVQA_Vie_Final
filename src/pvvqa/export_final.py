"""Đầu ra cuối: dataset tiếng Việt (cùng cấu trúc dataset gốc), bản đối chiếu EN–VI, quality report.

Chạy sau Step 3 (không gọi model):
  PYTHONPATH=src python -m pvvqa.export_final

Ghi vào outputs/final/:
  PlantVillageVQA_vi.csv     cùng cột, cùng thứ tự cột với PlantVillageVQA.csv gốc:
                             image_id, question_type, question, answer, image_path, split
                             (question/answer tiếng Việt; các cột khác giữ nguyên giá trị gốc).
                             Chỉ gồm PASS + PASS_AFTER_REPAIR (silver-standard tự động).
  PlantVillageVQA_vi.json    cùng cấu trúc PlantVillageVQA.json gốc:
                             {image_id: {image_path, split, questions: [{question_type, question, answer}]}}
  PlantVillageVQA_vi_en_alignment.csv   mọi dòng subset (kể cả UNRESOLVED) với qa_id, EN, VI,
                             answer_label, pair_id, status, kết quả judge, log repair.
  quality_report.md / .json, manifest.json (sha256 các file).
"""
from __future__ import annotations

import hashlib
import json
import sys

import pandas as pd

from pvvqa.common import ROOT, load_config
from pvvqa.step2_translate import git_commit, now, read_jsonl
from pvvqa.step3_judge import latest_valid
from pvvqa.step3_repair import _latest, resolve, summary

SOURCE_COLS = ["image_id", "question_type", "question", "answer", "image_path", "split"]
TRAINABLE = {"PASS", "PASS_AFTER_REPAIR"}


def build_rows(cfg: dict) -> pd.DataFrame:
    """Một dòng mỗi QA của subset, kèm bản dịch cuối, trạng thái và vết judge/repair."""
    run_dir = ROOT / cfg["step3"]["run_dir"]
    sub = pd.read_parquet(ROOT / cfg["paths"]["step1_dir"] / "subset_en.parquet")
    qmap = pd.read_parquet(ROOT / cfg["step2"]["out_dir"] / "pair_qa_map.parquet")
    res = resolve(cfg)
    judged = latest_valid(run_dir / "judgments.jsonl")
    rejudged = latest_valid(run_dir / "rejudgments.jsonl")
    repairs = {k: r for k, r in _latest(run_dir / "repairs.jsonl").items() if not r.get("error")}

    def js(x):
        return json.dumps(x, ensure_ascii=False) if x else ""

    trace = pd.DataFrame([{
        "pair_id": pid,
        "rule_errors_step2": js(res_r.rule_errors),
        "judge_errors": js((judged.get(pid) or {}).get("errors")),
        "repair_feedback": js((repairs.get(pid) or {}).get("feedback")),
        "pre_repair_question_vi": (repairs.get(pid) or {}).get("old_question_vi", ""),
        "pre_repair_answer_vi": (repairs.get(pid) or {}).get("old_answer_vi", ""),
        "rejudge_errors": js((rejudged.get(pid) or {}).get("errors")),
    } for pid, res_r in zip(res.pair_id, res.itertuples())])
    res = res.merge(trace, on="pair_id")
    keep = ["pair_id", "answer_label", "question_vi", "answer_vi", "status", "judge_first", "repaired",
            "rejudge", "rule_errors_step2", "judge_errors", "repair_feedback", "pre_repair_question_vi",
            "pre_repair_answer_vi", "rejudge_errors"]
    rows = (sub.merge(qmap, on="qa_id", how="left").merge(res[keep], on="pair_id", how="left")
            .sort_values("source_row").reset_index(drop=True))
    assert len(rows) == len(sub) and rows.pair_id.notna().all() and rows.status.notna().all()
    return rows


def to_source_json(df: pd.DataFrame) -> dict:
    out = {}
    for r in df.itertuples():  # df đã theo thứ tự source_row
        img = out.setdefault(r.image_id, {"image_path": r.image_path, "split": r.split, "questions": []})
        img["questions"].append({"question_type": r.question_type, "question": r.question, "answer": r.answer})
    return out


def strata(cfg: dict, vi: pd.DataFrame) -> pd.DataFrame:
    t = pd.read_csv(ROOT / cfg["paths"]["step1_dir"] / "strata.csv")[["split", "question_type", "N_h", "n_h"]]
    v = vi.groupby(["split", "question_type"]).size().rename("n_vi").reset_index()
    t = t.merge(v, on=["split", "question_type"], how="left").fillna({"n_vi": 0})
    t["n_vi"] = t.n_vi.astype(int)
    t["lost"] = t.n_h - t.n_vi
    for c, tot in (("N_h", t.N_h.sum()), ("n_h", t.n_h.sum()), ("n_vi", max(t.n_vi.sum(), 1))):
        t[f"{c}_pct"] = (t[c] / tot * 100).round(3)
    return t


def usage(run_dir) -> dict:
    out = {"input_tokens": 0, "output_tokens": 0, "model_elapsed_s": 0.0}
    for r in read_jsonl(run_dir / "run_log.jsonl"):
        out["input_tokens"] += r.get("usage_input_tokens", 0) + r.get("rejudge_usage_input_tokens", 0)
        out["output_tokens"] += r.get("usage_output_tokens", 0) + r.get("rejudge_usage_output_tokens", 0)
        out["model_elapsed_s"] += r.get("model_elapsed_s", 0) + r.get("rejudge_model_elapsed_s", 0)
    out["model_elapsed_s"] = round(out["model_elapsed_s"], 1)
    return out


def report(cfg: dict, rows: pd.DataFrame, res_sum: dict, st: pd.DataFrame) -> tuple[dict, str]:
    src = json.loads((ROOT / cfg["paths"]["step1_dir"] / "source_report.json").read_text())
    s3 = cfg["step3"]
    out3 = ROOT / "outputs" / "step3"
    tag = f"{s3['judge_model']}__{s3['judge_reasoning']}"
    smoke = json.loads((out3 / f"smoke_report__{tag}.json").read_text())
    cross = {p.stem.replace("crosscheck_report__", ""): json.loads(p.read_text())
             for p in sorted(out3.glob("crosscheck_report__*.json"))}
    repaired_same = int(((rows.status == "PASS_AFTER_REPAIR") & (rows.pre_repair_question_vi == rows.question_vi)
                         & (rows.pre_repair_answer_vi == rows.answer_vi)).groupby(rows.pair_id).first().sum())
    rep = {
        "generated": now(), "git_commit": git_commit(),
        "source": {"repo_id": src["repo_id"], "revision": src["revision_sha"], "qa_file": src["qa_file"],
                   "rows": int(st.N_h.sum()), "splits": sorted(st.split.unique().tolist()),
                   "columns": SOURCE_COLS},
        "subset": {"fraction": cfg["sampling"]["fraction"], "seed": cfg["sampling"]["seed"],
                   "rows": int(st.n_h.sum()), "pairs": int(rows.pair_id.nunique())},
        "status": res_sum, "repaired_without_text_change_pairs": repaired_same,
        "smoke_test": smoke, "crosscheck": cross,
        "usage": {"step2_claude": usage(ROOT / cfg["step2"]["run_dir"]), "step3_all": usage(ROOT / s3["run_dir"])},
        "final_rows_trainable": int(rows.status.isin(TRAINABLE).sum()),
    }
    p, r = res_sum["pairs"], res_sum["rows"]
    tot_p, tot_r = sum(p.values()), sum(r.values())
    L = ["# Quality report — PlantVillageVQA tiếng Việt (Phase 1)", "",
         f"Tạo lúc {rep['generated']}, commit `{rep['git_commit']}`.", "",
         "## 1. Nguồn", "",
         f"- HF `{src['repo_id']}`, revision `{src['revision_sha']}`, file QA `{src['qa_file']}`.",
         f"- {rep['source']['rows']:,} dòng QA; split thực tế: {', '.join(rep['source']['splits'])} (không có val).",
         f"- Cột: `{', '.join(SOURCE_COLS)}` — dataset tiếng Việt giữ đúng các cột và thứ tự này.", "",
         "## 2. Phân phối split × question_type", "",
         f"Subset: lấy mẫu phân tầng tỷ lệ {cfg['sampling']['fraction']:.1%}, seed {cfg['sampling']['seed']}.", "",
         "| split | question_type | gốc | % | subset EN | % | VI cuối | % | mất |", "|---|---|---|---|---|---|---|---|---|"]
    for t in st.itertuples():
        L.append(f"| {t.split} | {t.question_type} | {t.N_h:,} | {t.N_h_pct:.3f} | {t.n_h:,} | {t.n_h_pct:.3f} | "
                 f"{t.n_vi:,} | {t.n_vi_pct:.3f} | {t.lost} |")
    L.append(f"| **tổng** | | **{st.N_h.sum():,}** | | **{st.n_h.sum():,}** | | **{st.n_vi.sum():,}** | | "
             f"**{st.lost.sum()}** |")
    L += ["", "## 3. Trạng thái kiểm định", "",
          "| trạng thái | cặp | % cặp | dòng | % dòng |", "|---|---|---|---|---|"]
    for k in ("PASS", "PASS_AFTER_REPAIR", "UNRESOLVED"):
        L.append(f"| {k} | {p.get(k, 0):,} | {p.get(k, 0) / tot_p:.2%} | {r.get(k, 0):,} | {r.get(k, 0) / tot_r:.2%} |")
    L += ["", f"- PASS = qua kiểm tra luật và judge không thấy lỗi major/critical ở lần chấm đầu.",
          f"- PASS_AFTER_REPAIR = trượt luật hoặc bị judge đánh NEEDS_REPAIR, Claude sửa đúng một lần, "
          f"qua luật và judge chấm lại PASS. Trong đó {repaired_same} cặp không đổi chữ nào sau repair "
          "nhưng lần chấm lại cho PASS (xem mục 6).",
          "- Chỉ PASS + PASS_AFTER_REPAIR có trong `PlantVillageVQA_vi.csv/.json`; mọi dòng (kể cả UNRESOLVED) "
          "có trong `PlantVillageVQA_vi_en_alignment.csv`.", "",
          "## 4. Tính nhất quán câu hỏi", "",
          f"- Số câu hỏi EN có nhiều hơn một `question_vi`: **{res_sum['questions_with_multiple_question_vi']}** "
          "(mục tiêu 0).", "",
          f"## 5. Smoke test judge (`{s3['judge_model']}`, reasoning `{s3['judge_reasoning']}`)", "",
          "Mục cố ý sai sinh tự động bằng thay chuỗi trên bản dịch đã qua luật. **Không phải hiệu chuẩn.**", ""]
    for k, v in smoke.items():
        L.append(f"- {k}: " + (f"báo nhầm {v['false_alarm']}/{v['n']}" if k == "control"
                               else f"Codex bắt được {v['caught']}/{v['n']}"))
    for k, v in cross.items():
        L += ["", f"Kiểm tra chéo với `{k.replace('__', ' ')}` trên {v['n']} cặp ngẫu nhiên: đồng ý verdict "
              f"{v['agree']}/{v['n']}; judge chính PASS nhưng model đối chiếu NEEDS_REPAIR: "
              f"{v['main_pass_other_needs_repair']}; ngược lại: {v['main_needs_repair_other_pass']}. "
              "Vì tỷ lệ NEEDS_REPAIR thật chỉ ~0,2%, mẫu gần như toàn PASS: kết quả chỉ cho thấy model đối chiếu "
              f"không tìm thêm lỗi major mà judge chính bỏ sót (tỷ lệ bỏ sót < ~{3 / max(v['n'], 1):.1%}, "
              "độ tin cậy 95%, quy tắc 3/n), không đo được độ nhạy với lỗi."]
    L += ["", "## 6. Giới hạn", "",
          "- Codex (một model) là lớp đánh giá ngữ nghĩa duy nhất; chưa hiệu chuẩn với người chấm. Nhãn chất "
          "lượng là *automatically validated silver-standard*, không phải đã được người kiểm định.",
          "- Judge không ổn định ở ca ranh giới: cùng một bản dịch có thể bị chấm NEEDS_REPAIR lần đầu và PASS "
          "khi chấm lại.",
          "- Dữ liệu gốc sinh từ template: câu hỏi/câu trả lời lặp nhiều, độ đa dạng ngôn ngữ thấp. Có lỗi template "
          "ở nguồn (ví dụ 3 câu hỏi dạng \"What …?\" nhưng đáp án Yes/No); bản dịch giữ đúng đáp án gốc.",
          "- Mất cân bằng lớp thừa hưởng từ PlantVillage (HLB trên cam và TYLCV trên cà chua chiếm khoảng 35% "
          "số dòng); subset giữ nguyên phân phối này.",
          "- Subset 12,5% theo dòng: còn khoảng 50% số cặp QA duy nhất của nguồn, mỗi ảnh trung bình ~1,3 câu hỏi.",
          "- Lỗi minor (chủ yếu độ trôi chảy) không được sửa theo thiết kế.", "",
          "## Chi phí (gói Claude Pro / ChatGPT Plus, không dùng API trả phí)", "",
          *[f"- {name}: {u['input_tokens']:,} token vào, {u['output_tokens']:,} token ra, "
            f"{u['model_elapsed_s'] / 60:.0f} phút model"
            for name, u in (("Step 2 (Claude Sonnet)", rep["usage"]["step2_claude"]),
                            ("Step 3 (Codex judge, smoke test, kiểm tra chéo, Claude repair, chấm lại)",
                             rep["usage"]["step3_all"]))]]
    return rep, "\n".join(L) + "\n"


def sha256(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    cfg = load_config()
    out = ROOT / "outputs" / "final"
    out.mkdir(parents=True, exist_ok=True)
    rows = build_rows(cfg)
    vi = rows[rows.status.isin(TRAINABLE)].copy()
    vi["question"], vi["answer"] = vi.question_vi, vi.answer_vi
    vi[SOURCE_COLS].to_csv(out / "PlantVillageVQA_vi.csv", index=False, encoding="utf-8")
    (out / "PlantVillageVQA_vi.json").write_text(
        json.dumps(to_source_json(vi[SOURCE_COLS]), ensure_ascii=False, indent=2), encoding="utf-8")
    align = rows.rename(columns={"question": "question_en", "answer": "answer_en"})
    align_cols = ["qa_id", "source_row", "image_id", "image_path", "split", "question_type", "question_en",
                  "answer_en", "question_vi", "answer_vi", "answer_label", "pair_id", "status",
                  "rule_errors_step2", "judge_first", "judge_errors", "repaired", "repair_feedback",
                  "pre_repair_question_vi", "pre_repair_answer_vi", "rejudge", "rejudge_errors"]
    align[align_cols].to_csv(out / "PlantVillageVQA_vi_en_alignment.csv", index=False, encoding="utf-8")
    res_sum = summary(resolve(cfg))
    rep, md = report(cfg, rows, res_sum, strata(cfg, vi))
    (out / "quality_report.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "quality_report.md").write_text(md, encoding="utf-8")
    files = ["PlantVillageVQA_vi.csv", "PlantVillageVQA_vi.json", "PlantVillageVQA_vi_en_alignment.csv",
             "quality_report.md", "quality_report.json"]
    manifest = {"generated": rep["generated"], "git_commit": rep["git_commit"],
                "source_revision": rep["source"]["revision"],
                "files": {f: {"sha256": sha256(out / f), "bytes": (out / f).stat().st_size} for f in files},
                "rows_vi": len(vi), "rows_alignment": len(rows)}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    print(json.dumps({"rows_vi": len(vi), "rows_alignment": len(rows), **res_sum}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())

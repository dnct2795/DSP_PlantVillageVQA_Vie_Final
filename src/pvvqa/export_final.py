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
         "## Pipeline (một lần chạy, tự động hoàn toàn, có checkpoint)", "",
         "1. **Step 1 — Lấy mẫu đại diện:** phân tầng tỷ lệ theo `split × question_type`, 12,5%, seed 42.",
         "2. **Step 2 — Dịch EN→VI theo ngữ cảnh (Claude Sonnet):** 2.1 gom cặp QA trùng; 2.2 glossary cố định "
         "(tên khoa học giữ nguyên; viết tắt HLB/TYLCV/ToMV dịch thành tên tiếng Việt đầy đủ); 2.3 dịch theo batch "
         "câu hỏi, một `question_vi` dùng chung cho mỗi câu hỏi EN, quy tắc Yes/No; 2.5 chuẩn hoá thuật ngữ theo "
         "glossary bằng luật (thay viết tắt còn sót bằng tên tiếng Việt đầy đủ); 2.6 kiểm tra bằng luật.",
         f"3. **Step 3 — Đánh giá độc lập và sửa chọn lọc:** 3.1 smoke test judge; 3.2 Codex `{s3['judge_model']}` "
         f"(reasoning `{s3['judge_reasoning']}`) chấm mọi cặp qua luật (lỗi kiểu MQM); 3.3 Claude sửa đúng một lần "
         "các cặp trượt luật hoặc NEEDS_REPAIR (bản sửa cũng qua 2.5 và 2.6), rồi chấm lại.",
         "- Lần chạy bị ngắt (hết quota, lỗi gọi model) được chạy tiếp từ checkpoint. Thứ tự thực thi thực tế và "
         "mọi lần chấm được lưu trong `runs/` và `PROGRESS.md`.", "",
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
          "- UNRESOLVED = không đạt sau repair; không sửa thêm, không thay mẫu.",
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
    L += ["", "## 6. Giới hạn", ""] + limitations(rows) + ["",
          "## Chi phí (gói Claude Pro / ChatGPT Plus, không dùng API trả phí)", "",
          *[f"- {name}: {u['input_tokens']:,} token vào, {u['output_tokens']:,} token ra, "
            f"{u['model_elapsed_s'] / 60:.0f} phút model"
            for name, u in (("Step 2 (Claude Sonnet)", rep["usage"]["step2_claude"]),
                            ("Step 3 (Codex judge, smoke test, kiểm tra chéo, Claude repair, chấm lại)",
                             rep["usage"]["step3_all"]))]]
    return rep, "\n".join(L) + "\n"


# Số liệu đo trên nguồn (revision đã ghim, không đổi): đa dạng ngôn ngữ và lỗi template.
SOURCE_FACTS = {"rows": 193609, "questions": 1213, "answers": 125, "pairs": 15065, "no": 48453, "yes": 33091,
                "singleton_pairs": 2227, "test_pairs_in_train": 0.982, "qa_per_image": 3.87,
                "what_yesno_rows": 434,
                "what_yesno": {"What disease indicators appear on this vegetation?": (104, 28),
                               "What pathological signs are visible on this leaf specimen?": (135, 13),
                               "What symptomatic characteristics are present here?": (131, 23)}}


def limitations(rows: pd.DataFrame) -> list[str]:
    """Mục 6 của quality report: mỗi giới hạn gồm vấn đề, số liệu, ảnh hưởng, cách xử lý / khuyến nghị."""
    F = SOURCE_FACTS
    keep = rows[rows.status.isin(TRAINABLE)]
    # 2. lỗi minor còn lại: lần chấm quyết định trạng thái (lần đầu cho PASS, chấm lại cho PASS_AFTER_REPAIR)
    errs = keep.rejudge_errors.where(keep.status == "PASS_AFTER_REPAIR", keep.judge_errors)
    has = keep[errs.astype(bool)]
    by_pair = errs[errs.astype(bool)].groupby(has.pair_id).first()
    cat_counts = pd.Series([e["category"] for x in by_pair for e in json.loads(x)]).value_counts()
    # 4. câu hỏi "What …?" có đáp án Yes/No
    w = keep[keep.question.str.match(r"^(What|Which)\b") & keep.answer.isin(["Yes", "No"])]
    # 5. ảnh hưởng của lấy mẫu theo dòng
    tr, te = keep[keep.split == "train"], keep[keep.split == "test"]
    q_in = te.question.isin(set(tr.question)).mean()
    p_in = pd.Series(list(zip(te.question, te.answer))).isin(set(zip(tr.question, tr.answer))).mean()
    n_img = keep.image_id.nunique()
    L = ["Mỗi mục ghi vấn đề, số liệu, ảnh hưởng và cách xử lý hoặc khuyến nghị.", "",
         "### 6.1 Kiểm định tự động, chưa có người kiểm tra", "",
         "- Dữ liệu là *automatically validated silver-standard*: Codex là lớp đánh giá ngữ nghĩa duy nhất, chưa "
         "hiệu chuẩn với người chấm. Không gọi là \"đã được người kiểm định\".",
         "- Bằng chứng đã có: smoke test (mục 5) và kiểm tra chéo với một model mạnh hơn. Mẫu kiểm tra chéo gần như "
         "toàn PASS nên chỉ chặn trên tỷ lệ bỏ sót lỗi nặng, không đo được độ nhạy với lỗi tinh tế.",
         "- Judge không ổn định ở ca ranh giới: cùng một bản dịch có thể bị NEEDS_REPAIR lần này và PASS lần khác. "
         "Ví dụ \"… hay còn gọi là bệnh vàng rồng cây có múi\" bị đánh lỗi ở 3 cặp nhưng PASS ở 1 cặp khác "
         "(cặp đó vẫn còn trong dataset).",
         "- Khuyến nghị: cho người chấm một mẫu ngẫu nhiên (ví dụ 200 cặp) để ước lượng tỷ lệ lỗi thật.", "",
         "### 6.2 Lỗi minor không được sửa", "",
         "- Theo thiết kế, PASS = không có lỗi major/critical; cặp chỉ có lỗi minor (nghĩa vẫn đúng, văn phong chưa "
         "mượt) giữ nguyên, không đi sửa.",
         f"- Dataset cuối còn **{len(by_pair):,} cặp / {len(has):,} dòng** có lỗi minor: " + ", ".join(f"{k} {v}" for k, v in cat_counts.items()) + ".",
         "- Ví dụ: \"đốm lốm đốm\" (cho *stippling*) lặp từ; câu hỏi tự thêm \"trên lá\"; \"chẩn đoán chắc chắn\" "
         "cho *authoritative diagnosis*.",
         "- Lý do: nghĩa vẫn đúng; dịch lại có thể sinh lỗi mới; giữ pipeline đơn giản. Mọi lỗi minor nằm ở cột "
         "`judge_errors` / `rejudge_errors` của bản đối chiếu.", "",
         "### 6.3 Dữ liệu gốc sinh từ template, độ đa dạng ngôn ngữ thấp", "",
         f"- Nguồn có {F['rows']:,} dòng nhưng chỉ **{F['questions']:,} câu hỏi** và **{F['answers']} câu trả lời** "
         f"khác nhau; \"No\" lặp {F['no']:,} lần, \"Yes\" {F['yes']:,} lần; bệnh mốc sương ở câu nhận diện bệnh chỉ "
         "có 4 cách nói, mỗi cách lặp khoảng 720 lần.",
         "- Ảnh hưởng: model dễ đoán theo mẫu câu mà không nhìn ảnh, và có thể lúng túng với câu hỏi tự nhiên của người "
         "dùng thật. Bản tiếng Việt dịch sát nguồn nên giữ nguyên tính lặp này.",
         "- Cách đo: 3 bộ test ablation (blank, noimage, shuffled) cho biết model dựa vào câu hỏi đến đâu.", "",
         "### 6.4 Lỗi template trong nguồn: câu hỏi \"What …?\" có đáp án Yes/No", "",
         f"- File gốc có 3 câu hỏi dạng hỏi mở nhưng được trả lời Yes/No, tổng {F['what_yesno_rows']} dòng (đều là "
         "General Health Assessment). Ví dụ dòng 224: `image_000088.JPG`, *\"What disease indicators appear on this "
         "vegetation?\"* → \"Yes\".", "",
         "| Câu hỏi gốc | Yes (nguồn) | No (nguồn) | Dòng trong dataset VI | Bản dịch |", "|---|---|---|---|---|"]
    for q, (y, n) in F["what_yesno"].items():
        g = w[w.question == q]
        L.append(f"| {q} | {y} | {n} | {len(g)} | {g.question_vi.iloc[0] if len(g) else ''} |")
    L += ["",
          "- Nguyên nhân có lẽ (phỏng đoán, paper không nói rõ): khi diễn đạt lại mẫu câu Yes/No, một vài câu bị đổi "
          "thành dạng \"What …?\" nhưng đáp án vẫn giữ nguyên.",
          "- Cách xử lý: giữ đúng nhãn gốc, dịch câu hỏi sang dạng \"… có … nào không?\" cho khớp đáp án Có/Không. Bản "
          "tiếng Việt tự nhiên hơn bản gốc nhưng không sát từng chữ với câu EN; đây là lý do một số cặp "
          "PASS_AFTER_REPAIR không đổi chữ nào sau bước sửa.", "",
          "### 6.5 Ảnh hưởng của việc lấy mẫu 12,5% theo dòng", "",
          "| | Gốc | Dataset VI |", "|---|---|---|",
          f"| QA trên mỗi ảnh | {F['qa_per_image']:.2f} | {len(keep) / n_img:.2f} |",
          f"| Cặp QA duy nhất | {F['pairs']:,} | {keep.pair_id.nunique():,} |",
          f"| Cặp hỏi–đáp test đã có y hệt trong train | {F['test_pairs_in_train']:.1%} | {p_in:.1%} |",
          f"| Câu hỏi test đã có trong train | 100% | {q_in:.1%} |", "",
          f"- Cặp bị mất chủ yếu là cặp hiếm ({F['singleton_pairs']:,} cặp chỉ xuất hiện 1 lần trong nguồn).",
          f"- Khoảng {1 - p_in:.0%} cặp trong test có câu trả lời (thường là câu mở) chưa xuất hiện y hệt trong train. "
          "Khuyến nghị: chấm câu trả lời mở bằng độ tương đồng (BLEU, ROUGE, BERTScore) hoặc theo ý chính (tên bệnh, "
          "tên cây), không dùng so khớp chính xác. Câu Yes/No không bị ảnh hưởng.",
          f"- Mỗi ảnh ~{len(keep) / n_img:.1f} câu hỏi: đổi lại có {n_img:,} ảnh khác nhau (lấy mẫu theo ảnh chỉ được "
          f"khoảng {round(len(keep) / F['qa_per_image']):,}), có lợi cho học hình ảnh. Hạn chế: không phân tích được "
          "tính nhất quán của model trên nhiều câu hỏi cùng một ảnh.", "",
          "### 6.6 Mất cân bằng lớp và không có tập validation", "",
          "- Mất cân bằng thừa hưởng từ PlantVillage: bệnh vàng lá gân xanh trên cam và virus xoăn vàng lá cà chua "
          "chiếm khoảng 35% số dòng; một số tổ hợp cây/bệnh hiếm chỉ còn vài đến vài chục dòng. Subset giữ đúng phân "
          "phối này vì mục tiêu là đại diện.",
          "- Nguồn chỉ có train/test (README nhắc tới val nhưng dữ liệu không có). Khi cần val, tách từ train **theo "
          "ảnh** (không theo dòng) để một ảnh không nằm ở cả train và val."]
    return L


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

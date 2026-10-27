# DSP391 — PlantVillageVQA Vietnamese (Phase 1: dataset construction)

This repository builds a **Vietnamese plant-pathology VQA dataset** from
[PlantVillageVQA](https://huggingface.co/datasets/SyedNazmusSakib/PlantVillageVQA) with a fully automatic,
three-step pipeline: representative sampling → context-aware translation → independent LLM evaluation with
selective repair. DSP391 course project, FPT University.

**Dataset (data + images + test sets):** https://www.kaggle.com/datasets/ngnguyncngthnh/plantvillagevqa-vietnamese

| | |
| --- | --- |
| Source | `SyedNazmusSakib/PlantVillageVQA`, revision `a025a438308eff9a7289231ebc09e27e8ec6678c`, CC BY 4.0 |
| Result | 24,195 Vietnamese QA rows, 18,747 images, train 19,366 / test 4,829 |
| Format | same columns and JSON structure as the source: `image_id, question_type, question, answer, image_path, split` |
| Validation | 7,489 pairs PASS + 30 PASS_AFTER_REPAIR; 3 UNRESOLVED pairs (6 rows) excluded |
| Models | Claude Sonnet via Claude Code (`claude -p`) for translation and repair; OpenAI Codex `gpt-6-luna` (`codex exec`) as judge |
| Cost | subscription plans only (Claude Pro, ChatGPT Plus), no paid API |

> **Tóm tắt:** repo này chứa toàn bộ mã nguồn, prompt, cấu hình và báo cáo của pipeline xây bộ VQA bệnh cây
> tiếng Việt từ PlantVillageVQA. Dữ liệu (CSV/JSON, ảnh, 4 bộ test) nằm trên Kaggle (link ở trên).

## Pipeline

```
HF PlantVillageVQA (EN, 193,609 QA)
 ─► Step 1  Representative subset          ─► 24,201 rows · 7,522 unique QA pairs
 ─► Step 2  EN→VI translation + rules       ─► Vietnamese translation + rule results per pair
 ─► Step 3  Judge (Codex) + one repair      ─► PASS / PASS_AFTER_REPAIR / UNRESOLVED per pair
 ─► Export  dataset (source format) + images + 4 test sets + EN–VI alignment + quality report
```

Principles: no human in the loop; every model result is written append-only right after each batch; reruns
skip finished items; a quota stop exits cleanly and the next run resumes from the checkpoint.

### Step 1 — Representative subset selection

- **Input:** the pinned source CSV (193,609 rows; splits train 154,977 / test 38,632, no validation split;
  9 question types → 18 strata).
- **Process:** proportional stratified random sampling over `split × question_type`, 12.5%, seed 42,
  largest-remainder quotas, ≥ 1 row per non-empty stratum, QA row as the unit, no replacement. The source has no
  QA id, so `qa_id = pvqa_<CSV row index>` (stable under the pinned revision).
- **Acceptance:** exact target size; every stratum within 0.002 pp of the source; no duplicate `qa_id`; source
  columns unchanged; every `image_path` resolves in the archive (by file name); same seed → same `qa_id` set
  (sha256 `d322d907…`).
- **Output:** `outputs/step1/subset_en.parquet` — 24,201 rows, 18,751 images, 7,522 unique QA pairs.

### Step 2 — Context-aware EN→VI translation (Claude Sonnet)

- **Input:** the English subset and `config/glossary.yaml`.
- **Process:**
  - 2.1 group rows into unique pairs `pair_id = hash(question_type, question_en, answer_en)`; translate each once.
  - 2.2 fixed glossary: 15 crops, 20 diseases/pests, ~25 symptom terms; scientific names kept; acronyms
    HLB / TYLCV / ToMV always written as full Vietnamese names.
  - 2.3 batches by question (≤ 40 pairs, 240 batches): all pairs of one English question share exactly one
    `question_vi`; question and answers translated together (`prompts/translator.md`, `schemas/translation.json`).
  - 2.4 Yes/No rules: keep proposition and polarity; "… có … không?" form, no tag or negative questions;
    answers `Có`/`Không`; `answer_label` copied from the source.
  - 2.5 rule-based terminology normalisation (`normalize_terms`).
  - 2.6 rule checks (`step2_rules.py`): valid output, Yes/No label and form, glossary names, no acronyms or
    leftover English, one `question_vi` per English question. Failing pairs go straight to repair (3.3).
- **Output:** translations for 7,522 pairs (7,508 pass the rules, 14 fail).

### Step 3 — Independent evaluation and selective repair

- **Input:** Step 2 translations, rule results, glossary.
- **Process:**
  - 3.1 smoke test (mandatory, not a calibration): 50 generated items — 10 each of polarity flip, crop swap,
    disease swap, dropped conditional, plus 10 correct controls. Result: 10/10 caught for every type, 0/10 false
    alarms (`outputs/step3/smoke_report__gpt-6-luna__high.md`).
  - 3.2 Codex `gpt-6-luna`, reasoning high, judges every rule-passing pair (40 per call) with MQM-style errors:
    mistranslation, polarity, omission, addition, terminology, fluency × minor/major/critical
    (`prompts/judge.md`, `schemas/judge.json`). PASS = no major/critical error. 7,489 PASS, 19 NEEDS_REPAIR.
    Cross-check on 120 random pairs with `gpt-6.1-sol`: 120/120 agreement.
  - 3.3 one repair: Claude re-translates the 33 flagged pairs with the judge's feedback (`prompts/repair.md`);
    the repair goes through 2.5–2.6 and is judged again → PASS_AFTER_REPAIR, or UNRESOLVED (never repaired twice,
    never replaced). If a repair changes a shared `question_vi`, every pair of that question is re-judged.
- **Output:** final status per pair: 7,489 PASS, 30 PASS_AFTER_REPAIR, 3 UNRESOLVED.

### Export

- `PlantVillageVQA_vi.csv` / `.json` — PASS + PASS_AFTER_REPAIR rows only, in the source format.
- `test_sets/` — `test_normal`, `test_blank` (white 256×256 image), `test_noimage` (empty image fields),
  `test_shuffled` (images permuted among test rows, seed 42, no row keeps its own image) + `test_sets_map.csv`.
- `PlantVillageVQA_vi_en_alignment.csv` — every subset row incl. UNRESOLVED, with judge errors and repair log.
- `outputs/final/quality_report.md` — source, distributions (source / EN subset / VI final), status by pair and
  by row, question consistency, smoke test, cross-check, limitations, cost.

## Results

| Status | Pairs | Rows |
| --- | --- | --- |
| PASS | 7,489 | 23,972 |
| PASS_AFTER_REPAIR | 30 | 223 |
| UNRESOLVED | 3 | 6 |

Model usage: Step 2 ≈ 2.36 M input tokens, 75 min; Step 3 ≈ 3.6 M input tokens, 70 min.

## Limitations (summary — full text in `outputs/final/quality_report.md`, section 6)

- Silver-standard: a single LLM judge, not calibrated against humans, inconsistent on borderline cases.
- Minor errors are not repaired by design: 299 pairs / 1,277 rows (~5%), mostly fluency.
- Template-generated source: 1,213 distinct questions, 125 distinct answers in 193,609 rows.
- Source template error: 3 "What …?" questions answered Yes/No (434 source rows, 68 in this dataset); translated
  as yes/no questions to match the labels.
- Row-level sampling: ~1.3 questions per image; ~20% of test QA pairs are not verbatim in train — score open
  answers by similarity, not exact match.
- Class imbalance inherited from PlantVillage; no validation split (split train by image if needed).

## Reproduce

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export PYTHONPATH=src
unset ANTHROPIC_API_KEY OPENAI_API_KEY      # use the logged-in Claude Code / Codex accounts

python -m pvvqa.step1_inspect               # Step 1.1  source revision, schema, splits
python -m pvvqa.step1_sample                # Step 1.2–1.3  sampling + acceptance
python -m pvvqa.step2_prepare               # Step 2.1–2.3  pairs, question table, batches
python -m pvvqa.step2_translate --pilot 50  # optional pilot
python -m pvvqa.step2_translate             # Step 2 translation (resumable)
python -m pvvqa.step3_judge --smoke         # Step 3.1
python -m pvvqa.step3_judge                 # Step 3.2 (resumable)
python -m pvvqa.step3_repair                # Step 3.3 repair + re-judge
python -m pvvqa.export_final                # dataset, alignment, quality report
python -m pvvqa.make_test_sets              # 4 test sets
python -m pvvqa.package_kaggle              # Kaggle folder with images (needs the source zip)
pytest -q
```

Configuration (pinned revision, seed, models): `config/phase1.yaml`. Plan and run rules: `CLAUDE.md`.
Run history, including interrupted runs and every decision: `PROGRESS.md`. Every model call is logged in
`runs/` (append-only checkpoints, raw model outputs, `run_log.jsonl` with command, commit, config hash, tokens).
Downloaded source data (`data/`) and the exported dataset files live on Kaggle, not in git.

## Repository layout

```
config/          phase1.yaml (revision, seed, models), glossary.yaml
prompts/         translator.md, repair.md, judge.md
schemas/         translation.json, judge.json
src/pvvqa/       step1_*, step2_*, step3_*, export_final, make_test_sets, package_kaggle
scripts/         one-off maintenance scripts (documented in PROGRESS.md)
tests/           pytest on synthetic data (fake claude / codex)
outputs/         step1 reports, step2 pair tables, step3 smoke/cross-check reports, final quality report
docs/            PIPELINE.md, kaggle_dataset_card.md
```

## License and citation

Data derived from PlantVillageVQA (CC BY 4.0) — cite the original dataset (arXiv:2508.17117) and the PlantVillage
image corpus (Hughes & Salathé, arXiv:1511.08060). Vietnamese dataset:
https://www.kaggle.com/datasets/ngnguyncngthnh/plantvillagevqa-vietnamese

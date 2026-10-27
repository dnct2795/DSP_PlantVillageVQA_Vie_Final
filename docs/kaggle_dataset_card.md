# PlantVillageVQA — Vietnamese Subset (silver-standard)

A Vietnamese visual question answering (VQA) dataset for plant pathology: **24,195 QA rows on 18,747 leaf
images**, translated from a representative 12.5% subset of
[PlantVillageVQA](https://huggingface.co/datasets/SyedNazmusSakib/PlantVillageVQA) (arXiv:2508.17117, CC BY 4.0)
and validated by a fully automatic pipeline. The files keep **the same columns and JSON structure as the
original dataset**, so code written for PlantVillageVQA runs on this one unchanged.

- **Code, pipeline and full run logs:** https://github.com/dnct2795/DSP_PlantVillageVQA_Vie_Final
- **Source dataset:** `SyedNazmusSakib/PlantVillageVQA`, revision `a025a438308eff9a7289231ebc09e27e8ec6678c`
- Built for the DSP391 course project (FPT University). No paid API was used.

> **Tóm tắt (tiếng Việt):** bộ VQA bệnh cây tiếng Việt gồm 24.195 câu hỏi–đáp trên 18.747 ảnh lá, lấy mẫu đại
> diện 12,5% từ PlantVillageVQA, dịch bằng Claude Sonnet và kiểm định tự động bằng Codex. Cột và cấu trúc giữ
> nguyên như dataset gốc. Có 4 bộ test (bình thường + 3 bộ ablation: ảnh trắng, không ảnh, tráo ảnh). Pipeline
> và mã nguồn: link GitHub ở trên.

## Files

```
PlantVillageVQA_vi.csv                 24,195 rows · image_id, question_type, question, answer, image_path, split
PlantVillageVQA_vi.json                same rows: {image_id: {image_path, split, questions: [{question_type, question, answer}]}}
images/train/<file>, images/test/<file>    18,747 JPEG images (256×256), placed exactly at image_path
images/blank/blank.jpg                 white 256×256 image used by test_blank.csv
test_sets/test_normal.csv              4,829 test rows, original images
test_sets/test_blank.csv               same rows, every image replaced by images/blank/blank.jpg
test_sets/test_noimage.csv             same rows, image_id and image_path empty
test_sets/test_shuffled.csv            same rows, images permuted among test rows (seed 42); no row keeps its own image
test_sets/test_sets_map.csv            qa_id ↔ image used in each test set
PlantVillageVQA_vi_en_alignment.csv    all 24,201 subset rows: qa_id, English and Vietnamese QA, answer_label,
                                       pair_id, status, judge errors, repair log
quality_report.md                      sampling, distributions, validation results, limitations, cost
```

| Column | Meaning |
| --- | --- |
| `image_id` | image file name, unchanged from the source |
| `question_type` | one of 9 source categories (English labels kept) |
| `question`, `answer` | Vietnamese; Yes/No answers are `Có` / `Không` |
| `image_path` | unchanged source value `images/<split>/<file>`; resolves inside this dataset |
| `split` | `train` (19,366 rows) or `test` (4,829 rows), unchanged from the source; no image is in both |

The source has no validation split. If you need one, split `train` **by image**, not by row.

## How it was built (3-step pipeline)

**Step 1 — Representative subset selection.** Proportional stratified random sampling over the 18
`split × question_type` strata of the 193,609 source rows: 12.5%, seed 42, largest-remainder quotas, at least
one row per stratum, QA row as the unit. Result: 24,201 rows, 18,751 images, 7,522 unique QA pairs. Every
stratum share is within 0.002 percentage points of the source; rerunning with the same seed gives the same
`qa_id` set (sha256 checked).

**Step 2 — Context-aware EN→VI translation (Claude Sonnet).**
2.1 identical `(question_type, question, answer)` rows are grouped into unique pairs, translated once;
2.2 a fixed glossary of 15 crops, 20 diseases/pests and ~25 symptom terms (scientific names kept; the acronyms
HLB, TYLCV, ToMV always written as full Vietnamese names);
2.3 pairs sharing an English question are translated together and share exactly one Vietnamese question;
2.4 Yes/No rules: same proposition and polarity, "… có … không?" form, answers `Có`/`Không`, label copied from
the source;
2.5 rule-based terminology normalisation;
2.6 rule checks (valid output, Yes/No form and label, glossary names, no leftover English).

**Step 3 — Independent evaluation and selective repair.**
3.1 smoke test of the judge on 50 generated items: it caught 10/10 injected errors of each type (polarity flip,
crop swap, disease swap, dropped "if") with 0/10 false alarms on correct controls;
3.2 OpenAI Codex `gpt-6-luna` (reasoning high) judged every pair against the English with MQM-style errors
(mistranslation, polarity, omission, addition, terminology, fluency × minor/major/critical); PASS = no major or
critical error; a cross-check of 120 random pairs with `gpt-6.1-sol` agreed 120/120;
3.3 pairs failing the rules or the judge were re-translated once by Claude with the judge's feedback and judged
again: PASS_AFTER_REPAIR, or UNRESOLVED (kept only in the alignment file).

| Status | Pairs | Rows |
| --- | --- | --- |
| PASS | 7,489 | 23,972 |
| PASS_AFTER_REPAIR | 30 | 223 |
| UNRESOLVED (excluded) | 3 | 6 |

No English question has more than one Vietnamese translation.

## Ablation test sets

The four files in `test_sets/` contain the same 4,829 questions and answers in the same order; only the image
changes. Comparing a model across them shows how much it relies on the question text instead of the image:
`blank` (an uninformative image), `noimage` (no image at all), `shuffled` (a real but wrong leaf image). Compare
Yes/No accuracy with the per-question-type majority baseline (about 40% of Yes/No answers are `Có`).

## Limitations

- **Silver-standard.** One LLM judge is the only semantic check; it is not calibrated against human raters and
  is inconsistent on borderline cases. Do not describe the data as human-verified.
- **Minor errors are not repaired** by design: 299 pairs (1,277 rows, ~5%) keep minor issues, mostly fluency
  (e.g. "đốm lốm đốm" for *stippling*). They are listed in the alignment file.
- **Template-generated source:** 1,213 distinct questions and 125 distinct answers across 193,609 rows; models
  can learn the templates without looking at the image.
- **Source template error:** three questions phrased "What …?" are answered Yes/No in the source (434 rows; 68
  in this dataset). The Vietnamese questions are phrased as yes/no questions so they match the answers.
- **Row-level sampling:** about 1.3 questions per image, and ~20% of test QA pairs do not appear verbatim in
  train. Score open answers by similarity or key terms (disease, crop), not exact match.
- **Class imbalance** inherited from PlantVillage: citrus greening on orange and tomato yellow leaf curl virus
  make up about 35% of rows.

Details and figures: `quality_report.md`.

## License and citation

CC BY 4.0, inherited from PlantVillageVQA. Please cite the original dataset and paper:

- PlantVillageVQA — Hugging Face `SyedNazmusSakib/PlantVillageVQA`, arXiv:2508.17117.
- PlantVillage images — Hughes & Salathé, *An open access repository of images on plant health to enable the
  development of mobile disease diagnostics*, arXiv:1511.08060.

and link this dataset and https://github.com/dnct2795/DSP_PlantVillageVQA_Vie_Final for the Vietnamese
version.

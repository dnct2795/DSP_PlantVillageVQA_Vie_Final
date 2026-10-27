# Official Phase 1 pipeline (3 steps)

Source of truth: the team design doc, tab "Pipeline chính thức (3 bước)".
Summary of what the code must respect:

- Preserve `split`, `question_type`, `image_path` and the original QA mapping (`qa_id` ↔ image).
- **Step 1**: 1.1 inspect revision/schema/splits; 1.2 proportional stratified random sampling
  (split × question_type, 12.5%, seed 42, largest remainder, ≥1 per non-empty stratum,
  QA-row unit, no replacement); 1.3 acceptance (distribution, no duplicate ids, image paths
  exist, original columns unchanged, reproducible).
- **Step 2**: unique pairs `(question_type, question_en, answer_en)` → `pair_id`; glossary fixed
  once; pairs sharing `(question_type, question_en)` translated in one batch and share one
  `question_vi`; Yes/No: keep proposition + polarity, answers "Có"/"Không", `answer_label`
  copied; rule checks; append-only checkpoints.
- **Step 3**: mandatory smoke test (~10 injected errors per type: polarity flip, crop swap,
  disease swap, dropped hypothetical; ~10 correct controls) → Codex judges every pair
  (MQM-style) → PASS / NEEDS_REPAIR → one repair → PASS_AFTER_REPAIR / UNRESOLVED.
  UNRESOLVED kept for traceability, never silently dropped or replaced, not used for training.
- Only PASS + PASS_AFTER_REPAIR = "automatically validated silver-standard".
- Quality report: by unique pair AND by QA row; distribution original vs EN subset vs VI final.


## Repair mode (this call)
This call is a REPAIR, not a fresh translation. Each input question has the current Vietnamese
translation and, for each pair, feedback from automatic checks and/or an independent evaluator.

Input: {"questions": [{question_key, question_type, question_en, current_question_vi,
pairs: [{pair_id, answer_en, is_yes_no, current_answer_vi, feedback: [...]}]}]}

- Fix every problem named in the feedback, following all rules above (glossary, Yes/No form,
  polarity, conditionals, no leftover English). Keep everything that was already correct.
- question_vi is SHARED with other pairs of the same question that are not shown here. Return
  current_question_vi unchanged unless the feedback is about the question itself; if you must
  change it, the new question_vi must still fit every answer of that question.
- Output exactly the same shape as a normal translation: one entry per input question (same
  question_key) with question_vi, and one entry per input pair (same pair_id) with answer_vi.

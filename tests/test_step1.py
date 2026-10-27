import numpy as np
import pandas as pd

from pvvqa.common import detect_columns, ids_digest
from pvvqa.step1_sample import acceptance, allocate, prepare, sample, strata_table


def synth(seed=0):
    rng = np.random.default_rng(seed)
    rows = []
    sizes = {("train", "yes_no"): 5000, ("train", "open"): 1203, ("train", "rare"): 3,
             ("test", "yes_no"): 1200, ("test", "open"): 311, ("val", "rare"): 1}
    for (sp, qt), n in sizes.items():
        for i in range(n):
            rows.append({"split": sp, "question_type": qt, "question": f"q{qt}{i % 7}",
                         "answer": "Yes" if i % 2 else "No", "image_path": f"img/{sp}_{i}.jpg"})
    df = pd.DataFrame(rows).sample(frac=1, random_state=seed).reset_index(drop=True)
    return df


def test_allocate_total_and_min():
    s = pd.Series({("a", "x"): 5000, ("a", "y"): 3, ("b", "x"): 1, ("b", "y"): 997})
    q = allocate(s, 0.125, 1)
    assert q.sum() == round(s.sum() * 0.125)
    assert (q >= 1).all() and (q <= s.sort_index()).all()


def test_sample_reproducible_and_checks_pass():
    raw = synth()
    cols = detect_columns(raw)
    src = prepare(raw, cols)
    sub, sizes, quotas = sample(src, 0.125, 42, 1)
    sub2, _, _ = sample(src, 0.125, 42, 1)
    assert ids_digest(sub["qa_id"]) == ids_digest(sub2["qa_id"])
    sub3, _, _ = sample(src, 0.125, 73, 1)
    assert ids_digest(sub["qa_id"]) != ids_digest(sub3["qa_id"])
    table = strata_table(sizes, quotas, 0.125)
    checks = acceptance(raw, src, sub, table, 0.125, 1, set(raw["image_path"]),
                        ids_digest(sub2["qa_id"]))
    assert checks["all_passed"], checks
    # per-stratum counts equal quotas
    got = sub.groupby(["split", "question_type"]).size()
    assert (got.sort_index() == quotas.sort_index()).all()


def test_missing_image_detected():
    raw = synth()
    src = prepare(raw, detect_columns(raw))
    sub, sizes, quotas = sample(src, 0.125, 42, 1)
    table = strata_table(sizes, quotas, 0.125)
    checks = acceptance(raw, src, sub, table, 0.125, 1, set(), ids_digest(sub["qa_id"]))
    assert checks["image_path_exists_in_repo"]["ok"] is False
    assert not checks["all_passed"]

# Step 1.2–1.3 — Sampling report

- Method: proportional stratified random sampling; strata = split × question_type
- Fraction 0.125, seed 42, min 1/stratum, largest-remainder rounding, no replacement
- Source rows: 193,609 → subset rows: 24,201; strata: 18
- Source revision: `a025a438308eff9a7289231ebc09e27e8ec6678c`
- Unique images in subset: 18751

## Acceptance checks

- **PASS** total_matches_target {'n_subset': 24201, 'n_target': 24201}
- **PASS** quota_within_rounding {'max_abs_dev_rows': 0.5, 'n_strata_forced_to_min': 0}
- max_share_diff_pp: 0.0021
- **PASS** every_nonempty_stratum_present 
- **PASS** no_duplicate_qa_id 
- **PASS** original_columns_unchanged 
- **PASS** image_path_exists_in_repo {'n_missing': 0, 'examples': []}
- **PASS** reproducible_seed_rerun {'qa_id_sha256': 'd322d907ec88015af41f477af40512fbadb156e4dad58ed76b48d00e69ab091f'}
- **ALL PASSED: True**

## Strata

| split | question_type | N_h | n_h | source % | subset % | diff pp |
|---|---|---|---|---|---|---|
| test | Causal Reasoning | 5230 | 654 | 2.701 | 2.702 | +0.001 |
| test | Comprehensive Description | 5573 | 697 | 2.878 | 2.880 | +0.002 |
| test | Counterfactual Reasoning | 2021 | 253 | 1.044 | 1.045 | +0.002 |
| test | Detailed Verification | 2848 | 356 | 1.471 | 1.471 | +0.000 |
| test | Existence & Sanity Check | 617 | 77 | 0.319 | 0.318 | -0.001 |
| test | General Health Assessment | 6365 | 796 | 3.288 | 3.289 | +0.002 |
| test | Plant Species Identification | 6794 | 849 | 3.509 | 3.508 | -0.001 |
| test | Specific Disease Identification | 5979 | 747 | 3.088 | 3.087 | -0.002 |
| test | Visual Attribute Grounding | 3205 | 401 | 1.655 | 1.657 | +0.002 |
| train | Causal Reasoning | 20993 | 2624 | 10.843 | 10.843 | -0.000 |
| train | Comprehensive Description | 22236 | 2779 | 11.485 | 11.483 | -0.002 |
| train | Counterfactual Reasoning | 7960 | 995 | 4.111 | 4.111 | +0.000 |
| train | Detailed Verification | 11241 | 1405 | 5.806 | 5.806 | -0.000 |
| train | Existence & Sanity Check | 2228 | 278 | 1.151 | 1.149 | -0.002 |
| train | General Health Assessment | 25734 | 3217 | 13.292 | 13.293 | +0.001 |
| train | Plant Species Identification | 27357 | 3420 | 14.130 | 14.132 | +0.002 |
| train | Specific Disease Identification | 23947 | 2993 | 12.369 | 12.367 | -0.001 |
| train | Visual Attribute Grounding | 13281 | 1660 | 6.860 | 6.859 | -0.000 |

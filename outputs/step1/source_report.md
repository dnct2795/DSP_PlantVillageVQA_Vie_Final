# Step 1.1 — Source report

- Repo: `SyedNazmusSakib/PlantVillageVQA`  revision (commit sha): `a025a438308eff9a7289231ebc09e27e8ec6678c`
- QA file: `PlantVillageVQA/PlantVillageVQA.csv`
- QA rows: 193,609
- Unique images (QA table): 50073
- Image files in repo: 55448
- Unique QA pairs: 15065; unique questions: 1213; top-10 pairs cover 0.0455 of rows
- Non-empty strata (split × question_type): 18
- Images appearing in >1 split: 0

## Detected columns

- id: `None`
- split: `split`
- question_type: `question_type`
- question: `question`
- answer: `answer`
- image: `image_path`

## Schema

| column | dtype | nulls | example |
|---|---|---|---|
| image_id | str | 0 | image_000001.jpg |
| question_type | str | 0 | Existence & Sanity Check |
| question | str | 0 | Is there a plant leaf in this image? |
| answer | str | 0 | No |
| image_path | str | 0 | images/train/image_000001.jpg |
| split | str | 0 | train |

## split × question_type (rows)

| split | Causal Reasoning | Comprehensive Description | Counterfactual Reasoning | Detailed Verification | Existence & Sanity Check | General Health Assessment | Plant Species Identification | Specific Disease Identification | Visual Attribute Grounding | total |
|---|---|---|---|---|---|---|---|---|---|---|
| test | 5230 | 5573 | 2021 | 2848 | 617 | 6365 | 6794 | 5979 | 3205 | 38632 |
| train | 20993 | 22236 | 7960 | 11241 | 2228 | 25734 | 27357 | 23947 | 13281 | 154977 |

## Differences vs paper / README

- unique images in QA table 50,073 != paper 55,448
- actual split values: ['test', 'train'] (paper: ['train', 'test'], README: ['train', 'val', 'test'])
- CSV vs JSON copy (PlantVillageVQA/PlantVillageVQA.json): identical rows {'both': 193609, 'left_only': 0, 'right_only': 0}
- image_path resolves by exact path 0.00%, by file name 100.00% (QA table uses images/<split>/<file>; archive example: 'PlantVillageVQA/Images/image_000000.JPG')
- 5,375 archive images have no QA row

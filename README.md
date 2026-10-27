# DSP391 — PlantVillageVQA EN → VI (Phase 1)

Builds a Vietnamese agricultural VQA subset from
[PlantVillageVQA](https://huggingface.co/datasets/SyedNazmusSakib/PlantVillageVQA)
following the official 3-step pipeline (see [docs/PIPELINE.md](docs/PIPELINE.md)):

1. **Representative Subset Selection** — proportional stratified random sampling
   (split × question_type, 12.5%, seed 42). *Implemented.*
2. **Context-aware EN–VI QA Translation** — unique QA pairs, shared question map. *Not yet.*
3. **Independent Translation Evaluation & Selective Repair** — Codex judge, one repair. *Not yet.*

Phase 1 = dataset construction only (no training / benchmarking).

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export PYTHONPATH=src
```

## Step 1

```bash
python -m pvvqa.step1_inspect     # 1.1 revision, schema, splits (downloads metadata only, no images)
python -m pvvqa.step1_sample      # 1.2 sampling + 1.3 acceptance checks
pytest -q                         # unit tests on synthetic data
```

Outputs in `outputs/step1/`: `source_report.{md,json}`, `sampling_report.{md,json}`,
`strata.csv`, `subset_manifest.csv`, `subset_en.parquet`.
Downloaded metadata goes to `data/raw/` (git-ignored).

After 1.1, pin `dataset.revision` in `config/phase1.yaml` to the reported commit sha.

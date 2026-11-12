# Offline assets

These files are part of the repo so Kaggle dependency setup does not clone
NoRA, contact PyPI, or download build dependencies.

| Asset | Version | Provenance |
| --- | --- | --- |
| `peft/` | 0.19.2.dev0 | Joluck/NoRA commit `4669c35ce0ffd027456272ee5050c0f58ac8d22a`, copied unchanged |
| `wheels/peft-0.19.2.dev0-py3-none-any.whl` | 0.19.2.dev0 | Built from `peft/` using `scripts/build_peft_wheel.py`, including Apache/MIT notices |
| `wheels/transformers-4.57.6-py3-none-any.whl` | 4.57.6 | Repacked from the local uv cache of the official distribution with `wheel pack` |
| `wheels/huggingface_hub-0.36.2-py3-none-any.whl` | 0.36.2 | Repacked from the local uv cache of the official distribution with `wheel pack` |

The HF wheels are pure Python, include the original distribution metadata and
licenses, and are repacked artifacts rather than byte-identical PyPI downloads.
They allow the notebook to keep its existing Transformers `<5` contract even
when the offline Kaggle image ships Transformers 5 and Hub 1.

`manifest.json` records source and wheel SHA-256 hashes. Setup verifies every
entry before installing anything. `scripts/build_vendor_manifest.py` prints
a refreshed manifest when the vendored sources or wheels are intentionally
rebuilt. The application additionally validates the imported NoRA config,
layer, and variant code against the reference hashes.

From the repo root, before importing PEFT or Transformers:

```bash
python scripts/setup_offline.py --check-only
python scripts/setup_offline.py
```

The installer always reinstalls the local PEFT wheel, since an ordinary PEFT
release number does not prove NoRA support. It changes Transformers/Hub only
when their installed versions violate the project's pins. It uses only wheel
files, with `--isolated --no-index --no-deps --no-cache-dir`; it does not build
or install the project package. Notebook subprocesses use `PYTHONPATH=src`.

The remaining dependencies come from the Kaggle image. Missing/incompatible
image packages cause a clear preflight error before installation. CUDA torch
is never included in the install plan. NoRA source and licenses are described
in [peft/UPSTREAM.md](peft/UPSTREAM.md).

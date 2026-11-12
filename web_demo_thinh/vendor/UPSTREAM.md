# Vendored NoRA PEFT

Source: https://github.com/Joluck/NoRA
Commit: `4669c35ce0ffd027456272ee5050c0f58ac8d22a`
Package: `peft==0.19.2.dev0`

`src/peft/`, `setup.py`, `README.md`, and `LICENSE` are copied unchanged
from that commit's `peft/` directory. `LICENSE-NoRA` is the repository's
MIT license. PEFT retains its Apache-2.0 license and file notices.
No git checkout, network download, or monkey patch is needed at runtime.

NoRA-specific implementation locations:

- `src/peft/tuners/lora/config.py`: serialized `use_nora=False`, `"init"`, or `True`.
- `src/peft/tuners/lora/layer.py`: adapter state, one-time column normalization,
  differentiable continuous normalization, normalized delta for merge/unmerge,
  and multihead-attention initialization.
- `src/peft/tuners/lora/variants.py`: normalized A callable for the DoRA variant.

The complete package is retained so configuration loading, adapter dispatch,
Trainer integration, saving, reloading, and upstream variants use the same code
as the reference implementation. Upstream limitations are preserved; this
project targets ordinary decoder `nn.Linear` projections and evaluates adapters
without merging.

The wheel in `../wheels/` is built from this source with setuptools, including
both Apache and MIT notices. Rebuild
after any intentional vendor edit:

```bash
.venv/bin/python scripts/build_peft_wheel.py
```

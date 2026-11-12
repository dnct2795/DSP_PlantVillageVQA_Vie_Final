# Sao chép từ pvvqa/model/adapters.py (repo model của Khoa): kiểm tra PEFT đang cài đúng là bản NoRA.
import hashlib
import inspect
from pathlib import Path

NORA_UPSTREAM_COMMIT = '4669c35ce0ffd027456272ee5050c0f58ac8d22a'
NORA_SOURCE_HASHES = {
    'config.py': '1319a8704b07e5cafdaddbdbe5199864ec29c02dc279253c4fa47b1e2f7043bc',
    'layer.py': 'a7a0cc33473c328e751c22fa2710d60e5b7b9513e84916fae8037733d2a21c56',
    'variants.py': 'f3458a1eeffae5274f5463ca3c8ff6300d5ef58b4949cfdd89c71a74b2a7799b',
}


def check_nora_capability():
    from peft import LoraConfig
    if 'use_nora' not in inspect.signature(LoraConfig).parameters:
        raise RuntimeError('PEFT thiếu use_nora. Cài wheel trong vendor/wheels (scripts/setup_env.sh).')
    from peft.tuners.lora import config, layer, variants
    for module in [config, layer, variants]:
        digest = hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest()
        if digest != NORA_SOURCE_HASHES[Path(module.__file__).name]:
            raise RuntimeError('PEFT đang cài không phải bản NoRA đi kèm. Chạy scripts/setup_env.sh.')

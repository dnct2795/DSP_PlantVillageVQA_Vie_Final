"""Codex giả cho test: đọc prompt từ stdin, ghi JSON vào file -o, in sự kiện --json.
FAKE_MODE: good | quota | broken. Mục smoke cố ý sai (id smoke_* trừ control) bị chấm critical."""
import json, os, re, sys

args = sys.argv[1:]
out = args[args.index("-o") + 1]
msg = sys.stdin.read()
mode = os.environ.get("FAKE_MODE", "good")
if mode == "quota":
    print(json.dumps({"type": "error", "message": "You've hit your usage limit. Try again later."}))
    sys.exit(1)
if mode == "broken":
    print(json.dumps({"type": "turn.completed", "usage": {"input_tokens": 1, "output_tokens": 1}}))
    sys.exit(0)  # không ghi file -o
payload = json.loads(msg[msg.index("{"):])
items = []
for it in payload["items"]:
    bad = it["id"].startswith("smoke_") and "control" not in it["id"]
    items.append({"id": it["id"], "errors": [{"category": "mistranslation", "severity": "critical",
                                               "explanation": "giả"}] if bad else []})
open(out, "w").write(json.dumps({"items": items}))
print(json.dumps({"type": "turn.completed", "usage": {"input_tokens": 100, "output_tokens": 10}}))

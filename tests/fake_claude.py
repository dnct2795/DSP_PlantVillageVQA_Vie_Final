"""Claude giả cho test: đọc batch từ stdin, trả JSON giống `claude -p --output-format json`.
FAKE_MODE: good | quota | broken | drop_pair
"""
import json, os, re, sys

msg = sys.stdin.read()
mode = os.environ.get("FAKE_MODE", "good")
counter = os.environ.get("FAKE_COUNTER")
if counter:
    n = int(open(counter).read() or 0) if os.path.exists(counter) else 0
    open(counter, "w").write(str(n + 1))
    if mode == "quota_after_1" and n >= 1:
        mode = "quota"
    elif mode == "quota_after_1":
        mode = "good"
if mode == "quota":
    print(json.dumps({"type": "result", "is_error": True,
                      "result": "Claude usage limit reached. Your limit resets at 9pm."}))
    sys.exit(1)
if mode == "broken":
    print(json.dumps({"type": "result", "is_error": False, "result": "sorry, no json"}))
    sys.exit(0)
payload = json.loads(msg[msg.index("{"):])
out = []
for q in payload["questions"]:
    pairs = []
    for p in q["pairs"]:
        a = {"Yes": "Có", "No": "Không"}.get(p["answer_en"], "Đây là lá cà chua.")
        pairs.append({"pair_id": p["pair_id"], "answer_vi": a})
    if mode == "drop_pair" and len(pairs) > 1:
        pairs = pairs[:-1]
    out.append({"question_key": q["question_key"],
                "question_vi": "Lá cà chua này có bệnh không?", "pairs": pairs})
print(json.dumps({"type": "result", "is_error": False, "result": json.dumps({"questions": out}),
                  "usage": {"input_tokens": 10, "output_tokens": 5}}))

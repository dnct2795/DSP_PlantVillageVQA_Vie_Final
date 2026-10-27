"""Step 2.5–2.6 — chuẩn hoá thuật ngữ và kiểm tra bằng luật (không dùng model).

normalize_terms(text): 2.5, thay viết tắt tiếng Anh HLB / TYLCV / ToMV bằng tên tiếng Việt đầy đủ theo
glossary (áp lên mọi bản dịch của Claude — dịch lần đầu và bản sửa ở 3.3 — trước khi kiểm tra luật).

check_question(item_in, item_out, glossary) -> {pair_id: [mã lỗi, ...]}
Mã lỗi: missing_question, missing_pair, extra_pair, empty, yn_answer, yn_form, yn_tag,
        gloss:<en>, abbr:<viết tắt>, untranslated:<từ>
Cặp có lỗi KHÔNG bị loại: được ghi lại và chuyển thẳng sang repair ở Step 3.
"""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import yaml

YN_VI = {"Yes": "Có", "No": "Không"}
WORD = re.compile(r"[A-Za-zÀ-ỹĐđ']+")
# Từ ASCII hợp lệ trong tiếng Việt có thể trùng từ tiếng Anh trong câu nguồn.
VI_ASCII_OK = {"do", "to", "an", "con", "can", "hay", "ma", "cho", "ban", "long", "hang",
               "bang", "nam", "tim", "lam", "ta", "da", "va"}
EN_COMMON = {"the", "is", "are", "of", "and", "or", "with", "this", "that", "leaf", "leaves",
             "plant", "disease", "healthy", "spot", "spots", "blight", "rust", "mold", "yes",
             "no", "symptoms", "infection", "specimen", "foliage", "lesions", "sign", "signs"}


# 2.5 — thứ tự quan trọng: bỏ viết tắt trong ngoặc sau tên đầy đủ trước, rồi mới thay viết tắt đứng riêng.
NORMALIZE_RULES = [
    (r"\s*\((TYLCV|ToMV|HLB)\)", ""),
    (r"\(Huanglongbing, HLB\)", "(Huanglongbing)"),
    (r"\bbệnh (nhiễm|do) virus: TYLCV\b", r"bệnh \1 virus xoăn vàng lá cà chua"),
    (r"\bbệnh (nhiễm|do) virus: ToMV\b", r"bệnh \1 virus khảm cà chua"),
    (r"\bbệnh HLB\b", "bệnh vàng lá gân xanh"),
    (r"\bvirus TYLCV\b", "virus xoăn vàng lá cà chua"),
    (r"\bvirus ToMV\b", "virus khảm cà chua"),
    (r"\bTYLCV\b", "virus xoăn vàng lá cà chua"),
    (r"\bToMV\b", "virus khảm cà chua"),
    (r"\bHLB\b", "bệnh vàng lá gân xanh"),
]


def normalize_terms(text: str) -> str:
    for pat, rep in NORMALIZE_RULES:
        text = re.sub(pat, rep, text)
    return text


def load_glossary(path: str | Path) -> dict:
    with open(path, encoding="utf-8") as f:
        g = yaml.safe_load(f)
    for k in ("crops", "diseases"):
        for e in g[k]:
            e["_re"] = re.compile(e["match"], re.IGNORECASE)
            e.setdefault("check", e["vi"])
    g["_keep"] = {w.lower() for item in g.get("keep", []) for w in item.split()}
    return g


def _norm(s: str) -> str:
    return unicodedata.normalize("NFC", s).strip()


def _is_ascii_word(w: str) -> bool:
    return all(ord(c) < 128 for c in w)


def gloss_errors(en: str, vi: str, glossary: dict) -> list[str]:
    out = []
    vi_l = vi.lower()
    for k in ("crops", "diseases"):
        for e in glossary[k]:
            # Viết tắt tiếng Anh (HLB, TYLCV, ToMV) không được giữ trong bản dịch, kể cả trong ngoặc.
            if e.get("abbr") and re.search(rf"\b{re.escape(e['abbr'])}\b", vi):
                out.append(f"abbr:{e['abbr']}")
            if e["_re"].search(en) and e["check"].lower() not in vi_l:
                out.append(f"gloss:{e['en']}")
    return out


def untranslated(en: str, vi: str, glossary: dict) -> list[str]:
    en_vocab = {w.lower() for w in WORD.findall(en)} | EN_COMMON
    bad = []
    for w in WORD.findall(vi):
        wl = w.lower().strip("'")
        if len(wl) < 2 or not _is_ascii_word(wl):
            continue
        if wl in glossary["_keep"] or wl in VI_ASCII_OK:
            continue
        if wl in en_vocab:
            bad.append(f"untranslated:{wl}")
    return sorted(set(bad))


def yn_question_errors(q_vi: str) -> list[str]:
    q = q_vi.strip()
    errs = []
    # Câu hỏi đuôi "…(,) phải không?" / "…(,) đúng không?", có hay không có dấu phẩy.
    # Kết thúc bằng "phải không?" luôn là câu hỏi đuôi ("có phải … không?" thì có nội dung ở giữa);
    # "… có đúng không?" vẫn là dạng "có … không?" nên không tính.
    if re.search(r"(phải|(?<!có )đúng)\s+không\s*\?$", q, re.IGNORECASE):
        errs.append("yn_tag")
    if not re.search(r"không\s*\?$", q, re.IGNORECASE) or not re.search(r"\bcó\b", q, re.IGNORECASE):
        errs.append("yn_form")
    return errs


def check_question(item_in: dict, item_out: dict | None, glossary: dict) -> dict[str, list[str]]:
    pids = [p["pair_id"] for p in item_in["pairs"]]
    if item_out is None:
        return {pid: ["missing_question"] for pid in pids}
    q_vi = _norm(item_out.get("question_vi") or "")
    got = {p.get("pair_id"): _norm(p.get("answer_vi") or "") for p in item_out.get("pairs", [])}
    has_yn = any(p["is_yes_no"] for p in item_in["pairs"])
    q_errs = []
    if not q_vi:
        q_errs.append("empty")
    else:
        q_errs += gloss_errors(item_in["question_en"], q_vi, glossary)
        q_errs += untranslated(item_in["question_en"], q_vi, glossary)
        if has_yn:
            q_errs += yn_question_errors(q_vi)
    res = {}
    for p in item_in["pairs"]:
        pid = p["pair_id"]
        if pid not in got:
            res[pid] = ["missing_pair"]
            continue
        a_vi = got[pid]
        errs = list(q_errs)
        if not a_vi:
            errs.append("empty")
        elif p["is_yes_no"]:
            if a_vi != YN_VI[p["answer_en"]]:
                errs.append("yn_answer")
        else:
            errs += gloss_errors(p["answer_en"], a_vi, glossary)
            errs += untranslated(p["answer_en"], a_vi, glossary)
        res[pid] = sorted(set(errs))
    for extra in set(got) - set(pids):
        res.setdefault(extra, []).append("extra_pair")
    return res

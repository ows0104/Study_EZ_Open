"""ChatGPT 의 표·블록 응답 → 스키마에 맞는 문제은행 JSON.

정리는 모델이 한다(2026-10-03 관리자: 「정리는 LLM이 하긴 해야 할 것 같아」). 이 단계는
옮기기만 하고 고치지 않는다 — 고칠 만한 것은 warnings 로, 의학적 정오는 review.py 로.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from . import session
from .schema import BANK, SCHEMA_VERSION

PROMPT = Path(__file__).parent / "prompts" / "organize.md"
SYSTEM = "You convert a supplied study-bank response into the requested JSON. Follow the user message exactly."
COMPLETE_MARK = "STUDYEZ_BANK_COMPLETE"

# ChatGPT 가 첨부 파일을 인용할 때 본문에 심는 표식 — runner/preview.py 와 같은 것.
#     U+E200 filecite U+E202 turn0file0 U+E202 L6-L13 U+E201
# 그대로 두면 정리기가 이것을 출처로 읽는다.
_CITATION_RE = re.compile(".*?", re.S)
_PUA_RE = re.compile("[-]")


def clean_response(raw: str) -> str:
    """인용 표식·사용자 영역 문자·끝의 완료 표시를 걷는다."""
    text = _CITATION_RE.sub("", raw)
    text = _PUA_RE.sub("", text)
    text = re.sub(r"[ \t]+\n", "\n", text).strip()
    text = re.sub(r"\**\s*" + COMPLETE_MARK + r"\s*\**\s*$", "", text).rstrip()
    return text


def organizer_prompt(raw: str, lecture: dict) -> str:
    meta = {"title": lecture["title"], "sources": lecture["sources"]}
    fill = {"schema_version": SCHEMA_VERSION,
            "lecture": json.dumps(meta, ensure_ascii=False),
            "raw": json.dumps(clean_response(raw), ensure_ascii=False)}
    return re.sub(r"\{\{(schema_version|lecture|raw)\}\}", lambda m: fill[m.group(1)],
                  PROMPT.read_text(encoding="utf-8"))


# `L1:M1` · `A: cAMP 감소` · `R2) PLC` — ChatGPT 가 짝짓기·순서 항목에 붙이는 라벨.
_LABEL_RE = re.compile(r"^\s*([A-Z]\d{0,2}|\d{1,2})\s*[:.)]\s*(.+?)\s*$")


def _unlabel(items: list[str]) -> dict[str, str] | None:
    """항목마다 라벨이 붙어 있으면 {라벨: 본문}. 하나라도 없거나 라벨이 겹치면 None."""
    found = [_LABEL_RE.match(x) for x in items]
    if not items or not all(found):
        return None
    labels = {m.group(1): m.group(2) for m in found}
    return labels if len(labels) == len(items) else None


def tidy_labels(bank: dict) -> list[str]:
    """정답이 라벨(`L1`·`B`)만 가리키면 라벨을 떼고 본문으로 맞춘다. 고친 문항 ID 를 돌려준다.

    261002_02 실측(2026-10-04): 같은 응답을 두 번 정리했더니 한 번은 라벨을 풀고 한 번은 안 풀었다 —
    안 푼 쪽에서 matching 4 · sequence 2 문항이 「참조 오류」로 떨어졌다. 모델에 맡기지 않는다.
    """
    fixed = []
    for q in bank.get("questions", []):
        if q.get("format") == "matching":
            left, right = _unlabel(q["matching_left"]), _unlabel(q["matching_right"])
            pairs = q["answer_pairs"]
            if left and right and all(p["left"] in left and p["right"] in right for p in pairs):
                q["matching_left"], q["matching_right"] = list(left.values()), list(right.values())
                q["answer_pairs"] = [{"left": left[p["left"]], "right": right[p["right"]]} for p in pairs]
                fixed.append(q["question_id"])
        if q.get("format") == "sequence":
            items = _unlabel(q["sequence_items"])
            if items and all(x in items for x in q["correct_order"]):
                q["sequence_items"] = list(items.values())
                q["correct_order"] = [items[x] for x in q["correct_order"]]
                fixed.append(q["question_id"])
    return fixed


def organize(raw: str, lecture: dict, *, model: str | None = None) -> tuple[dict, dict]:
    """`(bank, info)`. lecture = {title, sources: [{id, kind, filename}]}."""
    bank, info = session.run_structured(organizer_prompt(raw, lecture), BANK, system=SYSTEM,
                                        label="정리", timeout=1200, model=model)
    fixed = tidy_labels(bank)
    if fixed and isinstance(bank.get("warnings"), list):
        bank["warnings"].append(f"[정리] 짝짓기·순서 라벨을 떼고 본문으로 맞췄다: {', '.join(fixed)}")
    return bank, info

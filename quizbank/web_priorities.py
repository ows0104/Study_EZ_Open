"""Read original web priority metadata without assigning or changing labels."""
from __future__ import annotations

import json
import re

from .session import SessionError

TIERS = {"Must-Know", "Essential", "Core", "Important", "Advanced", "Optional"}  # Preserve historical provenance.


def _plain(text: str) -> str:
    return re.sub(r"[`*]", "", text).strip()


def candidates(raw: str) -> list[dict]:
    """Support historical field blocks, question tables and compact blocks.

    IDs identify candidates for comparison, not proof that the current question
    still tests the original goal. Consumers must compare the question text.
    """
    rows: list[dict] = []

    def add(qid, tier, importance, question, origin):
        qid, tier, importance = map(_plain, (qid, tier, importance))
        tier = 'Essential' if tier == 'Must-Know' else tier
        if not qid or tier not in TIERS or not re.fullmatch("[1-5]", importance):
            raise SessionError("웹 우선순위: 원문의 ID·Tier·중요도를 읽지 못했습니다.")
        item = {"question_id": qid, "tier": tier, "importance": int(importance),
                "question": question.strip(), "origin": origin}
        if item not in rows:
            rows.append(item)

    # Some saved responses are explicit JSON exports, rather than web Markdown.
    # Preserve that provenance instead of calling it an original web decision.
    start = raw.find("{")
    if start >= 0:
        try:
            obj, _ = json.JSONDecoder().raw_decode(raw[start:])
        except ValueError:
            obj = None
        if isinstance(obj, dict) and isinstance(obj.get("questions"), list):
            for q in obj["questions"]:
                add(q["question_id"], q["tier"], str(q["importance"]), q["question"], "saved_json")
            return rows

    header = None
    for line in raw.splitlines():
        if not line.strip().startswith("|"):
            header = None
            continue
        cells = [c.strip() for c in re.split(r"(?<!\\)\|", line.strip().strip("|"))]
        names = [_plain(c).lower() for c in cells]
        if {"question_id", "tier", "importance", "question"}.issubset(names):
            header = names
            continue
        if header is None or all(re.fullmatch(r":?-+:?", c.replace(" ", "")) for c in cells):
            continue
        if len(cells) != len(header):
            # Historical tables sometimes omit a later format/direction cell.
            # Read only the explicit leading metadata; never guess shifted prose.
            if header[:4] == ["question_id", "concept_id", "tier", "importance"] and len(cells) >= 4:
                add(cells[0], cells[2], cells[3], "", "web_table_metadata_only")
                continue
            raise SessionError("웹 우선순위: 문항 표의 열 수가 맞지 않습니다.")
        row = dict(zip(header, cells, strict=True))
        add(row["question_id"], row["tier"], row["importance"], row["question"], "web_table")

    headings = list(re.finditer(r"^#{1,6}\s+(Q[A-Za-z0-9_-]+)([^\n]*)$", raw, re.M))
    for i, heading in enumerate(headings):
        body = raw[heading.end():headings[i + 1].start() if i + 1 < len(headings) else len(raw)]
        qid, tail = heading.groups()
        fields = [c.strip() for c in tail.split("|")][1:]
        if len(fields) >= 3 and fields[1] in TIERS:
            match = re.search(r"(?:^|\n)\s*문제:\s*([^\n]+)", body)
            add(qid, fields[1], fields[2], match[1] if match else "", "web_compact")
            continue
        def field(name):
            match = re.search(rf"^\s*(?:[-*]\s*)?{name}:\s*([^\n]+)", body, re.M)
            return match[1].strip() if match else None
        tier, importance = field("tier"), field("importance")
        if tier is not None or importance is not None:
            if tier is None or importance is None:
                raise SessionError(f"웹 우선순위: {qid} 메타데이터 일부가 없습니다.")
            add(qid, tier, importance, field("question") or "", "web_fields")
    return rows


def read(raw: str) -> list[dict]:
    """Return unambiguous records; repeated conflicting IDs need source review."""
    rows = candidates(raw)
    if len({r["question_id"] for r in rows}) != len(rows):
        raise SessionError("웹 우선순위: 중복 ID의 서로 다른 원문을 개별 확인해야 합니다.")
    return rows


def reference(raw: str) -> dict:
    """An auxiliary comparison cannot silently guess or block source review."""
    try:
        rows = candidates(raw)
    except (SessionError, KeyError, TypeError, ValueError) as cause:
        return {"status": "unavailable", "reason": str(cause), "candidates": []}
    return {"status": "available" if rows else "unavailable",
            "reason": "저장된 응답의 후보이며 현재 문항과의 목표 동등성·실제 생성 출처는 별도 확인이 필요합니다.",
            "candidates": rows}

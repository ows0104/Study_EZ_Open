"""Lossless reconstruction of the answers omitted from compact web blocks."""
from __future__ import annotations

import json
import re

from .schema import DIRECTIONS, FORMATS, TIERS
from server.app.bank_validation.cloze import INLINE, normalize_cloze
from .session import SessionError

# Conflict headings and references to other questions are not question blocks.
HEADER = re.compile(r"^#{1,6}[ \t]+(Q[A-Za-z0-9_-]+)([^\n]*)$", re.M)
LABEL = re.compile(r"^\s*([A-Z]\d*|\d+)\s*[:.)]\s*(.+?)\s*$")


def normalize_single_unit_lists(bank: dict) -> list[dict]:
    """Map one authored grading unit to basic without changing any authored text."""
    changes = []
    for question in bank.get('questions', []):
        units = question.get('answer_units')
        if (question.get('format') == 'list' and isinstance(units, list) and len(units) == 1
                and isinstance(units[0], str) and units[0].strip()
                and question.get('answer') == units[0]):
            question['format'] = 'basic'
            changes.append({'questionId': question['question_id'], 'from': 'list', 'to': 'basic',
                            'reason': 'one unchanged authored grading unit'})
    return changes


def _json_value(body: str, start: int) -> tuple[object, int]:
    """Decode an authored JSON value, allowing only a matched inline-code wrapper."""
    fragment = body[start:]
    wrapper = re.match(r"`{1,2}(?!`)", fragment)
    offset = wrapper.end() if wrapper else 0
    if wrapper:
        offset += len(fragment[offset:]) - len(fragment[offset:].lstrip(" \t"))
    value, size = json.JSONDecoder().raw_decode(fragment[offset:])
    end = offset + size
    if wrapper:
        end += len(fragment[end:]) - len(fragment[end:].lstrip(" \t"))
        ticks = wrapper[0]
        if fragment[end:end + len(ticks)] != ticks or fragment[end + len(ticks):].startswith("`"):
            raise ValueError("JSON inline-code wrapper is missing or contains trailing text")
        end += len(ticks)
    return value, end


def deduplicate_repeats(raw: str) -> tuple[str, list[str]]:
    """Collapse exact repeated compact blocks; conflicting versions remain an error."""
    headings = list(HEADER.finditer(raw))
    if not any("|" in h[2] for h in headings):
        return raw, []
    seen, skipped, repeated = {}, [], []
    for index, heading in enumerate(headings):
        end = headings[index + 1].start() if index + 1 < len(headings) else len(raw)
        following = re.search(r"^#{1,6}[ \t]+(?:CF\d+|Source Conflicts|출처 충돌|Statistics|통계)[ \t]*$",
                              raw[heading.end():end], re.M)
        if following:
            end = heading.end() + following.start()
        body = raw[heading.end():end]
        # These are response/chunk wrappers, never answer JSON or source text.
        body = re.sub(r"(?m)^[ \t]*(?:```(?:markdown|md)?|STUDYEZ_BANK_COMPLETE)[ \t]*$", "", body).strip()
        signature = (heading[0].strip(), body)
        qid = heading[1]
        if qid in seen:
            if seen[qid] != signature:
                raise SessionError(f"문항 ID 중복: {qid} — 내용이 다른 블록은 합칠 수 없습니다.")
            skipped.append((heading.start(), end))
            repeated.append(qid)
        else:
            seen[qid] = signature
    for start, end in reversed(skipped):
        raw = raw[:start] + raw[end:]
    return raw, repeated


def read_blocks(raw: str) -> list[dict]:
    """Read explicit metadata, answers and optional display text; the LLM organizes the rest."""
    raw, _ = deduplicate_repeats(raw)
    headings = list(HEADER.finditer(raw))
    if not any("|" in heading[2] for heading in headings):
        return []  # Older field blocks without compact metadata keep their existing path.
    blocks, seen = [], set()
    for i, heading in enumerate(headings):
        qid, tail = heading.groups()
        cells = [cell.strip() for cell in tail.split("|")]
        if len(cells) < 2 or cells[0] or cells[1] not in FORMATS:
            raise SessionError(f"{qid}: 문항 블록 형식·머리 오류")
        fmt, fields = cells[1], cells[2:]
        if qid in seen:
            raise SessionError(f"문항 ID 중복: {qid}")
        seen.add(qid)
        choice = fmt in ("mcq", "multi_select")
        if len(fields) != (5 if choice else 4):
            raise SessionError(f"{qid}: 문항 블록 머리의 필드 수 오류")
        tier, importance, difficulty, direction = fields[:4]
        tier = 'Essential' if tier == 'Must-Know' else tier
        mode = fields[4] if choice else "none"
        if tier not in (*TIERS, "Advanced") or direction not in DIRECTIONS or not all(
                re.fullmatch(r"[1-5]", n) for n in (importance, difficulty)) \
                or mode not in ("recall_first", "comparison", "none") or choice and mode == "none":
            raise SessionError(f"{qid}: 문항 블록 메타데이터 오류")
        body = raw[heading.end():headings[i + 1].start() if i + 1 < len(headings) else len(raw)]
        conflict = re.search(r'^#{1,6}[ \t]+CF[\w-]+[ \t]*$', body, re.M)
        if conflict:
            body = body[:conflict.start()]
        evidence, evidence_span = None, None
        evidence_marker = re.search(r"(?:^|\s|&#x20;)근거:[ \t]*(?=(?:`{1,2}(?!`)[ \t]*)?\{)", body)
        if evidence_marker:
            try:
                evidence, size = _json_value(body, evidence_marker.end())
                evidence_span = (evidence_marker.end(), evidence_marker.end() + size)
            except ValueError:
                pass  # Invalid display metadata is resolved in the evidence stage.
        depth = re.findall(r"(?:^|\s|&#x20;)심화:[ \t]*(true|false)\b", body)
        if len(depth) > 1 or (re.search(r"(?:^|\s|&#x20;)심화:", body) and not depth):
            raise SessionError(f"{qid}: 심화는 true 또는 false여야 합니다.")
        # Browser Markdown copying may put all labeled fields in one paragraph.
        # Decode the JSON value rather than assuming an answer occupies a whole line.
        values, position = {}, 0
        # Consume v1.52's retired hints too, so JSON strings remain intact.
        marker = re.compile(r"(?:^|\s|&#x20;)(정답|힌트|해설):[ \t]*")
        try:
            while match := marker.search(body, position):
                if evidence_span and evidence_span[0] <= match.start(1) < evidence_span[1]:
                    position = evidence_span[1]
                    continue
                name = match[1]
                try:
                    value, size = _json_value(body, match.end())
                except ValueError:
                    # A rationale can mention e.g. "Case 1 해설: ..." in prose.
                    # Ignore that mention only when a separate, line-aligned JSON
                    # field supplies the actual value. Never guess a missing value.
                    line = body[body.rfind("\n", 0, match.start(1)) + 1:match.start(1)]
                    actual = re.search(r"(?m)^[ \t]*" + name + r":[ \t]*(?=(?:`{1,2}(?!`)[ \t]*)?[\[\"])", body)
                    if re.match(r"[ \t]*(?:문제|출처|출제근거):", line) and actual:
                        position = match.end()
                        continue
                    raise
                if name in values:
                    raise SessionError(f"{qid}: {name} 필드 중복")
                values[name] = value
                position = match.end() + size
            units = values.get("정답")
            inline_question = None
            if fmt == "cloze":
                stem = re.search(r"(?:^|\s|&#x20;)문제:[ \t]*(.*?)(?=(?:\s|&#x20;)(?:정답|해설|출처|출제근거|근거|충돌):|\Z)", body, re.S)
                if stem and INLINE.search(stem[1]):
                    inline_question = stem[1].strip()
                    embedded = [m[1].strip() for m in INLINE.finditer(inline_question)]
                    if units is not None and units != embedded:
                        raise SessionError(f"{qid}: 발문과 별도 정답이 서로 다릅니다.")
                    units = embedded
        except ValueError as cause:
            raise SessionError(f"{qid}: 정답·힌트·해설 JSON 오류") from cause
        if not isinstance(units, list) or not units or not all(isinstance(u, str) and u.strip() for u in units):
            raise SessionError(f"{qid}: 정답은 비어 있지 않은 문자열 JSON 배열이어야 합니다.")
        if any(not isinstance(values.get(name, ""), str) for name in ("힌트", "해설")):
            raise SessionError(f"{qid}: 힌트·해설은 JSON 문자열이어야 합니다.")
        blocks.append({"question_id": qid, "format": fmt, "tier": "Important" if tier == "Advanced" else tier,
                       "importance": int(importance), "advanced": depth == ["true"],
                       "item_difficulty": int(difficulty), "retrieval_direction": direction,
                       "mcq_mode": mode, "units": units,
                       "explanation": values.get("해설", "")})
        if inline_question is not None:
            blocks[-1]["question"] = inline_question
        if evidence is not None:
            blocks[-1]["source_evidence"] = evidence
    return blocks


def require_ids(bank: dict, blocks: list[dict]) -> None:
    expected = [b["question_id"] for b in blocks]
    actual = [q["question_id"] for q in bank["questions"]]
    if blocks and (set(actual) != set(expected) or len(actual) != len(expected)):
        raise SessionError("문항 블록 정리에서 원문 문항 ID가 누락·추가·중복됐습니다.")


def _labels(items: list[str], qid: str) -> dict[str, str]:
    pairs = [LABEL.fullmatch(item) for item in items]
    if not items or not all(pairs) or len({m[1] for m in pairs}) != len(items):
        raise SessionError(f"{qid}: 보기의 ID·번호를 보존해야 합니다.")
    return {m[1]: m[2] for m in pairs}


def restore(bank: dict, blocks: list[dict]) -> None:
    """Expand authored answers by position/ID, without adding knowledge or regrading."""
    require_ids(bank, blocks)
    questions = {q["question_id"]: q for q in bank["questions"]}
    for block in blocks:
        qid, fmt, units = block["question_id"], block["format"], block["units"]
        q = questions[qid]
        q.update({key: value for key, value in block.items() if key not in ("units", "source_evidence")})
        if fmt == "cloze":
            q.update(normalize_cloze(q))
        if fmt in ("basic", "list", "cloze"):
            if fmt == "basic" and len(units) != 1:
                raise SessionError(f"{qid}: basic 정답은 한 단위여야 합니다.")
            q["answer_units"] = units.copy()
            if fmt == "cloze":
                if len(re.findall(r"\{\{c\d+\}\}", q["question"])) != len(units):
                    raise SessionError(f"{qid}: 빈칸 수와 정답 단위 수가 다릅니다.")
                answers = iter(units)
                q["answer"] = re.sub(r"\{\{c\d+\}\}", lambda _: next(answers), q["question"])
            else:
                q["answer"] = "\n".join(units)
        elif fmt == "ox":
            if len(units) != 1 or units[0] not in ("O", "X"):
                raise SessionError(f"{qid}: OX 정답은 O 또는 X 하나여야 합니다.")
            q["answer"], q["answer_units"] = units[0], units.copy()
        elif fmt in ("mcq", "multi_select"):
            options = {o["id"]: o["text"] for o in q["options"]}
            if len(options) != len(q["options"]) or len(set(units)) != len(units) or any(u not in options for u in units):
                raise SessionError(f"{qid}: 정답 선택지 ID 오류")
            q["correct_option_ids"] = units.copy()
            q["answer_units"] = [options[u] for u in units]
            q["answer"] = "\n".join(f"{u}. {options[u]}" for u in units)
        elif fmt == "matching":
            left, right = _labels(q["matching_left"], qid), _labels(q["matching_right"], qid)
            pairs = [re.fullmatch(r"(\d+)-([A-Z]\d*)", u) for u in units]
            if not all(pairs) or any(p[1] not in left or p[2] not in right for p in pairs) \
                    or len({p[1] for p in pairs}) != len(left) or len(pairs) != len(left):
                raise SessionError(f"{qid}: 정답 짝의 번호·ID 오류")
            q["matching_left"], q["matching_right"] = list(left.values()), list(right.values())
            q["answer_pairs"] = [{"left": left[p[1]], "right": right[p[2]]} for p in pairs]
            q["answer_units"] = [f"{left[p[1]]} - {right[p[2]]}" for p in pairs]
            q["answer"] = "\n".join(q["answer_units"])
        elif fmt == "sequence":
            items = _labels(q["sequence_items"], qid)
            if sorted(units) != sorted(items):
                raise SessionError(f"{qid}: 순서 정답은 모든 보기 ID의 순열이어야 합니다.")
            q["sequence_items"] = list(items.values())
            q["correct_order"] = [items[u] for u in units]
            q["answer_units"] = q["correct_order"].copy()
            q["answer"] = " → ".join(q["correct_order"])
    if blocks:
        bank["questions"] = [questions[b["question_id"]] for b in blocks]

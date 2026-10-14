"""Conservative answer-disclosure checks for V1 authoring."""
import html
import re
import unicodedata

CHOICE = ("mcq", "multi_select")
# Repeated causal verbs do not disclose which process changes or why.
# "Na 통로 억제 → 활동전위 생성은? / 억제" still requires a causal judgment.
GENERIC_PREDICATES = {"억제", "촉진", "차단", "증가", "감소", "상승", "하강", "활성화", "비활성화"}


def _text(value: str) -> str:
    text = html.unescape(unicodedata.normalize("NFKC", value)).casefold()
    return re.sub(r"\s+", " ", re.sub(r"[*_`]+", "", text)).strip()


def _without_candidates(stem: str, answer: str, question: dict) -> str:
    """Ignore an answer only at an explicit alternative, not elsewhere in prose."""
    spans = []
    basic = question['format'] == 'basic'
    prefix, separator, comparison = stem.partition(' 중 ')
    if separator and (basic or question.get('retrieval_direction') == 'discrimination') \
            and re.search(r'가장|어느|어떤|무엇|어디|어떻게|쪽|고르|선택|판단|분류', comparison):
        separators = list(re.finditer(r'[·,/]|(?:와|과)\s+', prefix))
        boundaries = [0] + [m.end() for m in separators]
        ends = [m.start() for m in separators] + [len(prefix)]
        parts = [prefix[start:end].strip() for start, end in zip(boundaries, ends)]
        if len(parts) >= 2 and all(parts) and len(set(parts)) >= 2:
            for start, end in zip(boundaries, ends):
                piece = prefix[start:end].rstrip()
                if piece.strip() == answer or piece.endswith(' ' + answer):
                    # Preserve preceding context: an earlier asserted answer
                    # must still be detected even when the last term is a choice.
                    spans.append((start + len(piece) - len(answer), start + len(piece)))
    if basic:
        for match in re.finditer(r'(?P<a>[^\s,?]+?)인가\s*[,?]\s*(?P<b>[^\s,?]+?)인가', stem):
            if match['a'] != match['b']:
                spans.extend(match.span(k) for k in ('a', 'b') if match[k] == answer)
    for start, end in sorted(set(spans), reverse=True):
        stem = stem[:start] + ' ' * (end - start) + stem[end:]
    return stem


def leaked_units(question: dict) -> list[str]:
    """Conservative literal disclosure check, never applied to choice candidates."""
    if question["format"] not in ("basic", "cloze", "list"):
        return []
    stem = _text(question["question"])
    found = []
    for unit in question["answer_units"]:
        answer = _text(unit)
        # A one-letter symbol or a one-syllable suffix is not useful evidence.
        if len(answer) < 2 or answer in GENERIC_PREDICATES:
            continue
        boundary = (r"(?<![a-z0-9])" if answer[0].isascii() and answer[0].isalnum() else "")
        boundary_end = (r"(?![a-z0-9])" if answer[-1].isascii() and answer[-1].isalnum() else "")
        if re.search(boundary + re.escape(answer) + boundary_end, _without_candidates(stem, answer, question)):
            found.append(unit)
    return found


def quality_errors(bank: dict) -> tuple[list[str], list[str]]:
    """New authoring checks leave existing 3.0 banks valid."""
    if bank["build_meta"]["schema_version"] != "3.1":
        return [], []
    errors, warnings = [], []
    for q in bank["questions"]:
        disclosed = leaked_units(q)
        if disclosed and len(disclosed) == len(q["answer_units"]):
            errors.append(f"{q['question_id']}: 발문에 모든 정답 단위 노출 — 복사로 답할 수 있음")
        elif disclosed:
            warnings.append(f"{q['question_id']}: 발문에 일부 정답 단위 노출 가능 — {', '.join(disclosed)}")
    return errors, warnings

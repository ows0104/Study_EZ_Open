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


def leaked_units(question: dict) -> list[str]:
    """Conservative literal disclosure check, never applied to choice candidates."""
    if question["format"] not in ("basic", "cloze", "list"):
        return []
    stem = _text(question["question"])
    # Enumerated candidates still require a comparison. Their presence alone
    # does not identify the answer (e.g. "UFH·LMWH·fondaparinux 중 … 가장 …?").
    candidate_prefix, separator, comparison = stem.partition(" 중 ")
    candidates = [item.strip() for item in re.split(r"[·,/]", candidate_prefix)]
    choosing = (question.get("retrieval_direction") == "discrimination" and separator
                and len(candidates) >= 2 and all(candidates)
                and re.search(r"가장|어느|어떤|무엇", comparison))
    found = []
    for unit in question["answer_units"]:
        answer = _text(unit)
        if choosing and answer in candidates and answer not in comparison:
            continue
        # A one-letter symbol or a one-syllable suffix is not useful evidence.
        if len(answer) < 2 or answer in GENERIC_PREDICATES:
            continue
        boundary = (r"(?<![a-z0-9])" if answer[0].isascii() and answer[0].isalnum() else "")
        boundary_end = (r"(?![a-z0-9])" if answer[-1].isascii() and answer[-1].isalnum() else "")
        if re.search(boundary + re.escape(answer) + boundary_end, stem):
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

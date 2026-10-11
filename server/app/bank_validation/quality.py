"""v4.1 authoring checks. Semantic novelty and medical truth still need review.

The older contract is intentionally unchanged. New first-pass coverage requires
one complete representative question, rather than silently losing a fact when
one of several unrelated questions sharing an objective is selected.
"""
import html
import re
import unicodedata
from collections import Counter

CHOICE = ("mcq", "multi_select")


def _text(value: str) -> str:
    text = html.unescape(unicodedata.normalize("NFKC", value)).casefold()
    return re.sub(r"\s+", " ", re.sub(r"[*_`]+", "", text)).strip()


def leaked_units(question: dict) -> list[str]:
    """Conservative literal disclosure check, never applied to choice candidates."""
    if question["format"] not in ("basic", "cloze", "list"):
        return []
    stem = _text(question["question"])
    found = []
    for unit in question["answer_units"]:
        answer = _text(unit)
        # A one-letter symbol or a one-syllable suffix is not useful evidence.
        if len(answer) < 2:
            continue
        boundary = (r"(?<![a-z0-9])" if answer[0].isascii() and answer[0].isalnum() else "")
        boundary_end = (r"(?![a-z0-9])" if answer[-1].isascii() and answer[-1].isalnum() else "")
        if re.search(boundary + re.escape(answer) + boundary_end, stem):
            found.append(unit)
    return found


def quality_errors(bank: dict, source_ids: set[str]) -> tuple[list[str], list[str]]:
    if bank["build_meta"]["schema_version"] != "4.1":
        return [], []
    errors, warnings = [], []
    questions = bank["questions"]
    for objective in bank["learning_objectives"]:
        oid = objective["objective_id"]
        representatives = [q for q in questions if q["primary_objective_id"] == oid and q["role"] == "learning"]
        if len(representatives) != 1:
            errors.append(f"objective {oid}: 대표 learning 문항은 정확히 하나 필요 — 독립 사실 분리 또는 누락 확인")
        elif objective["kind"] == "discrimination" and representatives[0]["format"] not in CHOICE:
            errors.append(f"objective {oid}: 비교·구별 요점의 대표 learning 문항은 객관식 필요")
    exams = {q["question_id"]: q for q in questions if q["role"] == "exam"}
    if exams and not any(q["role"] == "learning" and q["format"] in CHOICE for q in questions):
        errors.append("learning choices: 시험용 외에 평소 대표 학습용 객관식 필요")
    designs = bank.get("exam_design", [])
    if Counter(d["question_id"] for d in designs) != Counter({qid: 1 for qid in exams}):
        errors.append("exam_design: 시험 문항마다 정확히 한 출제 근거 필요 (없는 문항·중복 포함)")
    for design in designs:
        qid = design["question_id"]
        if not design["novelty"].strip():
            errors.append(f"{qid}: 기존 학습·기출과 달라진 판단 설명 필요")
        if any(r["source_id"] not in source_ids - {"EXT"} or not r["locator"].strip() for r in design["basis_refs"]):
            errors.append(f"{qid}: 비교한 원본 기출의 유효한 위치 필요")
    for q in questions:
        disclosed = leaked_units(q)
        if disclosed and len(disclosed) == len(q["answer_units"]):
            errors.append(f"{q['question_id']}: 발문에 모든 정답 단위 노출 — 복사로 답할 수 있음")
        elif disclosed:
            warnings.append(f"{q['question_id']}: 발문에 일부 정답 단위 노출 가능 — {', '.join(disclosed)}")
        if q["role"] != "exam":
            continue
        choices = sorted(_text(o["text"]) for o in q["options"])
        peers = [other["question_id"] for other in questions if other["question_id"] != q["question_id"]
                 and other["format"] in CHOICE and sorted(_text(o["text"]) for o in other["options"]) == choices]
        if peers:
            warnings.append(f"{q['question_id']}: {', '.join(peers)}와 같은 선지 구성 — 새로운 판단인지 대조 필요")
    return errors, warnings

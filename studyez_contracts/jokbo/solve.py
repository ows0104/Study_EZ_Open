"""jokbo-solve/1 — 사이트에서 강의별로 푸는 족보 한 강의분.

한 파일이 강의 하나다. 문항은 족보 원문 그대로(발문·선지 순서·그림·정답표)이고,
구획(`sections`)이 「올해와 같은 교수」를 앞에, 다른·미상 교수를 뒤에 세운다.

**정답과 해설은 출처가 다르다.** `answers`는 족보 답안지에서 온 것이고, 해설
(`explanation`)은 우리가 만든 것이다. 해설이 답안지 답에 의문을 달아도 `answers`를
바꾸지 않는다 — `explanation.answerCheck = "doubt"`와 `caution`으로 드러낸다.
답안지에 답이 없는 문항은 `answerStatus = "missing"`이고 채점하지 않는다. 해설이
추정한 답은 `explanation.proposedAnswers`에만 둔다.

표준 라이브러리만 쓴다. DB·서버·모델 호출에 의존하지 않는다.
"""

from __future__ import annotations

import re
from typing import Any

SCHEMA = "jokbo-solve/1"
EXPLAIN_SCHEMA = "jokbo-explain/1"

SECTION_KINDS = ("same", "other", "unknown")
_SECTION_ORDER = {k: i for i, k in enumerate(SECTION_KINDS)}

# key          답안지의 답 하나(또는 all_of 묶음)
# key-multiple 이의제기 등으로 인정 답이 여럿(one_of) — 아무거나 맞으면 정답
# all-correct  전원 정답 처리된 문항 — 무엇을 골라도 정답
# missing      답안지에 답이 없다 — 채점하지 않는다
ANSWER_STATUSES = ("key", "key-multiple", "all-correct", "missing")

ANSWER_MODES = ("one_of", "all_of")
VERIFICATIONS = ("verified", "corrected", "unverifiable", "pending")
PROFESSOR_SOURCES = ("notes", "timetable", "none")
BASIS_KINDS = ("notes", "knowledge")
ANSWER_CHECKS = ("agree", "doubt", "no-key")

_FIGURE = re.compile(r"^[A-Za-z0-9_.-]+\.(png|jpg|jpeg|gif|webp)$")


class JokboSolveError(ValueError):
    """계약 위반. 메시지에 위치를 적는다."""


def answer_status(answers: list[int], mode: str | None, all_correct: bool) -> str:
    if all_correct:
        return "all-correct"
    if not answers:
        return "missing"
    if len(answers) > 1 and (mode or "one_of") == "one_of":
        return "key-multiple"
    return "key"


def _need(cond: bool, where: str, msg: str) -> None:
    if not cond:
        raise JokboSolveError(f"{where}: {msg}")


def _str_list(v: Any) -> bool:
    return isinstance(v, list) and all(isinstance(x, str) for x in v)


def validate_explain(entry: Any, n_choices: int, where: str) -> None:
    """해설 한 칸. 강의 파일 안의 `explanation`과 explain 파일의 값이 같은 꼴이다."""
    _need(isinstance(entry, dict), where, "해설은 객체")
    _need(isinstance(entry.get("text"), str) and entry["text"].strip() != "", where, "text 비어 있음")
    notes = entry.get("choiceNotes")
    if n_choices:
        _need(_str_list(notes) and len(notes) == n_choices, where,
              f"choiceNotes는 선지 수({n_choices})와 같은 길이")
    else:
        _need(notes in (None, []), where, "선지 없는 문항에 choiceNotes")
    basis = entry.get("basis")
    _need(isinstance(basis, dict) and basis.get("kind") in BASIS_KINDS, where, "basis.kind")
    pages = basis.get("pages", [])
    _need(isinstance(pages, list) and all(isinstance(p, int) and p > 0 for p in pages), where, "basis.pages")
    _need(entry.get("answerCheck") in ANSWER_CHECKS, where, "answerCheck")
    proposed = entry.get("proposedAnswers", [])
    _need(isinstance(proposed, list) and all(isinstance(a, int) and 1 <= a <= max(n_choices, 1) for a in proposed),
          where, "proposedAnswers")
    caution = entry.get("caution")
    _need(caution is None or isinstance(caution, str), where, "caution")
    _need(entry.get("source") in (None, "studyez", "amgi"), where, "source")


def _validate_item(item: Any, where: str) -> None:
    _need(isinstance(item, dict), where, "문항은 객체")
    _need(isinstance(item.get("id"), str) and item["id"], where, "id")
    _need(isinstance(item.get("year"), int), where, "year")
    _need(isinstance(item.get("number"), int), where, "number")
    _need(isinstance(item.get("stem"), str) and item["stem"].strip() != "", where, "stem")
    choices = item.get("choices")
    _need(_str_list(choices), where, "choices")
    n = len(choices)
    answers = item.get("answers")
    _need(isinstance(answers, list) and all(isinstance(a, int) and 1 <= a <= n for a in answers),
          where, "answers는 1..선지 수")
    _need(len(set(answers)) == len(answers), where, "answers 중복")
    mode = item.get("answerMode")
    _need(mode in ANSWER_MODES, where, "answerMode")
    all_correct = bool(item.get("allCorrect"))
    status = item.get("answerStatus")
    _need(status in ANSWER_STATUSES, where, "answerStatus")
    _need(status == answer_status(answers, mode, all_correct), where,
          f"answerStatus {status}가 answers·answerMode·allCorrect와 다름")
    _need(item.get("verification") in VERIFICATIONS, where, "verification")
    figs = item.get("figures", [])
    _need(isinstance(figs, list), where, "figures")
    for i, f in enumerate(figs):
        _need(isinstance(f, dict) and isinstance(f.get("file"), str) and _FIGURE.match(f["file"]) is not None,
              f"{where}.figures[{i}]", "파일 이름")
    _need(item.get("repeatYears") is None or _str_list(item["repeatYears"]), where, "repeatYears")
    if item.get("explanation") is not None:
        validate_explain(item["explanation"], n, f"{where}.explanation")
        if status != "missing":
            _need(not item["explanation"].get("proposedAnswers"), where,
                  "답안지 답이 있는 문항에 proposedAnswers — 의문은 answerCheck=doubt·caution으로")
        else:
            _need(item["explanation"]["answerCheck"] == "no-key", where, "답 없는 문항의 answerCheck는 no-key")


def validate_lecture(doc: Any) -> None:
    """강의 한 편의 풀이 자료 전체를 검사한다. 통과하면 None."""
    _need(isinstance(doc, dict), "$", "객체")
    _need(doc.get("schema") == SCHEMA, "$.schema", SCHEMA)
    lec = doc.get("lecture")
    _need(isinstance(lec, dict), "$.lecture", "객체")
    _need(isinstance(lec.get("eventId"), str) and lec["eventId"], "$.lecture", "eventId")
    _need(lec.get("runId") is None or re.fullmatch(r"\d{6}_\d{2}", lec["runId"] or "") is not None,
          "$.lecture", "runId는 YYMMDD_NN")
    _need(_str_list(lec.get("currentProfessors")), "$.lecture", "currentProfessors")
    _need(lec.get("professorSource") in PROFESSOR_SOURCES, "$.lecture", "professorSource")

    items = doc.get("items")
    _need(isinstance(items, list) and items, "$.items", "문항 목록")
    ids: set[str] = set()
    for i, it in enumerate(items):
        _validate_item(it, f"$.items[{i}]")
        _need(it["id"] not in ids, f"$.items[{i}]", f"id 중복 {it['id']}")
        ids.add(it["id"])

    sections = doc.get("sections")
    _need(isinstance(sections, list) and sections, "$.sections", "구획 목록")
    seen: list[str] = []
    last = -1
    for i, sec in enumerate(sections):
        where = f"$.sections[{i}]"
        _need(isinstance(sec, dict) and sec.get("kind") in SECTION_KINDS, where, "kind")
        order = _SECTION_ORDER[sec["kind"]]
        _need(order >= last, where, "같은 교수 → 다른 교수 → 미상 순서")
        last = order
        _need(_str_list(sec.get("professors")), where, "professors")
        _need(_str_list(sec.get("years")), where, "years")
        _need(_str_list(sec.get("itemIds")) and sec["itemIds"], where, "itemIds")
        if sec["kind"] == "same":
            _need(bool(set(sec["professors"]) & set(lec["currentProfessors"])), where,
                  "same 구획은 올해 교수와 한 명 이상 겹친다")
        elif sec["kind"] == "other":
            _need(bool(sec["professors"]) and not set(sec["professors"]) & set(lec["currentProfessors"]),
                  where, "other 구획은 올해 교수와 겹치지 않는 알려진 교수")
        else:
            _need(not lec["currentProfessors"] or not sec["professors"], where,
                  "unknown 구획은 기출 교수 또는 올해 교수를 모를 때만")
        seen.extend(sec["itemIds"])
    _need(len(seen) == len(set(seen)), "$.sections", "한 문항이 두 구획에")
    _need(set(seen) == ids, "$.sections", "구획이 모든 문항을 정확히 한 번씩 덮어야 한다")

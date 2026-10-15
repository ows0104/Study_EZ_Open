"""Repair validation, source-audit and answer-review findings inside the CLI."""
from __future__ import annotations

import json
from pathlib import Path

import fitz
import jsonschema

from studyez_llm.pdf import render

from .coverage import _call, bank_hash
from .generate import item_quality_guidance, lecture_scope
from .points import STR, _array, _object
from .schema import BANK
from .session import SessionError
from .web_audit import parse_points

PROMPT = Path(__file__).parent / "prompts" / "repair-bank.md"
POINTS = _array(_object({"point_id": STR, "point": STR, "source_refs": STR}))
WRITTEN = _object({"written": {"type": "boolean", "enum": [True]},
                   "summary": STR, "changes": _array(STR)})


class RepairError(SessionError):
    """A completed repair produced an unusable candidate; retain the findings."""


def repair(bank: dict, raw: str, pdf: Path, title: str, sources: list[dict], findings: dict,
           out: Path, round_number: int, *, points: list[dict] | None = None,
           jokbo: Path | None = None, model: str | None = None,
           defer_structure: bool = False) -> tuple[dict, list[dict], dict, dict]:
    work = out / "repair" / str(round_number)
    work.mkdir(parents=True, exist_ok=True)
    for name in ("repaired-bank.json", "repaired-points.json", "changes.json"):
        (work / name).unlink(missing_ok=True)
    if points is None:
        try:
            points = parse_points(raw)
        except SessionError:
            points = []  # The CLI explicitly reconstructs a missing plan from source evidence.
    with fitz.open(pdf) as doc:
        count = len(doc)
        source_text = "\n\n".join(f"## PDF p.{i + 1}\n{p.get_text()}" for i, p in enumerate(doc))
    source_work = out / "repair" / "source-pages"
    images = render(pdf, f"1-{count}", source_work)
    for name, data in (("bank.json", bank), ("point-plan.json", points),
                       ("findings.json", findings), ("bank-schema.json", BANK),
                       ("point-schema.json", POINTS),
                       ("source-pages.json", [str(p.resolve()) for p in images]),
                       ("context.json", {"title": title, "sources": sources, "page_count": count,
                                         "lecture_scope": lecture_scope(title, sources)})):
        (work / name).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    (work / "source-text.md").write_text(source_text, encoding="utf-8")
    (work / "original-response.md").write_text(raw, encoding="utf-8")
    if jokbo:
        (work / "jokbo.md").write_text(jokbo.read_text(encoding="utf-8"), encoding="utf-8")
    prompt = PROMPT.read_text(encoding="utf-8")
    if defer_structure:
        prompt += "\n이번 실행은 문항 우선 내용 수정 단계다. concepts·retrieval_plan은 빈 배열, " \
            "각 concept_id는 빈 문자열, prerequisites는 빈 배열로 유지한다. " \
            "integration의 기초 연결을 포함한 학습 구조는 내용 검수 뒤 별도 CLI가 작성한다."
    prompt += "\n\n" + item_quality_guidance()
    written, info = _call(prompt, WRITTEN, work, model, "CLI 문항 수정·누락 보완")
    try:
        corrected = json.loads((work / "repaired-bank.json").read_text(encoding="utf-8-sig"))
        revised_points = json.loads((work / "repaired-points.json").read_text(encoding="utf-8-sig"))
        jsonschema.validate(corrected, BANK)
        jsonschema.validate(revised_points, POINTS)
    except (OSError, ValueError, jsonschema.ValidationError) as cause:
        raise RepairError(f"CLI 수정 파일이 없거나 스키마에 맞지 않습니다: {cause}") from cause
    if corrected["build_meta"] != bank["build_meta"]:
        raise RepairError("CLI 수정에서 강의 제목·스키마 버전을 바꿀 수 없습니다.")
    if defer_structure:
        from .question_first import require_draft
        try:
            require_draft(corrected)
        except SessionError as cause:
            raise RepairError(str(cause)) from cause
    ids = [p["point_id"] for p in revised_points]
    if not ids or len(ids) != len(set(ids)) or any(
            not all(value.strip() for value in p.values()) for p in revised_points):
        raise RepairError("CLI 수정 포인트의 ID·내용·근거가 없거나 ID가 중복됐습니다.")
    before = {q["question_id"]: q for q in bank["questions"]}
    after = {q["question_id"]: q for q in corrected["questions"]}
    audit = (findings.get("audit") or {}).get("webAudit") or {}
    duplicates = audit.get("duplicates", [])
    removable = {qid for group in duplicates for qid in group["question_ids"]}
    removed = before.keys() - after.keys()
    if not removed.issubset(removable) or any(
            removed.intersection(group["question_ids"]) and not (after.keys() & set(group["question_ids"]))
            for group in duplicates):
        raise RepairError("CLI 수정은 검수에서 확인한 중복만 통합할 수 있습니다. 정상 문항 ID를 보존하세요.")
    old_points = {p["point_id"] for p in points}
    excluded = {pid for issue in audit.get("plan_issues", []) if issue["kind"] == "out_of_scope"
                for pid in issue["point_ids"]}
    if not (old_points - set(ids)).issubset(excluded):
        raise RepairError("CLI 수정은 근거 없이 기존 출제 포인트를 제거할 수 없습니다.")
    changes = {"added": sorted(after.keys() - before.keys()), "removed": sorted(before.keys() - after.keys()),
               "modified": sorted(qid for qid in before.keys() & after.keys() if before[qid] != after[qid])}
    if corrected == bank and revised_points == points:
        raise RepairError("CLI 수정 결과에 변경이 없습니다. 미해결 검수 기록을 확인하세요.")
    if not written["summary"].strip() or not written["changes"] or any(not s.strip() for s in written["changes"]):
        raise RepairError("CLI 수정의 근거와 변경 기록이 없습니다.")
    log = {"round": round_number, **written, "questions": changes,
           "beforeHash": bank_hash(bank), "afterHash": bank_hash(corrected),
           "pointsChanged": revised_points != points}
    (work / "changes.json").write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "authored-points.json").write_text(json.dumps(revised_points, ensure_ascii=False, indent=2), encoding="utf-8")
    return corrected, revised_points, log, info

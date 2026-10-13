"""원본 PDF와 현 은행을 독립 대조하고, 기존 문항을 보존한 채 누락·객관식을 보강한다."""
from __future__ import annotations

import copy
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import fitz
import jsonschema

from studyez_llm import codex
from studyez_llm.pdf import render
from .generate import lecture_scope
from .schema import BANK, without_retired
from .validate import validate_bank
from .points import PLAN, MATCH_REPORT, shape_plan, match_report
from .classify import CLASSIFICATION, apply_classifications

PROMPTS = Path(__file__).parent / "prompts"
WRITTEN = {"type": "object", "properties": {"written": {"type": "boolean", "enum": [True]}},
           "required": ["written"], "additionalProperties": False}


def bank_hash(bank: dict) -> str:
    return hashlib.sha256(json.dumps(bank, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def supplement_tasks(report: dict) -> dict:
    """쪽별 UI 보고서의 중복 포인트를 모델 입력에서는 한 번만 보낸다."""
    gaps = {}
    for row in report["pages"]:
        for point in row["points"]:
            if point["status"] != "gap":
                continue
            task = gaps.setdefault(point["point_id"], {**point, "slides": []})
            task["slides"].append(row["page"])
    return {"summary": report["summary"], "gaps": list(gaps.values()), "mcq_opportunities": report["mcq_opportunities"]}


def _call(prompt: str, schema: dict, work: Path, model: str | None, label: str) -> tuple[dict, dict]:
    result = codex.run(prompt, blind=False, cwd=work, model=model, schema=schema, timeout=3600, label=label)
    try:
        output = json.loads(result["text"])
        jsonschema.validate(output, schema)
    except (ValueError, jsonschema.ValidationError) as cause:
        raise codex.SessionError(f"{label}: 구조화 출력 형식 오류: {cause}") from cause
    usage = result["usage"]
    return output, {"seconds": round(result["duration_ms"] / 1000, 1), "cost_usd": result["cost_usd"],
                    "input_tokens": usage["input_tokens"] + usage["cache_read_input_tokens"],
                    "output_tokens": usage["output_tokens"], "models": sorted(result["models"])}


def _supplement(work: Path, model: str | None) -> tuple[dict, dict]:
    """큰 보강본을 파일로 생성한다. 전체 JSON을 최종 응답에 중복 출력하지 않는다."""
    target = work / "supplement-bank.json"
    target.unlink(missing_ok=True)
    (work / "addition-schema.json").write_text(json.dumps(BANK, ensure_ascii=False), encoding="utf-8")
    prompt = (PROMPTS / "supplement.md").read_text(encoding="utf-8") + "\n\n" + (
        "이번 작업은 파일 출력 방식이다. addition-schema.json의 BANK schema를 읽고, 추가분 전체를 "
        "이 작업 폴더의 supplement-bank.json에 UTF-8 JSON으로 저장한다. Python 등으로 공통 빈 필드를 "
        "구성해도 된다. 모든 실제 문항·정답·선지·해설과 근거는 직접 작성한다. 기존 bank.json과 "
        "point-plan.json 및 원본 파일은 변경하지 않는다. 저장한 JSON을 스키마에 대조한다. "
        '최종 응답에는 전체 은행을 다시 출력하지 않고 {"written":true}만 반환한다.')
    _, info = _call(prompt, WRITTEN, work, model, "누락·객관식 보강")
    try:
        patch = json.loads(target.read_text(encoding="utf-8"))
        jsonschema.validate(patch, BANK)
    except (OSError, ValueError, jsonschema.ValidationError) as cause:
        raise codex.SessionError(f"보강 파일이 없거나 BANK 형식에 맞지 않습니다: {cause}") from cause
    return patch, info


def shape_report(report: dict, bank: dict, count: int) -> dict:
    """빠진 쪽·중복 쪽·없는 문항 참조를 검증 완료로 세지 않는다."""
    known = {q["question_id"] for q in bank["questions"]}
    pages: dict[int, dict] = {}
    for raw in report["pages"]:
        page = raw["page"]
        if page < 1 or page > count:
            raise codex.SessionError(f"원본 대조: PDF에 없는 쪽 {page}")
        if page in pages:
            raise codex.SessionError(f"원본 대조: 중복 쪽 {page}")
        row = copy.deepcopy(raw)
        if row["status"] == "excluded" and (not row["note"].strip() or row["points"]):
            raise codex.SessionError(f"원본 대조: p.{page} 제외 근거가 필요하다")
        if row["status"] == "checked" and not row["points"]:
            row.update(status="unreadable", note="검토할 출제 포인트가 보고되지 않았습니다.")
        for point in row["points"]:
            if not point["fact"].strip():
                raise codex.SessionError(f"원본 대조: p.{page} 빈 출제 포인트")
            point["question_ids"] = list(dict.fromkeys(qid for qid in point["question_ids"] if qid in known))
            if point["status"] == "covered" and not point["question_ids"]:
                point["status"] = "gap"
        pages[page] = row
    for page in range(1, count + 1):
        pages.setdefault(page, {"page": page, "status": "unreadable", "note": "검토 결과에 이 쪽이 없습니다.", "points": []})
    ordered = [pages[p] for p in sorted(pages)]
    gaps = sum(point["status"] == "gap" for row in ordered for point in row["points"])
    unreadable = sum(row["status"] == "unreadable" for row in ordered)
    return {**report, "pages": ordered, "status": "verified" if not gaps and not unreadable else "partial",
            "totalPages": count, "checkedPages": sum(row["status"] == "checked" for row in ordered),
            "excludedPages": sum(row["status"] == "excluded" for row in ordered),
            "unreadablePages": unreadable, "gapCount": gaps, "bankHash": bank_hash(bank),
            "checkedAt": datetime.now(UTC).isoformat()}


def merge_additions(bank: dict, patch: dict, source_ids: list[str]) -> dict:
    """원문과 ID를 유지한다. 잘못된 보강본이면 학습 은행에 적용하지 않는다."""
    old, patch = without_retired(bank), without_retired(patch)
    merged = copy.deepcopy(old)
    existing = {q["question_id"] for q in old["questions"]}
    if any(q["question_id"] in existing for q in patch["questions"]):
        raise codex.SessionError("보강 문항은 기존 question_id를 수정하거나 재사용할 수 없습니다.")
    for field, id_key in (("concepts", "concept_id"), ("retrieval_plan", "concept_id"), ("source_conflicts", "conflict_id")):
        indexed = {item[id_key]: item for item in merged[field]}
        for item in patch[field]:
            if item[id_key] not in indexed:
                fresh = copy.deepcopy(item)
                merged[field].append(fresh)
                indexed[item[id_key]] = fresh
            elif field == "concepts":
                for prop in ("core_facts", "source_refs", "related_concepts"):
                    indexed[item[id_key]][prop] += [value for value in item[prop] if value not in indexed[item[id_key]][prop]]
            elif field == "retrieval_plan":
                indexed[item[id_key]]["directions"] = list(dict.fromkeys(indexed[item[id_key]]["directions"] + item["directions"]))
            elif item != indexed[item[id_key]]:
                raise codex.SessionError("보강 과정에서 기존 출처 충돌 기록을 바꿀 수 없습니다.")
    merged["questions"] += patch["questions"]
    merged["audit_summary"]["changes"] += patch["audit_summary"]["changes"]
    checked = validate_bank(merged, source_ids)
    if not checked["pass"]:
        raise codex.SessionError("보강 문항 검증 실패: " + " · ".join(checked["errors"][:8]))
    return merged


def audit_and_supplement(bank: dict, pdf: Path, title: str, sources: list[dict], out: Path,
                         *, model: str | None = None, pdf_source: str = "S1", jokbo: Path | None = None) -> tuple[dict, dict, list[dict]]:
    work = out / "coverage"
    work.mkdir(parents=True, exist_ok=True)
    with fitz.open(pdf) as doc:
        count = len(doc)
        if not count:
            raise codex.SessionError("원본 대조: PDF가 비어 있습니다.")
        text = "\n\n".join(f"## {pdf_source} PDF p.{i + 1}\n{page.get_text()}" for i, page in enumerate(doc))
    (work / "source-text.md").write_text(text, encoding="utf-8")
    plan_work = work / "point-extraction"
    plan_work.mkdir(exist_ok=True)
    images = render(pdf, f"1-{count}", plan_work / "source-pages")
    (work / "source-pages.json").write_text(json.dumps([str(p.resolve()) for p in images]), encoding="utf-8")
    context = {"title": title, "sources": sources, "pdf_source": pdf_source, "page_count": count,
               "scope": lecture_scope(title, sources), "has_jokbo": jokbo is not None}
    if jokbo is not None:
        (work / "jokbo.md").write_text(jokbo.read_text(encoding="utf-8"), encoding="utf-8")
    (work / "context.json").write_text(json.dumps(context, ensure_ascii=False), encoding="utf-8")
    bank = without_retired(bank)
    usage = []

    # 이 작업 폴더에는 문제은행을 두지 않는다. 원본에서 포인트를 먼저 추출한다.
    for name in ("context.json", "source-text.md", "source-pages.json", "jokbo.md"):
        source = work / name
        if source.is_file():
            (plan_work / name).write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    raw_plan, info = _call((PROMPTS / "points.md").read_text(encoding="utf-8"), PLAN, plan_work, model, "① 出제 포인트 추출")
    plan = shape_plan(raw_plan, count)
    usage.append({"step": "출제 포인트 추출", **info})
    (work / "point-plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")

    def inspect(current: dict, label: str) -> dict:
        (work / "bank.json").write_text(json.dumps(current, ensure_ascii=False), encoding="utf-8")
        (work / "point-plan.json").write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
        output, info = _call((PROMPTS / "coverage.md").read_text(encoding="utf-8"), MATCH_REPORT, work, model, label)
        report = match_report(output, current, plan, count)
        usage.append({"step": label, **info})
        shaped = shape_report(report, current, count)
        shaped["gapCount"] = report["gapCount"]
        return shaped

    initial = inspect(bank, "원본 누락 검증")
    (work / "before.json").write_text(json.dumps(initial, ensure_ascii=False, indent=2), encoding="utf-8")
    additions = []
    final = initial
    for round_number in range(1, 4):
        if not final["gapCount"] and not final["mcq_opportunities"]:
            break
        (work / "before.json").write_text(json.dumps(final, ensure_ascii=False, indent=2), encoding="utf-8")
        (work / "tasks.json").write_text(json.dumps(supplement_tasks(final), ensure_ascii=False), encoding="utf-8")
        (work / f"before-{round_number}.json").write_text(json.dumps(final, ensure_ascii=False, indent=2), encoding="utf-8")
        patch, info = _supplement(work, model)
        usage.append({"step": "누락·객관식 보강", **info})
        (work / "additions.json").write_text(json.dumps(patch, ensure_ascii=False, indent=2), encoding="utf-8")
        (work / f"additions-{round_number}.json").write_text(json.dumps(patch, ensure_ascii=False, indent=2), encoding="utf-8")
        bank = merge_additions(bank, patch, [source["id"] for source in sources])
        additions += patch["questions"]
        final = inspect(bank, "보강 후 원본 재검증")
        if not patch["questions"]:
            break
    mcqs = [q for q in bank["questions"] if q["format"] in ("mcq", "multi_select")]
    if mcqs:
        classify_work = work / "classification"
        classify_work.mkdir(exist_ok=True)
        (classify_work / "questions.json").write_text(json.dumps(mcqs, ensure_ascii=False), encoding="utf-8")
        classified, info = _call((PROMPTS / "classify.md").read_text(encoding="utf-8"), CLASSIFICATION,
                                 classify_work, model, "객관식 유형 분류")
        usage.append({"step": "객관식 유형 분류", **info})
    else:
        classified = {"classifications": []}
    bank, classification = apply_classifications(bank, classified)
    (out / "classification.json").write_text(json.dumps(classification, ensure_ascii=False, indent=2), encoding="utf-8")
    final.update(addedQuestions=len(additions), addedMcq=sum(q["format"] in ("mcq", "multi_select") for q in additions),
                 bankHash=bank_hash(bank), classification=classification,
                 sourceSha256=hashlib.sha256(pdf.read_bytes()).hexdigest(), sourceFilename=pdf.name)
    (out / "coverage.json").write_text(json.dumps(final, ensure_ascii=False, indent=2), encoding="utf-8")
    return bank, final, usage

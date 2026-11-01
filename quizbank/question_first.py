"""Source-only targets and learning metadata connected after content review."""
from __future__ import annotations

import copy
import hashlib
import json
import re
import tempfile
from pathlib import Path

import fitz
import jsonschema

from studyez_llm.pdf import render
from .generate import item_quality_guidance, lecture_scope
from .points import PLAN, STR, _array, _object
from .point_refs import checked_plan
from .schema import BANK
from .session import SessionError

PROMPTS = Path(__file__).parent / "prompts"
POINTS = _array(_object({"point_id": STR, "point": STR, "source_refs": STR}))
STRUCTURE = _object({
    "concepts": BANK["properties"]["concepts"],
    "retrieval_plan": BANK["properties"]["retrieval_plan"],
    "assignments": _array(_object({"question_id": STR, "concept_id": STR, "prerequisites": _array(STR)})),
    "summary": STR,
})
STRUCTURE["properties"]["assignments"]["items"]["properties"]["learning_page"] = {
    "type": "integer", "minimum": 0}
# Saved historical structures remain readable. New CLI results must place every
# question using the relation actually tested, independently of evidence images.
SEQUENCED_STRUCTURE = copy.deepcopy(STRUCTURE)
SEQUENCED_STRUCTURE["properties"]["assignments"]["items"]["required"].append("learning_page")


def enabled(version: str) -> bool:
    match = re.fullmatch(r"v?(\d+)\.(\d+)(?:\.\d+)?", version)
    return bool(match and int(match[1]) == 1 and int(match[2]) >= 42)


def as_draft(bank: dict) -> dict:
    """Reset only learning metadata when resuming this pipeline."""
    draft = copy.deepcopy(bank)
    draft["concepts"], draft["retrieval_plan"] = [], []
    for q in draft["questions"]:
        q["concept_id"], q["prerequisites"] = "", []
        q.pop("learning_page", None)
    return draft


def require_draft(bank: dict) -> None:
    if bank.get("concepts") or bank.get("retrieval_plan") or any(
            q.get("concept_id") or q.get("prerequisites") for q in bank.get("questions", [])):
        raise SessionError("문항 우선 단계에서 개념·회상 계획·선행 관계를 먼저 작성할 수 없습니다.")


def content_hash(bank: dict) -> str:
    payload = {"build_meta": bank["build_meta"], "source_summary": bank["source_summary"],
               "source_conflicts": bank["source_conflicts"],
               "questions": [{k: v for k, v in q.items() if k not in ("concept_id", "prerequisites", "learning_page")}
                             for q in bank["questions"]]}
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def point_origin(pdf: Path, title: str, sources: list[dict], *, pdf_source: str = "S1",
                 jokbo: Path | None = None) -> dict:
    return {"origin": "independent-source-only", "title": title, "sources": sources,
            "scope": lecture_scope(title, sources), "pdf_source": pdf_source,
            "sourceSha256": hashlib.sha256(pdf.read_bytes()).hexdigest(),
            "jokboSha256": hashlib.sha256(jokbo.read_bytes()).hexdigest() if jokbo else None}


def cached_points(root: Path, pdf: Path, title: str, sources: list[dict], *, pdf_source: str = "S1",
                  jokbo: Path | None = None) -> Path | None:
    """Only completed source-matching independent lists can bypass a new CLI extraction."""
    expected = point_origin(pdf, title, sources, pdf_source=pdf_source, jokbo=jokbo)
    origins = sorted(root.rglob("independent-origin.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    for origin in origins:
        candidate = origin.with_name("authored-points.json")
        try:
            if json.loads(origin.read_text(encoding="utf-8")) != expected:
                continue
            rows = json.loads(candidate.read_text(encoding="utf-8"))
            jsonschema.validate(rows, POINTS)
            ids = [row["point_id"] for row in rows]
            if rows and len(set(ids)) == len(ids) and all(all(v.strip() for v in row.values()) for row in rows):
                return candidate
        except (OSError, ValueError, jsonschema.ValidationError):
            continue
    return None


def extract_points(pdf: Path, title: str, sources: list[dict], out: Path, *, pdf_source: str = "S1",
                   jokbo: Path | None = None, reuse: Path | None = None, model: str | None = None) -> tuple[list[dict], list[dict]]:
    """Never put a web response or bank into the extraction working directory."""
    from .coverage import _call
    if any(s.get("kind") == "jokbo" for s in sources) and (jokbo is None or not jokbo.is_file()):
        raise SessionError("독립 출제포인트 추출에 등록된 족보 원본이 필요합니다.")
    identity = point_origin(pdf, title, sources, pdf_source=pdf_source, jokbo=jokbo)
    if reuse is not None:
        try:
            origin = json.loads((reuse.parent / "independent-origin.json").read_text(encoding="utf-8"))
            points = json.loads(reuse.read_text(encoding="utf-8"))
            jsonschema.validate(points, POINTS)
        except (OSError, ValueError, jsonschema.ValidationError) as cause:
            raise SessionError("문항 우선 재개에는 원본 독립 추출 이력이 있는 포인트가 필요합니다.") from cause
        if origin != identity:
            raise SessionError("독립 출제포인트의 원본·족보·강의 범위가 달라졌습니다.")
        usage = []
    else:
        work = Path(tempfile.mkdtemp(prefix="source-only-", dir=out))
        with fitz.open(pdf) as doc:
            count = len(doc)
            text = "\n\n".join(f"## {pdf_source} PDF p.{i + 1}\n{p.get_text()}" for i, p in enumerate(doc))
        if not count:
            raise SessionError("독립 출제포인트 추출 원본이 비어 있습니다.")
        images = render(pdf, f"1-{count}", work / "source-pages")
        for name, data in (("context.json", {**identity, "page_count": count}),
                           ("source-pages.json", [str(p.resolve()) for p in images])):
            (work / name).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        (work / "source-text.md").write_text(text, encoding="utf-8")
        if jokbo:
            (work / "jokbo.md").write_text(jokbo.read_text(encoding="utf-8"), encoding="utf-8")
        prompt = (PROMPTS / "points.md").read_text(encoding="utf-8") + "\n\n" + item_quality_guidance()
        raw, info = _call(prompt, PLAN, work, model, "원본 독립 출제포인트 추출")
        (out / "independent-plan.raw.json").write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
        plan, reference_usage = checked_plan(raw, count, work, out, model, _call)
        (out / "independent-plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
        if plan["unreadable_pages"]:
            raise SessionError("독립 출제포인트 추출에서 읽지 못한 원본 쪽이 있습니다.")
        points = [{"point_id": t["point_id"], "point": t["target"],
                   "source_refs": "; ".join(f"{pdf_source} p.{p}" for p in t.get("slides", objective["slides"]))}
                  for objective in plan["objectives"] for t in objective["retrieval_targets"]]
        usage = [{"step": "원본 독립 출제포인트 추출", **info}, *reference_usage]
    ids = [p["point_id"] for p in points]
    if not ids or len(set(ids)) != len(ids) or any(not all(v.strip() for v in p.values()) for p in points):
        raise SessionError("독립 출제포인트의 ID·내용·근거가 없거나 중복됐습니다.")
    (out / "independent-origin.json").write_text(json.dumps(identity, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "authored-points.json").write_text(json.dumps(points, ensure_ascii=False, indent=2), encoding="utf-8")
    return points, usage


def _checked_assignments(bank: dict, structure: dict) -> dict:
    try:
        jsonschema.validate(structure, STRUCTURE)
    except jsonschema.ValidationError as cause:
        raise SessionError(f"사후 학습 구조의 형식 오류: {cause.message}") from cause
    assignments = {a["question_id"]: a for a in structure["assignments"]}
    ids = [q["question_id"] for q in bank["questions"]]
    if set(assignments) != set(ids) or len(structure["assignments"]) != len(ids):
        raise SessionError("사후 학습 구조는 모든 기존 문항을 정확히 한 번 연결해야 합니다.")
    concepts = [c["concept_id"] for c in structure["concepts"]]
    plans = {p["concept_id"]: p for p in structure["retrieval_plan"]}
    if len(set(concepts)) != len(concepts) or set(plans) != set(concepts) or len(plans) != len(structure["retrieval_plan"]):
        raise SessionError("사후 개념과 회상 계획은 같은 고유 ID로 빠짐없이 연결해야 합니다.")
    if {a["concept_id"] for a in assignments.values()} != set(concepts):
        raise SessionError("사후 개념은 실제 문항에 연결되어야 합니다.")
    return assignments


def resolve_directions(bank: dict, structure: dict) -> tuple[dict, list[dict]]:
    """Derive redundant plan directions from immutable questions and checked links.

    This does not infer new retrieval targets or change the CLI's concept grouping.
    Keep the raw CLI response separately so every corrected aggregate is traceable.
    """
    assignments = _checked_assignments(bank, structure)
    directions = {c["concept_id"]: set() for c in structure["concepts"]}
    for q in bank["questions"]:
        directions[assignments[q["question_id"]]["concept_id"]].add(q["retrieval_direction"])
    resolved, corrections = copy.deepcopy(structure), []
    for plan in resolved["retrieval_plan"]:
        actual = sorted(directions[plan["concept_id"]])
        if set(plan["directions"]) != set(actual) or len(plan["directions"]) != len(actual):
            corrections.append({"concept_id": plan["concept_id"], "reported": plan["directions"],
                                "actual": actual})
        plan["directions"] = actual
    return resolved, corrections


def apply_structure(bank: dict, structure: dict) -> dict:
    assignments = _checked_assignments(bank, structure)
    plans = {p["concept_id"]: p for p in structure["retrieval_plan"]}
    for cid, plan in plans.items():
        directions = {q["retrieval_direction"] for q in bank["questions"] if assignments[q["question_id"]]["concept_id"] == cid}
        if set(plan["directions"]) != directions or len(plan["directions"]) != len(directions):
            raise SessionError("사후 회상 계획의 방향은 실제 연결 문항과 일치해야 합니다.")
    result = copy.deepcopy(bank)
    result["concepts"], result["retrieval_plan"] = structure["concepts"], structure["retrieval_plan"]
    for q in result["questions"]:
        assignment = assignments[q["question_id"]]
        q["concept_id"], q["prerequisites"] = assignment["concept_id"], assignment["prerequisites"]
        q.pop("learning_page", None)
        if assignment.get("learning_page", 0) > 0:
            q["learning_page"] = assignment["learning_page"]
    if content_hash(result) != content_hash(bank):
        raise SessionError("사후 학습 구조 연결에서 검수한 문항 내용이 바뀌었습니다.")
    return result


def connect(bank: dict, points: list[dict], title: str, out: Path, *, model: str | None = None) -> tuple[dict, dict, dict]:
    from .coverage import _call
    work = out / "learning-structure"
    work.mkdir(exist_ok=True)
    for name, data in (("bank.json", bank), ("point-plan.json", points), ("context.json", {"title": title})):
        (work / name).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    for name in ("coverage.json", "review.json"):
        if (out / name).is_file():
            (work / name).write_text((out / name).read_text(encoding="utf-8"), encoding="utf-8")
    prompt = (PROMPTS / "learning-structure.md").read_text(encoding="utf-8") + "\n\n" + item_quality_guidance()
    structure, info = _call(prompt, SEQUENCED_STRUCTURE, work, model, "검수 후 개념도·회상 계획 연결")
    (out / "learning-structure.raw.json").write_text(json.dumps(structure, ensure_ascii=False, indent=2), encoding="utf-8")
    structure, corrections = resolve_directions(bank, structure)
    (out / "learning-structure.resolution.json").write_text(json.dumps(
        {"directionCorrections": corrections, "structure": structure}, ensure_ascii=False, indent=2), encoding="utf-8")
    return apply_structure(bank, structure), structure, info

"""CLI가 원본·문제·정답을 대조해 선택한 최소 근거 지면. 문항 내용은 수정하지 않는다."""
from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import fitz

from server.app.bank_validation.slide_focus import question_hash, authored_hash
from .coverage import _call
from .points import STR, INT, _array, _object
from .session import SessionError
from . import evidence_sources

PROMPT = Path(__file__).parent / "prompts/slide-focus.md"
REPORT = _object({"selections": _array(_object({
    "question_id": STR, "pool_id": STR, "candidate_id": STR,
    "mode": {"type": "string", "enum": ["single", "linked", "unresolved"]},
    "reason": STR, "slides": _array(_object({"source_id": STR, "page": INT, "evidence": STR})),
    "unresolved_cause": {"type": "string", "enum": ["", "exam_only", "partial_support", "source_conflict", "unsupported", "uncertain"]},
    "searched_sources": _array(STR),
    "exam_pages": _array(_object({"source_id": STR, "page": INT, "evidence": STR})),
}))})


def targets(bank: dict) -> list[dict]:
    rows = []
    for question in bank["questions"]:
        q = {key: question.get(key) for key in (
            "question_id", "question", "answer", "answer_units", "explanation", "format", "source_refs",
            "options", "correct_option_ids", "answer_pairs", "correct_order", "option_explanations")}
        rows.append({**q, "pool_id": "", "candidate_id": ""})
        for pool in question.get("option_pools", []):
            for candidate in pool["candidates"]:
                rows.append({"question_id": question["question_id"], "question": question["question"],
                             "pool_id": pool["pool_id"], **candidate})
    return rows


def identity(row: dict) -> tuple[str, str, str]:
    return row["question_id"], row["pool_id"], row["candidate_id"]


def shape(raw: dict, bank: dict, page_count: int, source_hash: str, *, sources: dict | None = None) -> dict:
    expected = {identity(row) for row in targets(bank)}
    seen = set()
    questions = {q["question_id"]: {"questionHash": question_hash(q), "candidates": {}} for q in bank["questions"]}
    for row in raw["selections"]:
        key = identity(row)
        if key not in expected or key in seen:
            raise SessionError("핵심 근거 선택: 없는 대상 또는 중복 대상")
        seen.add(key)
        slides = row["slides"]
        mode = row["mode"]
        if mode not in ("single", "linked", "unresolved") or not row["reason"].strip() or mode == "single" and len(slides) != 1 \
                or mode == "linked" and len(slides) < 2 or mode == "unresolved" and slides:
            raise SessionError(f"{key}: 근거 장수와 선택 이유가 선택 유형에 맞지 않습니다.")
        pages = [(s.get("source_id") or "self", s["page"]) for s in slides]
        limits = {"self": page_count, **{sid: m["pageCount"] for sid, m in (sources or {}).items()}}
        if len(set(pages)) != len(pages) or any(sid not in limits or type(p) is not int or not 1 <= p <= limits[sid] for sid, p in pages) \
                or any(not s["evidence"].strip() for s in slides):
            raise SessionError(f"{key}: 실제 지면 번호와 구체적인 근거가 필요합니다.")
        selection = {k: row[k] for k in ("mode", "reason", "slides")}
        if sources and mode == "unresolved":
            if row.get("unresolved_cause") not in ("exam_only", "partial_support", "source_conflict", "unsupported", "uncertain") \
                    or not set(limits) <= set(row.get("searched_sources", [])):
                raise SessionError(f"{key}: 미선정은 전체 강의 검색 기록과 구체적인 원인이 필요합니다.")
        for field in ("unresolved_cause", "searched_sources"):
            if field in row:
                selection[field] = row[field]
        exam_pages = row.get('exam_pages', [])
        if any((s.get('source_id') or 'self') not in limits or type(s.get('page')) is not int
               or not 1 <= s['page'] <= limits[s.get('source_id') or 'self'] or not s.get('evidence', '').strip()
               for s in exam_pages):
            raise SessionError(f'{key}: 첨부 기출도 실제 원본과 쪽·근거가 필요합니다.')
        if exam_pages:
            selection['exam_pages'] = exam_pages
        if row["pool_id"]:
            questions[row["question_id"]]["candidates"][f"{row['pool_id']}/{row['candidate_id']}"] = selection
        else:
            questions[row["question_id"]]["base"] = selection
    if seen != expected:
        raise SessionError(f"핵심 근거 선택: 대상 {len(expected - seen)}개 누락")
    return {"version": 3 if sources else 2, "sourceSha256": source_hash, "checkedAt": datetime.now(UTC).isoformat(),
            "questions": questions, **({"sources": sources} if sources else {})}


def select(bank: dict, pdf: Path, out: Path, *, model: str | None = None,
           authored: dict | None = None, related: dict[str, Path] | None = None,
           source_cache: Path | None = None, jokbo: Path | None = None) -> tuple[dict, list[dict]]:
    out.mkdir(parents=True, exist_ok=True)
    source_hash = hashlib.sha256(pdf.read_bytes()).hexdigest()
    related = {sid: path for sid, path in (related or {}).items() if path.resolve() != pdf.resolve()}
    sources = {sid: evidence_sources.describe(path, sid) for sid, path in related.items()}
    if sources:
        sources["self"] = evidence_sources.describe(pdf)
    inputs = targets(bank)
    signature = hashlib.sha256(json.dumps({"targets": inputs, "source": source_hash, "authored": authored or {},
        "sources": sources, "jokbo": jokbo.read_text(encoding="utf-8") if jokbo else "",
        "prompt": PROMPT.read_text(encoding="utf-8")}, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    cached = out / "slide-focus.json"
    if cached.is_file():
        report = json.loads(cached.read_text(encoding="utf-8"))
        if report.get("inputHash") == signature:
            return report, []
    with fitz.open(pdf) as doc:
        count = doc.page_count
    preselected = []
    for question in bank["questions"]:
        record = (authored or {}).get(question["question_id"], {})
        metadata = record.get("evidence")
        if record.get("authoredHash") != authored_hash(question) or not isinstance(metadata, dict):
            continue
        # An author's absence claim is a search task, never a reusable proof of absence.
        if metadata.get("mode") == "unresolved":
            continue
        row = {"question_id": question["question_id"], "pool_id": "", "candidate_id": "",
               **{k: metadata.get(k) for k in ("mode", "reason", "slides")}}
        try:
            shape({"selections": [row]}, {"questions": [{**question, "option_pools": []}]}, count, source_hash, sources=sources)
        except (SessionError, TypeError, KeyError, AttributeError):
            continue
        preselected.append(row)
    covered = {identity(row) for row in preselected}
    inputs = [row for row in inputs if identity(row) not in covered]
    usage = None
    if not inputs:
        raw = {"selections": preselected}
        report = {**shape(raw, bank, count, source_hash, sources=sources), "inputHash": signature,
                  "selectionOrigin": "authored", "authoredCount": len(preselected), "reselectedCount": 0}
        (out / "slide-focus.raw.json").write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
        cached.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return report, []
    own = evidence_sources.prepare(pdf, out)
    paths = own["images"]
    catalog = {"self": {**own, **evidence_sources.describe(pdf)}}
    for sid, path in related.items():
        cache = (source_cache or out / "related-sources") / sources[sid]["sourceSha256"]
        catalog[sid] = {**evidence_sources.prepare(path, cache), **sources[sid]}
    (out / "sources.json").write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "jokbo.md").write_text(jokbo.read_text(encoding="utf-8") if jokbo else "첨부 족보 없음", encoding="utf-8")
    (out / "source-pages.json").write_text(json.dumps(paths), encoding="utf-8")
    (out / "targets.json").write_text(json.dumps(inputs, ensure_ascii=False), encoding="utf-8")
    raw, usage = _call(PROMPT.read_text(encoding="utf-8"), REPORT, out, model, "문제·정답 핵심 근거 지면 선택")
    (out / "slide-focus.raw.json").write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
    raw["selections"] = preselected + raw["selections"]
    report = {**shape(raw, bank, count, source_hash, sources=sources), "inputHash": signature,
              "selectionOrigin": "mixed" if preselected else "reviewed", "authoredCount": len(preselected), "reselectedCount": len(inputs)}
    (out / "slide-focus.raw.json").write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
    cached.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "usage.json").write_text(json.dumps(usage, ensure_ascii=False), encoding="utf-8")
    return report, [usage]

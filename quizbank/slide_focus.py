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

PROMPT = Path(__file__).parent / "prompts/slide-focus.md"
REPORT = _object({"selections": _array(_object({
    "question_id": STR, "pool_id": STR, "candidate_id": STR,
    "mode": {"type": "string", "enum": ["single", "linked", "unresolved"]},
    "reason": STR, "slides": _array(_object({"page": INT, "evidence": STR})),
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


def shape(raw: dict, bank: dict, page_count: int, source_hash: str) -> dict:
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
        pages = [s["page"] for s in slides]
        if len(set(pages)) != len(pages) or any(type(p) is not int or not 1 <= p <= page_count for p in pages) \
                or any(not s["evidence"].strip() for s in slides):
            raise SessionError(f"{key}: 실제 지면 번호와 구체적인 근거가 필요합니다.")
        selection = {k: row[k] for k in ("mode", "reason", "slides")}
        if row["pool_id"]:
            questions[row["question_id"]]["candidates"][f"{row['pool_id']}/{row['candidate_id']}"] = selection
        else:
            questions[row["question_id"]]["base"] = selection
    if seen != expected:
        raise SessionError(f"핵심 근거 선택: 대상 {len(expected - seen)}개 누락")
    return {"version": 2, "sourceSha256": source_hash, "checkedAt": datetime.now(UTC).isoformat(),
            "questions": questions}


def select(bank: dict, pdf: Path, out: Path, *, model: str | None = None,
           authored: dict | None = None) -> tuple[dict, list[dict]]:
    out.mkdir(parents=True, exist_ok=True)
    source_hash = hashlib.sha256(pdf.read_bytes()).hexdigest()
    inputs = targets(bank)
    signature = hashlib.sha256(json.dumps({"targets": inputs, "source": source_hash, "authored": authored or {},
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
        row = {"question_id": question["question_id"], "pool_id": "", "candidate_id": "",
               **{k: metadata.get(k) for k in ("mode", "reason", "slides")}}
        try:
            shape({"selections": [row]}, {"questions": [{**question, "option_pools": []}]}, count, source_hash)
        except (SessionError, TypeError, KeyError, AttributeError):
            continue
        preselected.append(row)
    covered = {identity(row) for row in preselected}
    inputs = [row for row in inputs if identity(row) not in covered]
    usage = None
    if not inputs:
        raw = {"selections": preselected}
        report = {**shape(raw, bank, count, source_hash), "inputHash": signature,
                  "selectionOrigin": "authored", "authoredCount": len(preselected), "reselectedCount": 0}
        (out / "slide-focus.raw.json").write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
        cached.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return report, []
    images = out / "source-pages"
    images.mkdir(exist_ok=True)
    with fitz.open(pdf) as doc:
        count = doc.page_count
        (out / "source-text.md").write_text("\n\n".join(
            f"## PDF p.{i + 1}\n{page.get_text()}" for i, page in enumerate(doc)), encoding="utf-8")
        paths = []
        for i, page in enumerate(doc):
            image = images / f"page-{i + 1:04d}.png"
            if not image.is_file():
                page.get_pixmap(matrix=fitz.Matrix(1.2, 1.2), alpha=False).save(image)
            paths.append(str(image.resolve()))
    (out / "source-pages.json").write_text(json.dumps(paths), encoding="utf-8")
    (out / "targets.json").write_text(json.dumps(inputs, ensure_ascii=False), encoding="utf-8")
    raw, usage = _call(PROMPT.read_text(encoding="utf-8"), REPORT, out, model, "문제·정답 핵심 근거 지면 선택")
    (out / "slide-focus.raw.json").write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
    raw["selections"] = preselected + raw["selections"]
    report = {**shape(raw, bank, count, source_hash), "inputHash": signature,
              "selectionOrigin": "mixed" if preselected else "reviewed", "authoredCount": len(preselected), "reselectedCount": len(inputs)}
    (out / "slide-focus.raw.json").write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
    cached.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "usage.json").write_text(json.dumps(usage, ensure_ascii=False), encoding="utf-8")
    return report, [usage]

"""Public question/answer projections and signed evidence slides."""
from __future__ import annotations

import hashlib
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app import bank_edits, bank_excluded, bank_personal
from app.bank_validation.choice_mode import choice_mode
from app.bank_validation.evidence_resolution import (
    primary_references as exam_primary_references, status as evidence_status,
)
from app.bank_validation.jokbo_pages import references as jokbo_references
from app.bank_validation.priorities import priority_fields
from app.bank_validation.slide_focus import (
    all_selected_pages, all_selected_references, external_filename, question_hash, selected_references,
    source_id,
)
from app.models import Asset, BankState, QuizBank, SLIDE_KINDS
from app.storage import ObjectStorage, StorageNotConfigured
from app.study_engine.engine import target_for
from app.study_engine.matching import matching_presentation
from app.study_engine.personal_priority import question_priority


ANSWER_FIELDS = ("answer", "answer_units", "explanation", "correct_option_ids", "answer_pairs", "correct_order", "option_explanations", "option_pools", "choice_variant")


def _public(q: dict, *, bank: dict, show_choices: bool = True) -> dict:
    q = matching_presentation(priority_fields(q, question=True))
    out = {**{k: v for k, v in q.items() if k not in ANSWER_FIELDS}, "mcq_mode": choice_mode(q)}
    out.pop("hint", None)  # Retired experiment fields can remain in older stored JSON.
    out.pop("personalSlideReferences", None)
    if q.get('stimuli'):
        from studyez_contracts.roots.media import public_images
        out['stimuli']=public_images(q)
    out["targetMastery"] = target_for(bank, q)["effective"]
    if not show_choices and out["mcq_mode"] == "recall_first":
        out["options"] = []
    return out


def _served_question(db: Session, row: QuizBank, user_id: str, bank: dict, served: dict,
                     *, prepared_entry: dict | None = None) -> dict:
    original = next(q for q in bank["questions"] if q["question_id"] == served["question_id"])
    personal = (bank_personal.apply_edit(original, prepared_entry["personal_edits"].get(original["question_id"]))
                if prepared_entry is not None and "personal_edits" in prepared_entry
                else bank_personal.apply(db, row, user_id, original))
    snapshot = served.get("question_snapshot") or {}
    # Explicit private corrections take effect immediately and disable pools.
    # A reset during the same exposure restores the original authored options.
    # Freeze the presented choices and scoring, but show current priority labels
    # after a metadata-only review without resetting this exposure or its token.
    question = personal if personal.get("personalAdded") or personal.get("personalEdited") or snapshot.get("personalEdited") else snapshot or personal
    metadata = priority_fields(original, question=True)
    if prepared_entry is not None:
        current = prepared_entry["state"]
    else:
        state = db.get(BankState, (user_id, row.subject, row.run_id))
        current = state.state if state and state.build_id == row.build_id else {}
    metadata = question_priority(metadata, current)
    out = {**question, **{k: metadata[k] for k in ("tier", "importance", "advanced")},
           "presentationSeed": snapshot.get("presentationSeed") or hashlib.sha256(
               f"layout:{served['token']}".encode()).hexdigest()}
    if metadata.get("personalTier"):
        out.update(personalTier=True, originalTier=metadata["originalTier"])
    else:
        out.pop("personalTier", None)
        out.pop("originalTier", None)
    return out


def _slide_url(object_key: str, prepared_entry: dict | None = None) -> str:
    if prepared_entry is None or "resources" not in prepared_entry:
        return ObjectStorage().presign_download(object_key)
    resources = prepared_entry["resources"]
    urls = resources.setdefault("urls", {})
    if object_key not in urls:
        if "storage" not in resources:
            resources["storage"] = ObjectStorage()
        urls[object_key] = resources["storage"].presign_download(object_key)
    return urls[object_key]


def _slides(db: Session, row: QuizBank, question_id: str, presented: dict | None = None, *, references_only: bool = False,
            prepared_entry: dict | None = None) -> list[dict[str, Any]]:
    if prepared_entry is not None and "assets" not in prepared_entry:
        prepared_entry = None
    if presented and presented.get("personalAdded"):
        out = []
        for reference in presented.get("personalSlideReferences", []):
            asset = (prepared_entry["assets_by_id"].get(reference["assetId"]) if prepared_entry is not None
                     else db.get(Asset, reference["assetId"]))
            if not asset or (asset.subject, asset.run_id, asset.kind) != (row.subject, row.run_id, SLIDE_KINDS["bank"]):
                continue
            if references_only:
                out.append(dict(reference))
                continue
            try:
                out.append({**{k: v for k, v in reference.items() if k != "assetId"},
                            "primary": False, "url": _slide_url(asset.object_key, prepared_entry)})
            except StorageNotConfigured:
                break
        return out
    question = next((q for q in (row.bank or {}).get("questions", []) if q["question_id"] == question_id), {})
    report = (row.validation or {}).get("slideFocus") or {}
    current = (report.get("questions", {}).get(question_id) or {}).get("questionHash") == question_hash(question)
    pages = sorted(set((row.pages or {}).get(question_id) or []) | (all_selected_pages(report, question_id) if current else set()))
    related = {}
    if current and report.get("version") == 3:
        for ref in all_selected_references(report, question_id):
            sid, page = source_id(ref), ref["page"]
            if sid == "self":
                continue
            meta = report.get("sources", {}).get(sid) or {}
            if type(page) is not int or type(meta.get("pageCount")) is not int or not 1 <= page <= meta["pageCount"]:
                continue
            try:
                name = external_filename(row.run_id, sid, meta.get("sourceSha256", ""), page)
            except ValueError:
                continue
            related[name] = {"page": page, "sourceId": sid, "sourceRunId": meta.get("runId", sid),
                             "sourceFilename": meta.get("sourceFilename", "")}
    if not pages and not related:
        return []
    assets = ([asset for asset in prepared_entry["assets"] if asset.slide_no in pages or asset.filename in related]
              if prepared_entry is not None else list(db.scalars(select(Asset).where(
                  Asset.subject == row.subject, Asset.run_id == row.run_id, Asset.kind == SLIDE_KINDS["bank"],
                  or_(Asset.slide_no.in_(pages), Asset.filename.in_(related))))))
    own_assets = {a.slide_no: a for a in assets if a.slide_no in pages}
    foreign_assets = {a.filename: a for a in assets if a.filename in related}
    out = []
    requested = [(own_assets.get(page), {"page": page, "sourceId": "self", "sourceRunId": row.run_id,
                  "sourceFilename": report.get("sourceFilename", "")}) for page in pages]
    requested += [(foreign_assets.get(name), info) for name, info in related.items()]
    for asset, info in requested:
        if asset is None:
            continue
        if references_only:
            out.append({**info, "assetId": asset.id})
            continue
        try:
            out.append({**info, "url": _slide_url(asset.object_key, prepared_entry)})
        except StorageNotConfigured:
            break
    primary = selected_references(report, question, {(s["sourceId"], s["page"]) for s in out}, presented)
    for slide in out:
        slide["primary"] = (slide["sourceId"], slide["page"]) in primary
    return out


def _jokbo_slides(db: Session, row: QuizBank, question: dict, *, prepared_entry: dict | None = None) -> list[dict[str, Any]]:
    if prepared_entry is not None and "assets" not in prepared_entry:
        prepared_entry = None
    original = next((q for q in (row.bank or {}).get("questions", []) if q["question_id"] == question["question_id"]), {})
    refs = jokbo_references((row.validation or {}).get("jokboPages"), original, question)
    primary = exam_primary_references((row.validation or {}).get("evidenceResolution"), original, question)
    refs += primary
    if not refs:
        return []
    names = {ref["filename"] for ref in refs}
    source_assets = (prepared_entry["assets"] if prepared_entry is not None else db.scalars(select(Asset).where(
        Asset.subject == row.subject, Asset.run_id == row.run_id, Asset.kind == SLIDE_KINDS["bank"], Asset.filename.in_(names))))
    assets = {a.filename: a for a in source_assets if a.filename in names}
    core_names = {ref['filename'] for ref in primary}
    complete = bool(primary) and core_names <= set(assets)
    grouped = {}
    for ref in refs:
        name = ref["filename"]
        if name not in assets:
            continue
        if name not in grouped:
            try:
                url = _slide_url(assets[name].object_key, prepared_entry)
            except StorageNotConfigured:
                break
            grouped[name] = {"page": ref["page"], "url": url, "pdfFilename": ref["pdfFilename"], "references": [],
                             "primary": complete and name in core_names, "embedded": bool(ref.get('embedded')), "questions": []}
        labels = ref.get('references') or ([f"{ref['year']} {ref['number']}번"] if ref.get('year') and ref.get('number') else ['첨부 기출'])
        grouped[name]['embedded'] = grouped[name]['embedded'] or bool(ref.get('embedded'))
        for label in labels:
            if label not in grouped[name]["references"]:
                grouped[name]["references"].append(label)
        if isinstance(ref.get('question'), dict) and ref['question'].get('stem'):
            if ref['question'] not in grouped[name]['questions']:
                grouped[name]['questions'].append(ref['question'])
    if not core_names <= set(grouped):
        for slide in grouped.values():
            slide['primary'] = False
    return list(grouped.values())


def _answer(db: Session, row: QuizBank, q: dict, *, prepared_entry: dict | None = None) -> dict[str, Any]:
    review = next((r for r in bank_edits.current_review(row.review, row.validation)["reviews"]
                   if r["question_id"] == q["question_id"]), None)
    if review is None:
        review = bank_excluded.records(row).get(q['question_id'], {}).get('medicalReview')
    if q.get("personalAnswer"):
        review = None
    # 프롬프트 v1.2(2026-10-05): 충돌은 한 문항으로 합치고 외부 의학지식으로 답을 정한다. 학생은 답을 본 뒤
    # 각 출처가 무엇이라고 하는지와 고른 근거(충돌 기록의 설명)를 읽는다. 자료 밖 내용은 출처 `EXT` 로 표시된다.
    conflict = next((c for c in (row.bank or {}).get("source_conflicts", [])
                     if q["conflict_id"] and c["conflict_id"] == q["conflict_id"]), None)
    original = next((item for item in (row.bank or {}).get('questions', []) if item['question_id'] == q['question_id']), {})
    exam_slides = _jokbo_slides(db, row, q, prepared_entry=prepared_entry)
    evidence = evidence_status((row.validation or {}).get('evidenceResolution'), original, q,
                              focus=(row.validation or {}).get('slideFocus'))
    if evidence and evidence['category'] == 'exam_only':
        evidence['primaryAvailable'] = any(slide.get('primary') for slide in exam_slides)
    return {"answer": q["answer"], "answerUnits": q["answer_units"], "explanation": q.get("explanation", ""), "correctOptionIds": q["correct_option_ids"],
            "personalEdited": q.get("personalEdited", False), "personalAnswer": q.get("personalAnswer", False),
            "answerPairs": matching_presentation(q)["answer_pairs"], "correctOrder": q["correct_order"],
            "slides": _slides(db, row, q["question_id"], q, prepared_entry=prepared_entry), "jokboSlides": exam_slides, "evidenceStatus": evidence, "medicalReview": review,
            'reviewIssues': [issue.get('reason') or issue.get('issue', '')
                for issue in (((row.validation or {}).get('revision') or {}).get('audit') or {}).get('question_issues', [])
                if issue.get('question_id') == q['question_id'] and issue.get('severity') == 'error'
                and not q.get('personalEdited') and q['question_id'] not in (row.validation or {}).get('edits', {})],
            "conflict": conflict["description"] if conflict else "",
            "external": any(r["source_id"] == "EXT" for r in q["source_refs"])}

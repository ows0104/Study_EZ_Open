"""Authorized reference images for the exact question that was served.

Sign on read so resumed sessions do not retain expired URLs. Never substitute
the pages of a regenerated bank for an older, frozen question.
"""
from sqlalchemy import select

from app.bank_validation.pages import pages_of
from app.models import Asset, QuizBank
from app.models.lectures import SLIDE_KINDS
from app.models.learning import LearningBankVersion
from app.storage import ObjectStorage, StorageNotConfigured


def references(db, unit: dict, question: dict | None) -> dict:
    row = db.get(QuizBank, (unit["subject"], unit["runId"]))
    version = db.get(LearningBankVersion, unit["version"])
    empty = {"slides": [], "missingSlidePages": [], "sourceDocument": None}
    if not row or not row.open_to_students:
        return empty
    if not version or row.build_id != version.build_id:
        return {**empty, "slideStatus": "자료가 교체되어 이전 문항의 슬라이드를 표시할 수 없습니다."}
    refs = (question or unit["objective"])["source_refs"]
    pages = sorted({p for r in refs if r["source_id"] == "S1" for p in pages_of(r["locator"])})
    if not pages and question:
        pages = sorted(set((row.pages or {}).get(question["question_id"], [])))
    assets = {a.slide_no: a for a in db.scalars(select(Asset).where(
        Asset.subject == unit["subject"], Asset.run_id == unit["runId"],
        Asset.kind == SLIDE_KINDS["bank"], Asset.slide_no.in_(pages)))} if pages else {}
    document = db.scalars(select(Asset).where(Asset.subject == unit["subject"], Asset.run_id == unit["runId"],
                                            Asset.kind == "notes_current")).first()
    out = {**empty, "missingSlidePages": [p for p in pages if p not in assets]}
    if not assets and not document:
        return out
    try:
        storage = ObjectStorage()
        out["slides"] = [{"page": p, "url": storage.presign_download(assets[p].object_key)} for p in pages if p in assets]
        if document:
            out["sourceDocument"] = {"filename": document.filename, "url": storage.presign_download(
                document.object_key, filename=document.filename, inline=True, content_type=document.content_type)}
    except StorageNotConfigured:
        out["missingSlidePages"] = pages
    return out

"""Export the current Quiz Bank as an offline Anki deck, cached by its contents."""

from __future__ import annotations

import hashlib
import html
import itertools
import json
import random
import re
import sqlite3
import tempfile
import time
import zipfile
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

import genanki
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Asset, Lecture, QuizBank
from app.bank_edits import current_review
from app.routes.common import storage_or_503

EXPORT_VERSION = 2
MODEL_ID = 1867040701
CSS = """
.card { font-family: Arial, sans-serif; font-size: 20px; line-height: 1.65;
  text-align: left; max-width: 860px; margin: auto; padding: 20px; }
.meta, .sources { font-size: 14px; color: #777; margin: 16px 0; }
.answer { margin: 20px 0; } .blank { font-weight: bold; }
.review { border-left: 3px solid #c87e20; padding: 10px; margin: 16px 0; }
img { max-width: 100%; height: auto; } li { margin: 6px 0; }
"""


def text(value: str) -> str:
    """Source strings are text, never executable HTML or Anki templates."""
    return html.escape(value).replace("\x1f", " ").replace("\x00", "").replace("\n", "<br>")


def listing(items: list[str]) -> str:
    return "<ul>" + "".join(f"<li>{text(item)}</li>" for item in items) + "</ul>" if items else ""


def bare(item: str) -> str:
    return re.sub(r"^[LR]\d+\s*[:.)]\s*", "", item)


def mixed(items: list[str], seed: str) -> list[str]:
    out = list(items)
    random.Random(seed).shuffle(out)
    if len(out) > 1 and out == items:
        out = out[1:] + out[:1]
    return out


def render_question(q: dict, *, answered: bool = False) -> str:
    stem = q["question"]
    if q["format"] == "cloze":
        units = iter(q["answer_units"])
        index = 0

        def blank(_match: re.Match) -> str:
            nonlocal index
            index += 1
            return text(next(units)) if answered else f"[ {index} ]"

        # Escape before substituting so answer strings cannot inject markup.
        stem_html = re.sub(r"\{\{c\d+\}\}", blank, text(stem))
    else:
        stem_html = text(stem)
    out = f'<div class="question">{stem_html}</div>'
    out += listing([f'{o["id"]}. {o["text"]}' for o in q.get("options", [])])
    if q["format"] == "matching":
        out += listing([f"{i + 1}. {bare(item)}" for i, item in enumerate(q["matching_left"])])
        right = mixed(q["matching_right"], q["question_id"])
        out += listing([f"{chr(65 + i)}. {bare(item)}" for i, item in enumerate(right)])
    if q["format"] == "sequence":
        out += listing(mixed(q["sequence_items"], q["question_id"]))
    if q["format"] == "ox":
        out += "<p>O인가 X인가, 그리고 왜인가?</p>"
    return out


def render_answer(q: dict, bank: dict, review: dict, images: list[tuple[int, str]]) -> str:
    out = '<div class="answer">'
    if q["format"] == "cloze":
        out += render_question(q, answered=True)
    if q.get("answer"):
        out += f'<p>{text(q["answer"])}</p>'
    if q.get("correct_option_ids"):
        correct = set(q["correct_option_ids"])
        out += "<b>정답 보기</b>" + listing([f'{o["id"]}. {o["text"]}' for o in q["options"] if o["id"] in correct])
    if q.get("answer_pairs"):
        right = mixed(q["matching_right"], q["question_id"])
        out += listing([f'{bare(p["left"])} → {chr(65 + right.index(p["right"]))}. {bare(p["right"])}'
                        for p in q["answer_pairs"]])
    if q.get("correct_order"):
        out += f'<p>{text(" → ".join(q["correct_order"]))}</p>'
    if len(q.get("answer_units", [])) > 1 and q["format"] not in {"cloze", "matching", "sequence"}:
        out += listing(q["answer_units"])
    conflict = next((c for c in bank.get("source_conflicts", []) if q.get("conflict_id") == c["conflict_id"]), None)
    if conflict:
        out += f'<p><b>자료 충돌</b> {text(conflict["description"])}</p>'
    if any(ref["source_id"] == "EXT" for ref in q.get("source_refs", [])):
        out += "<p>외부 의학지식이 포함된 문항입니다.</p>"
    item_review = next((r for r in review.get("reviews", []) if r["question_id"] == q["question_id"]), None)
    if item_review and item_review["verdict"] != "ok":
        verdict = "틀림" if item_review["verdict"] == "wrong" else "의심"
        out += f'<div class="review"><b>외부지식 검토 · {verdict}</b><br>{text(item_review.get("note", ""))}'
        if item_review.get("suggested_answer"):
            out += f'<br>검토에서 제안한 답: {text(item_review["suggested_answer"])}'
        out += "</div>"
    refs = [f'{r["source_id"]} · {r["locator"]}' for r in q.get("source_refs", [])]
    out += f'<div class="sources">{text(" / ".join(refs))}</div>'
    for page, filename in images:
        out += f'<p>필기 {page}쪽</p><img src="{html.escape(filename, quote=True)}">'
    return out + "</div>"


def stable_id(seed: str) -> int:
    return 1_000_000_000 + int(hashlib.sha256(seed.encode()).hexdigest()[:8], 16) % 1_000_000_000


@dataclass
class Export:
    revision: str
    filename: str
    key: str
    assets: dict[int, Asset]

    @property
    def grab_kind(self) -> str:
        return f"bank_{self.revision}"


def page_map(row: QuizBank) -> dict[str, list[int]]:
    return {q["question_id"]: list(dict.fromkeys((row.pages or {}).get(q["question_id"], [])))
            for q in (row.bank or {}).get("questions", []) if q.get("role") != "exam"}


def describe(db: Session, lecture: Lecture, row: QuizBank, *, media_assets: list[Asset] | None = None) -> Export:
    pages = {p for values in page_map(row).values() for p in values}
    if media_assets is None:
        media_assets = list(db.scalars(select(Asset).where(
            Asset.subject == row.subject, Asset.run_id == row.run_id, Asset.kind == "bank_media",
            Asset.slide_no.in_(pages)).order_by(Asset.uploaded_at, Asset.id)))
    assets = {a.slide_no: a for a in media_assets if a.slide_no in pages}
    signature = json.dumps({
        "version": EXPORT_VERSION, "bank": row.bank, "review": row.review, "pages": page_map(row),
        "build": row.build_id, "title": lecture.title, "professors": lecture.professors,
        "assets": [(p, a.object_key, a.size_bytes, str(a.uploaded_at)) for p, a in sorted(assets.items())],
    }, ensure_ascii=False, sort_keys=True)
    revision = hashlib.sha256(signature.encode()).hexdigest()[:16]
    title = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", lecture.title).strip()[:100] or "Main-Quiz"
    return Export(revision, f"{lecture.run_id} {title} QuizBank.apkg",
                  f"lectures/{lecture.subject}/{lecture.run_id}/bank_anki/{revision}.apkg", assets)


def ensure_export(db: Session, lecture: Lecture, row: QuizBank) -> Export:
    export = describe(db, lecture, row)
    storage = storage_or_503()
    if storage.head(export.key) is not None:
        return export
    bank = row.bank or {}
    if not bank.get("questions"):
        raise HTTPException(409, "Anki로 받을 문항이 없습니다.")
    with tempfile.TemporaryDirectory(prefix="studyez-anki-") as directory:
        root = Path(directory)
        media: dict[int, str] = {}
        mapped_pages = page_map(row)
        pages = {p for values in mapped_pages.values() for p in values}
        for page in sorted(pages):
            asset = export.assets.get(page)
            opened = storage.open_stream(asset.object_key) if asset else None
            if opened is None:
                raise HTTPException(409, f"필기 {page}쪽 이미지가 아직 없습니다. 자료 업로드 후 다시 받아 주세요.")
            # Distinct files for distinct revisions; local media stays valid offline.
            name = f"bank_{stable_id(lecture.subject + '/' + lecture.run_id)}_{export.revision}_s{page:03}.png"
            with (root / name).open("wb") as handle:
                for chunk in opened[0]:
                    handle.write(chunk)
            media[page] = name
        model = genanki.Model(MODEL_ID, "Study_EZ QuizBank v1", fields=[{"name": name} for name in ("Question", "Answer", "Meta")],
                              templates=[{"name": "QuizBank", "qfmt": "{{Question}}",
                                          "afmt": '{{FrontSide}}<hr id="answer">{{Answer}}<div class="meta">{{Meta}}</div>'}], css=CSS)
        subject = lecture.subject.replace("::", "：").replace("\n", " ")
        title = lecture.title.replace("::", "：").replace("\n", " ")
        deck_name = f"{subject}::{lecture.run_id} {title} QuizBank"
        deck = genanki.Deck(stable_id(f"bank/{lecture.subject}/{lecture.run_id}"), deck_name)
        for index, q in enumerate(bank["questions"]):
            if q.get("role") == "exam":
                continue  # Reserved assessment items must stay unexposed.
            # Q1 can name an entirely different question after regeneration. Content is
            # part of the identity; answer-only corrections retain the original GUID.
            identity = json.dumps({k: q.get(k) for k in ("question", "format", "options", "matching_left", "matching_right", "sequence_items")},
                                  ensure_ascii=False, sort_keys=True)
            guid = genanki.guid_for("studyez-bank", lecture.subject, lecture.run_id, q["question_id"], identity)
            images = [(p, media[p]) for p in mapped_pages.get(q["question_id"], [])]
            fields = [render_question(q), render_answer(q, bank, current_review(row.review, row.validation), images),
                      text(f'{lecture.title} · {q["question_id"]} · {q["concept_id"]} · {q["tier"]} · {q["retrieval_direction"]}')]
            tags = ["Study_EZ::QuizBank", f'형식::{q["format"]}', f'등급::{q["tier"]}']
            deck.add_note(genanki.Note(model=model, fields=fields, tags=tags, guid=guid, due=index + 1))
        # Write the SQLite file ourselves: genanki's write_to_file leaves a temporary
        # database behind. Both database and media here belong to this scoped directory.
        database = root / "collection.anki2"
        with closing(sqlite3.connect(database)) as connection:
            with connection:
                timestamp = time.time()
                genanki.Package(deck).write_to_db(connection.cursor(), timestamp, itertools.count(int(timestamp * 1000)))
        path = root / "deck.apkg"
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as package:
            package.write(database, "collection.anki2")
            names = list(media.values())
            package.writestr("media", json.dumps(dict(enumerate(names))))
            for index, name in enumerate(names):
                package.write(root / name, str(index))
        with path.open("rb") as handle:
            storage.upload_fileobj(handle, export.key, content_type="application/octet-stream")
    return export

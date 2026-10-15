"""Reviewed PDF page references for preview-based web quizzes.

The generator's original cards remain intact. A lecture-owned manifest records
the source PDF and question content so a later export cannot silently reuse a
reference for a different question or PDF.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path

MANIFEST = "pre_source_slides.json"


def pdf_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def item_hash(item: dict) -> str:
    support = item.get("learning_support") or {}
    content = [item.get("stem"), item.get("answer"), support.get("preview_excerpt")]
    return hashlib.sha256(json.dumps(content, ensure_ascii=False).encode("utf-8")).hexdigest()


def attach(run_dir: Path, items: list[dict], pdf: Path | None) -> list[dict]:
    path = run_dir / MANIFEST
    if not path.is_file():
        return items
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("version") != 1:
        raise ValueError(f"{path}: unsupported source reference version")
    if pdf is None or not pdf.is_file() or pdf_hash(pdf) != manifest["pdf_sha256"]:
        raise ValueError(f"{path}: source PDF changed; review references again")
    references = manifest["items"]
    result = []
    for item in items:
        reference = references.get(item["id"])
        if reference and item.get("slide_no") is None:
            if item_hash(item) != reference["content_sha256"]:
                raise ValueError(f"{path}: {item['id']} changed; review its source reference again")
            number = reference["slide_no"]
            if type(number) is not int or number < 1:
                raise ValueError(f"{path}: invalid page for {item['id']}")
            item = {**item, "slide_no": number}
        result.append(item)
    return result


def render(run_dir: Path, run_id: str, items: list[dict], pdf: Path) -> int:
    """Render required pages, replacing each file atomically for publishers.

    Called only for lectures with an approved manifest. Existing export media
    can be incomplete when the cards were generated from a preview text.
    """
    import fitz

    numbers = sorted({i["slide_no"] for i in items if type(i.get("slide_no")) is int})
    target = run_dir / "slides"
    with fitz.open(pdf) as document:
        if any(number < 1 or number > len(document) for number in numbers):
            raise ValueError(f"{run_id}: source page outside PDF")
        target.mkdir(exist_ok=True)
        for number in numbers:
            image = document[number - 1].get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
            handle, name = tempfile.mkstemp(prefix=".source-", suffix=".png", dir=target)
            os.close(handle)
            temporary = Path(name)
            try:
                image.save(temporary)
                os.replace(temporary, target / f"{run_id}_s{number:03d}.png")
            finally:
                temporary.unlink(missing_ok=True)
    return len(list(target.glob(f"{run_id}_s*.png")))

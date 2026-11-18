"""Pages an operator withheld from one run's model input (page-withhold/1, docs/changes/2026-11-18-root-exclude-pages).

The runner freezes the operator's record (runs/page-exclusions.json, runner.page_exclusions) as a sidecar next to
the run's downloaded copy of a source: `<source file>.withheld-pages.json`. Every place that turns that copy into
what a model reads opens it through `document(path)`: the withheld pages are replaced by blank pages of the same
size that carry only NOTICE. Page count and page numbers stay those of the original, so a citation, an image page,
the page review of the audit and the published crops all keep the original's numbering. The original file, its
SHA-256 and the server's packet are not changed; a source without a sidecar opens exactly as before.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import fitz

POLICY = 'page-withhold/1'
SUFFIX = '.withheld-pages.json'
NOTICE = ('[Page {page} withheld by the operator: it is not material for this run. '
          'Nothing was shown here; do not cite this page or use it for any question.]')


def sidecar(path: Path) -> Path:
    path = Path(path)
    return path.with_name(path.name + SUFFIX)


def pages(path: Path) -> frozenset[int]:
    """The withheld page numbers (1-based) of this local source copy; empty without a sidecar.

    A sidecar written for other bytes stops the caller: the copy changed after the operator's record was frozen."""
    target = sidecar(path)
    if not target.is_file():
        return frozenset()
    record = json.loads(target.read_text(encoding='utf-8-sig'))
    if record.get('policy') != POLICY:
        raise ValueError(f'{target.name}: policy is not {POLICY}')
    if record.get('sourceSha256') != hashlib.sha256(Path(path).read_bytes()).hexdigest():
        raise ValueError(f'{target.name}: written for other bytes than {Path(path).name}')
    found = record.get('pages')
    if not isinstance(found, list) or not found or not all(isinstance(p, int) and not isinstance(p, bool) and p >= 1 for p in found):
        raise ValueError(f'{target.name}: pages must be a non-empty list of page numbers')
    return frozenset(found)


def mask(doc: fitz.Document, withheld) -> fitz.Document:
    """Replace each withheld page of `doc` in place by a blank page of the same size carrying NOTICE."""
    withheld = set(withheld)
    if not withheld:
        return doc
    if max(withheld) > doc.page_count:
        raise ValueError(f'withheld page {max(withheld)} is outside the {doc.page_count}-page source')
    toc = doc.get_toc(simple=False)
    for number in sorted(withheld):
        rect = doc[number - 1].rect
        doc.delete_page(number - 1)
        page = doc.new_page(number - 1, width=rect.width, height=rect.height)
        page.insert_textbox(fitz.Rect(36, 36, rect.width - 36, rect.height - 36), NOTICE.format(page=number), fontsize=11)
    # Bookmark titles are text of the source too: keep only those that point at shown pages.
    doc.set_toc([entry[:3] for entry in toc if entry[2] not in withheld])
    doc.set_metadata({})
    return doc


def document(path: Path) -> fitz.Document:
    """The source as a model may read it: the original, or the original with its withheld pages blanked."""
    doc = fitz.open(path)
    try:
        return mask(doc, pages(path))
    except BaseException:
        doc.close()
        raise


def save_model_copy(path: Path, target: Path) -> frozenset[int]:
    """Write what `document(path)` shows to `target` (a PDF a model may open). Returns the withheld pages."""
    withheld = pages(path)
    with document(path) as doc:
        doc.save(target, garbage=4, deflate=True)
    return withheld

"""Same-course lecture catalog and content-addressed source images, never exam books."""
from __future__ import annotations
import hashlib
import json
import os
import re
from pathlib import Path
import fitz

from studyez_contracts.bank.slide_focus import all_selected_references, external_filename, source_id


def discover(pdf: Path) -> dict[str, Path]:
    """The runner's attached current notes live together in one course/year directory."""
    match = re.match(r"\[(\d{6}_\d{2})\]", pdf.name)
    if not match:
        return {}
    own = match[1]
    candidates = {}
    for path in pdf.parent.rglob("*.pdf"):
        found = re.match(r"\[(\d{6}_\d{2})\]", path.name)
        if not found or found[1] == own or found[1][:2] != own[:2]:
            continue
        version = re.search(r"v(\d+(?:\.\d+)?)\s*\.pdf$", path.name, re.I)
        score = (tuple(map(int, version[1].split('.'))) if version else (0,), path.stat().st_mtime_ns, path.name)
        if found[1] not in candidates or score > candidates[found[1]][0]:
            candidates[found[1]] = (score, path)
    return {key: value[1] for key, value in sorted(candidates.items())}


def describe(pdf: Path, run_id: str = "") -> dict:
    with fitz.open(pdf) as doc:
        count = doc.page_count
    return {"runId": run_id, "sourceFilename": pdf.name,
            "sourceSha256": hashlib.sha256(pdf.read_bytes()).hexdigest(), "pageCount": count}


def prepare(pdf: Path, out: Path) -> dict:
    """Atomic cache writes allow parallel bank workers to share these original renders."""
    out.mkdir(parents=True, exist_ok=True)
    images = out / "source-pages"
    images.mkdir(exist_ok=True)
    digest = hashlib.sha256(pdf.read_bytes()).hexdigest()
    stamp = out / "source-sha256.txt"
    fresh = stamp.is_file() and stamp.read_text(encoding="utf-8") == digest
    with fitz.open(pdf) as doc:
        text = out / "source-text.md"
        if not fresh or not text.is_file():
            temp = out / f"text-{os.getpid()}.tmp"
            temp.write_text("\n\n".join(f"## PDF p.{i + 1}\n{page.get_text()}" for i, page in enumerate(doc)), encoding="utf-8")
            temp.replace(text)
        paths = []
        for i, page in enumerate(doc):
            image = images / f"page-{i + 1:04d}.png"
            if not fresh or not image.is_file():
                temp = images / f"page-{i + 1:04d}-{os.getpid()}.png"
                page.get_pixmap(matrix=fitz.Matrix(1.2, 1.2), alpha=False).save(temp)
                temp.replace(image)
            paths.append(str(image.resolve()))
    temp = out / f"sha-{os.getpid()}.tmp"
    temp.write_text(digest, encoding="utf-8")
    temp.replace(stamp)
    return {"pdf": str(pdf.resolve()), "text": str(text.resolve()), "images": paths}


def render_selected(report: dict, paths: dict[str, Path], out: Path, run_id: str) -> list[Path]:
    """Copy only verified related pages into this bank's own authenticated asset scope."""
    out.mkdir(parents=True, exist_ok=True)
    grouped = {}
    for qid in report.get("questions", {}):
        for slide in all_selected_references(report, qid):
            sid = source_id(slide)
            if sid != "self":
                grouped.setdefault(sid, set()).add(slide["page"])
    made = []
    for sid, pages in grouped.items():
        meta = report["sources"][sid]
        pdf = paths[sid]
        if hashlib.sha256(pdf.read_bytes()).hexdigest() != meta["sourceSha256"]:
            raise ValueError(f"Evidence PDF changed: {sid}")
        with fitz.open(pdf) as doc:
            for page in sorted(pages):
                if not 1 <= page <= doc.page_count:
                    raise ValueError(f"Invalid evidence PDF page: {sid}/{page}")
                image = out / external_filename(run_id, sid, meta["sourceSha256"], page)
                if not image.is_file():
                    doc[page - 1].get_pixmap(matrix=fitz.Matrix(1.6, 1.6), alpha=False).save(image)
                made.append(image)
    return made

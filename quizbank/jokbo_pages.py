"""기존 족보 절단기의 연도·문항 번호·원본 PDF 지면 정보를 연결한다."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path

import fitz

from studyez_contracts.bank.slide_focus import question_hash

YEAR = re.compile(r"(?<!\d)((?:19|20)\d{2})(?:\s*[-–]\s*([12])(?!\d))?")
NUMBER = re.compile(r"(?<![\w.])(?:Q\s*)?(R?\s*\d{1,3})(?:\s*[–~\-]\s*(R?\s*\d{1,3}))?", re.I)


def references(locator: str) -> list[tuple[str, str]]:
    years = list(YEAR.finditer(locator))
    found = []
    for i, match in enumerate(years):
        year = match[1] + ("-" + match[2] if match[2] else "")
        tail = locator[match.end():years[i + 1].start() if i + 1 < len(years) else len(locator)]
        tail = re.sub(r"^\s*년", "", tail)
        for number in NUMBER.finditer(tail):
            start = re.sub(r"\s", "", number[1]).upper()
            end = re.sub(r"\s", "", number[2]).upper() if number[2] else start
            prefix = "R" if start.startswith("R") else ""
            a, b = int(start.lstrip("R")), int(end.lstrip("R"))
            if a <= b and b - a <= 10:
                found.extend((year, prefix + str(n)) for n in range(a, b + 1))
    return list(dict.fromkeys(found))


def connect(bank: dict, jokbo: Path | None, out: Path, run_id: str) -> tuple[dict, list[Path]]:
    out.mkdir(parents=True, exist_ok=True)
    index = next((p / "index.json" for p in [jokbo.parent, *jokbo.parents[:4]]
                  if (p / "index.json").is_file()), None) if jokbo else None
    sidecar = jokbo.with_suffix(".json") if jokbo else None
    catalog = json.loads(index.read_text(encoding="utf-8")) if index else {}
    source = json.loads(sidecar.read_text(encoding="utf-8")) if sidecar and sidecar.is_file() else {}
    by_key = {}
    for question in source.get("questions", []):
        key = str(question["year"]), str(question["no"]).upper()
        by_key.setdefault(key, []).append(question)
    made, documents, hashes = {}, {}, {}
    questions = {}
    try:
        for question in bank["questions"]:
            locators = dict.fromkeys(ref["locator"] for ref in question["source_refs"]
                                    if ref["source_id"] == "S2")
            for pool in question.get("option_pools", []):
                for candidate in pool["candidates"]:
                    locators.update(dict.fromkeys(ref["locator"] for ref in candidate["source_refs"] if ref["source_id"] == "S2"))
            if not locators:
                continue
            mapped, unresolved = {}, []
            for locator in locators:
                keys = references(locator)
                refs = []
                for year, no in keys:
                    candidates = by_key.get((year, no), [])
                    if not candidates and "-" not in year:
                        candidates = [q for (y, n), rows in by_key.items() if y.startswith(year + "-") and n == no for q in rows]
                    if len(candidates) != 1:
                        unresolved.append(f"{year} {no}")
                        continue
                    hit = candidates[0]
                    path = (source.get("sources", [])[hit["src"]].get("path") if hit.get("src") is not None
                            else catalog.get("source_path"))
                    if not path or not Path(path).is_file():
                        unresolved.append(f"{year} {no}")
                        continue
                    if path not in documents:
                        documents[path] = fitz.open(path)
                        hashes[path] = hashlib.sha256(Path(path).read_bytes()).hexdigest()
                    doc = documents[path]
                    for page in hit.get("pages", []):
                        if not 1 <= page <= doc.page_count:
                            unresolved.append(f"{year} {no} p.{page}")
                            continue
                        filename = f"{run_id}_jb{hashes[path][:10]}_p{page:04d}.png"
                        if filename not in made:
                            dest = out / filename
                            if not dest.is_file():
                                doc[page - 1].get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False).save(dest)
                            made[filename] = dest
                        refs.append({"year": str(hit["year"]), "number": no, "page": page, "filename": filename,
                                     "pdfFilename": Path(path).name, "sourceSha256": hashes[path],
                                     "question": {"reference": f"{hit['year']} {no}번",
                                                  "stem": hit.get("stem", ""),
                                                  "options": hit.get("options", []),
                                                  "answer": hit.get("answer"),
                                                  "objection": hit.get("objection"),
                                                  "needsFigure": bool(hit.get("needs_figure") or hit.get("figures"))}})
                if not keys:
                    unresolved.append(locator)
                mapped[locator] = refs
            questions[question["question_id"]] = {"questionHash": question_hash(question),
                "locators": mapped, "unresolved": list(dict.fromkeys(unresolved))}
    finally:
        for doc in documents.values():
            doc.close()
    report = {"version": 1, "checkedAt": datetime.now(UTC).isoformat(), "questions": questions}
    (out / "jokbo-pages.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report, list(made.values())

"""Main-Quiz(뿌리 학습) 판에 Quiz Bank와 같은 근거 보강을 만든다.

문항·판·학습 기록은 읽기만 한다. Quiz Bank의 `evidence.enrich`와 같은 함수
(`slide_focus.select` → `jokbo_pages.connect` → `exam_focus.resolve`)를 판의 `bank_snapshot`과
지문이 확인된 고정 원본 PDF에 돌려 `root-evidence/1` JSON 하나를 쓴다. 다른 강의 자료는 쓰지 않는다.

족보 번호→쪽은 공통 PDF 형식(docs/policies/jokbo-attachments.md)의 쪽 머리
`연도 | 교수 | N번`을 고정 사본에서 읽어 색인한다. 모델을 쓰지 않는다.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

import fitz

from studyez_contracts.bank.pages import pages_of
from studyez_contracts.bank.slide_focus import question_hash

SCHEMA = "root-evidence/1"
# 쪽 머리 둘째 줄: "2023 | 김지은 | 79번". 교수 칸은 비거나 여러 명일 수 있다.
HEADER = re.compile(r"^\s*((?:19|20)\d{2}(?:-[12])?)\s*\|[^|\n]*\|\s*(R?\d{1,3})\s*번", re.M)
HEAD_CHARS = 400


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def exam_index(pdf: Path) -> dict[tuple[str, str], list[int]]:
    """정리본 족보의 (연도, 번호) → 실제 쪽. 머리가 없는 쪽(공용 자료·정답표)은 빠진다."""
    index: dict[tuple[str, str], list[int]] = {}
    with fitz.open(pdf) as doc:
        for number, page in enumerate(doc, start=1):
            match = HEADER.search(page.get_text()[:HEAD_CHARS])
            if match:
                index.setdefault((match[1], match[2].upper()), []).append(number)
    return index


def _sidecar(index: dict, exam_pdf: Path, folder: Path) -> Path:
    """`jokbo_pages.connect`가 읽는 절단기 사이드카 모양으로 색인을 옮긴다(원본 PDF 경로 = 고정 사본)."""
    folder.mkdir(parents=True, exist_ok=True)
    questions = [{"year": year, "no": no, "pages": pages, "src": 0} for (year, no), pages in sorted(index.items())]
    marker = folder / "exam.md"
    marker.write_text("정리본 족보 쪽 머리 색인", encoding="utf-8")
    marker.with_suffix(".json").write_text(json.dumps(
        {"sources": [{"path": str(exam_pdf.resolve())}], "questions": questions}, ensure_ascii=False, indent=2), encoding="utf-8")
    return marker


def _direct_pages(bank: dict, report: dict, index: dict, exam_pdf: Path, digest: str, images: Path, run_id: str) -> None:
    """S2를 쪽으로 직접 인용한 것(`physical PDF page 23`)도 같은 족보 지면으로 잇는다. 번호는 쪽 머리에서."""
    labels = {page: key for key, pages in index.items() for page in pages}
    with fitz.open(exam_pdf) as doc:
        for question in bank["questions"]:
            for ref in question.get("source_refs", []):
                if ref["source_id"] != "S2":
                    continue
                pages = [p for p in pages_of(ref["locator"]) if 1 <= p <= doc.page_count]
                if not pages:
                    continue
                record = report["questions"].setdefault(question["question_id"], {
                    "questionHash": question_hash(question), "locators": {}, "unresolved": []})
                refs = record["locators"].setdefault(ref["locator"], [])
                for page in pages:
                    filename = f"{run_id}_jb{digest[:10]}_p{page:04d}.png"
                    if any(r["filename"] == filename for r in refs):
                        continue
                    image = images / filename
                    if not image.is_file():
                        doc[page - 1].get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False).save(image)
                    year, no = labels.get(page, ("", ""))
                    refs.append({"year": year, "number": no, "page": page, "filename": filename,
                                 "pdfFilename": exam_pdf.name, "sourceSha256": digest,
                                 **({"references": [f"{year} {no}번"]} if year else {"references": [f"족보 {page}쪽"]}),
                                 "question": {"reference": f"{year} {no}번" if year else f"족보 {page}쪽", "stem": "",
                                              "options": [], "answer": None, "objection": None, "needsFigure": True}})
                # 쪽으로 읽힌 인용은 번호 연결 실패가 아니다.
                record["unresolved"] = [u for u in record["unresolved"] if u != ref["locator"]]


def enrich(document: dict, sources: dict[str, Path], out: Path, run_id: str, *, model: str | None = None) -> dict:
    """`document`: root_content 문서. `sources`: source_id → 고정 사본. 지문은 문서의 review.sources로 확인한다."""
    from . import exam_focus, jokbo_pages, slide_focus

    bank = document["bank_snapshot"]
    known = {s["source_id"]: s for s in document["review"]["sources"]}
    for sid, path in sources.items():
        if sid not in known or sha256(path) != known[sid]["sha256"]:
            raise ValueError(f"{sid}: 판에 고정된 원본과 지문이 다릅니다.")
    notes = [sid for sid, s in known.items() if s.get("kind") == "notes" and sid in sources]
    exams = [sid for sid, s in known.items() if s.get("kind") == "exam" and sid in sources]
    if len(notes) != 1:
        raise ValueError("강의록(notes) 원본이 하나여야 합니다.")
    if len(exams) > 1:
        raise ValueError("족보(exam) 원본이 둘 이상인 판은 아직 다루지 않습니다.")
    notes_pdf = sources[notes[0]]
    out.mkdir(parents=True, exist_ok=True)
    images = out / "slides"
    images.mkdir(parents=True, exist_ok=True)

    focus, usage = slide_focus.select(bank, notes_pdf, out / "slide-focus", model=model)
    focus["sourceFilename"] = known[notes[0]].get("label", notes_pdf.name)
    references = {"version": 1, "questions": {}}
    indexed = 0
    if exams:
        exam_pdf = sources[exams[0]]
        index = exam_index(exam_pdf)
        indexed = sum(len(p) for p in index.values())
        references, _ = jokbo_pages.connect(bank, _sidecar(index, exam_pdf, out / "exam-index"), images, run_id)
        _direct_pages(bank, references, index, exam_pdf, known[exams[0]]["sha256"], images, run_id)
    resolution, exam_usage = exam_focus.resolve(bank, focus, references, {"self": notes_pdf}, out, run_id, model)
    evidence = {
        "schema": SCHEMA, "revision": document["revision"], "createdAt": datetime.now(UTC).isoformat(),
        "sources": {sid: known[sid]["sha256"] for sid in sources},
        "notesSource": notes[0], "examSource": exams[0] if exams else None, "examPagesIndexed": indexed,
        "slideFocus": focus, "jokboPages": references, "evidenceResolution": resolution,
    }
    (out / "evidence.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    with (out / "usage.jsonl").open("a", encoding="utf-8") as log:
        for entry in [*usage, *exam_usage]:
            log.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return evidence


def summary(evidence: dict) -> str:
    focus = evidence["slideFocus"].get("questions", {})
    modes = {m: sum((q.get("base") or {}).get("mode") == m for q in focus.values()) for m in ("single", "linked", "unresolved")}
    linked = sum(1 for q in evidence["jokboPages"]["questions"].values() if any(q["locators"].values()))
    cores = sum(1 for q in evidence["evidenceResolution"]["questions"].values() if (q.get("base") or {}).get("examCore"))
    return (f"핵심 근거 {modes} · 족보 연결 {linked}문항(색인 {evidence['examPagesIndexed']}쪽) · 족보 핵심 {cores}문항")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--document", type=Path, required=True, help="root_content 문서 JSON")
    ap.add_argument("--source", action="append", default=[], help="S1=경로 (판의 review.sources와 지문 대조)")
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--model")
    args = ap.parse_args(argv)
    sources = {}
    for item in args.source:
        sid, _, path = item.partition("=")
        sources[sid] = Path(path)
    document = json.loads(args.document.read_text(encoding="utf-8"))
    evidence = enrich(document, sources, args.out, args.run_id, model=args.model)
    print(summary(evidence), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

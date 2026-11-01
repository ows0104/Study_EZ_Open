"""One-off approved material preparation. Never writes to a source PDF."""
from pathlib import Path
import dataclasses
import hashlib
import json
import re
import sys
import unicodedata

import pymupdf as fitz

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from runner import ahead

HERE = Path(__file__).resolve().parent
OUT = ROOT / "runs/_materials/감염과 면역/261101-notes-appendices"
INV = json.loads((HERE / "inventory.json").read_text(encoding="utf-8"))
NOTES = {s["key"]: s for s in INV["notes"]}

# Inclusive, 1-based page ranges read from the actual source documents.
# Multi-part source documents have more than one appendix range.
RANGES = {
    "251103_02": [[47, 49]], "251103_03": [[62, 64]],
    "251103_05": [[47, 48]], "251103_06": [[36, 38], [60, 63]],
    "251103_07": [[60, 64]], "251105_01": [[28, 29]],
    "251105_02": [[43, 45]], "251105_03": [[55, 59]],
    "251105_05": [[65, 68]], "251106_01": [[30, 36]],
    "251106_02": [[22, 23]], "251106_03": [[30, 31]],
    "251106_05": [[73, 75]], "251106_06": [[41, 44]],
    "251106_07": [[28, 29], [57, 58]], "251107_03": [[44, 46]],
    "251107_05": [[37, 38]], "251107_06": [[26, 29]],
    "251110_01": [[22, 22]], "251110_02": [[24, 26]],
    "251110_03": [[27, 28]], "251110_05": [[105, 111]],
    "251111_01": [[38, 41]], "251111_02": [[35, 40]],
    "251111_03": [[35, 38]], "251112_01": [[33, 35]],
    "251112_02": [[51, 54]], "251113_01": [[30, 32]],
    "251113_02": [[34, 34]], "251113_03": [[36, 37]],
    "251114_01": [[34, 36]], "251114_03": [[46, 48]],
    "251117_01": [[53, 54]], "251117_02": [[43, 43]],
    "251117_03": [[33, 37]], "251117_05": [[38, 41]],
    "251117_06": [[44, 47]], "251118_01": [[61, 64]],
    "251118_02": [[27, 29]], "251118_03": [[42, 43]],
    "251119_01": [[48, 50]], "251119_02": [[36, 37]],
    "251119_04": [[60, 61]], "251120_01": [[31, 33]],
    "251120_02": [[23, 25]], "251120_03": [[44, 48]],
    "251120_05": [[43, 47]], "251120_06": [[48, 50]],
    "251124_01": [[24, 25]], "251124_02": [[40, 42]],
    "251124_03": [[59, 61]], "251124_05": [[35, 46]],
    "251124_06": [[48, 51]], "251124_07": [[41, 48]],
    "251125_01": [[41, 45]], "251125_02": [[30, 41]],
    "251125_03": [[47, 53]], "251126_01": [[65, 69]],
    "251126_02": [[41, 43]], "251126_03": [[41, 45]],
    "251126_05": [[46, 48]], "251126_06": [[45, 49]],
    "251127_01": [[79, 83]], "251127_02": [[70, 74]],
    "251127_03": [[42, 46]], "251127_05": [[32, 34]],
}
assert len(RANGES) == 66


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_pdf(target, parts):
    document = fitz.open()
    page_sources = []
    for key, ranges in parts:
        source = fitz.open(NOTES[key]["path"])
        for start, end in ranges:
            assert 1 <= start <= end <= len(source)
            before = len(document)
            document.insert_pdf(source, from_page=start - 1, to_page=end - 1)
            # insert_pdf does not retain a page-level transparency Group.
            # These source dictionaries contain only direct color-space values.
            for offset, original_index in enumerate(range(start - 1, end)):
                group_type, group = source.xref_get_key(source[original_index].xref, "Group")
                if group_type != "null":
                    assert group_type == "dict" and not re.search(r"\d+\s+\d+\s+R\b", group)
                    document.xref_set_key(document[before + offset].xref, "Group", group)
            page_sources.extend({"source_key": key, "source_page": page} for page in range(start, end + 1))
        source.close()
    document.save(target, garbage=4, deflate=True)
    document.close()
    return {"path": str(target), "sha256": sha(target), "page_count": len(page_sources), "page_sources": page_sources}


def main():
    if (HERE / "upload-plan.json").exists():
        raise SystemExit("A plan already exists: verify/reuse it instead of regenerating.")
    OUT.mkdir(parents=True, exist_ok=False)
    files = []
    appendix = {}
    for key, ranges in RANGES.items():
        target = OUT / f"{key}-족보.pdf"
        record = make_pdf(target, [(key, ranges)])
        record.update(kind="jokbo", source_keys=[key], source_ranges=ranges)
        files.append(record)
        appendix[key] = record
    clinical = ["251103_06", "251103_07"]
    merged_notes = make_pdf(OUT / "2025-위장관-피부연조직-요로-폐렴-필기합본.pdf", [
        (key, [[1, NOTES[key]["page_count"]]]) for key in clinical
    ])
    merged_notes.update(kind="notes_prev", source_keys=clinical)
    files.append(merged_notes)
    merged_exam = make_pdf(OUT / "2025-위장관-피부연조직-요로-폐렴-족보합본.pdf", [(key, RANGES[key]) for key in clinical])
    merged_exam.update(kind="jokbo", source_keys=clinical)
    files.append(merged_exam)
    cells = {c.key: c for c in ahead.read_cells(Path(INV["timetable"]))}
    plans = []
    for row in INV["mapping_draft"]:
        keys = row["previous_keys"]
        if not keys:
            continue
        cell = cells[row["run_id"]]
        item = dataclasses.replace(cell.as_lecture(), title=" ".join(cell.body))
        uploads = []
        if len(keys) == 2:
            assert keys == clinical
            uploads = [{"kind": "notes_prev", "path": merged_notes["path"]}, {"kind": "jokbo", "path": merged_exam["path"]}]
        else:
            key = keys[0]
            uploads.append({"kind": "notes_prev", "path": NOTES[key]["path"]})
            if key in appendix:
                uploads.append({"kind": "jokbo", "path": appendix[key]["path"]})
        plans.append({"subject": INV["subject"], "run_id": cell.key, "previous_keys": keys,
                      "lecture_payload": {"subject": INV["subject"], "runId": cell.key, "uid": item.uid,
                                          "date": cell.date, "slot": cell.slot, "slotEnd": cell.slot,
                                          "startTime": cell.start_time, "title": item.title,
                                          "professors": list(cell.professors), "author": "", "version": None},
                      "uploads": uploads})
    result = {"subject": INV["subject"], "source": "2025 notes, original appendix pages preserved",
              "files": files, "lectures": plans,
              "not_linked": [r for r in INV["mapping_draft"] if not r["previous_keys"]]}
    (HERE / "upload-plan.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"derived_pdfs": len(files), "lectures": len(plans),
                      "notes_prev": sum(u["kind"] == "notes_prev" for p in plans for u in p["uploads"]),
                      "jokbo": sum(u["kind"] == "jokbo" for p in plans for u in p["uploads"]),
                      "without_dedicated_previous_note": len(result["not_linked"])}, ensure_ascii=False))


if __name__ == "__main__":
    main()

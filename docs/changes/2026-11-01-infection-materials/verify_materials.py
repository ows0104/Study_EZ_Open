"""Read-only content and page preservation checks for this material operation."""
import hashlib
import json
from pathlib import Path
import pymupdf as fitz

folder = Path(__file__).resolve().parent
inventory = json.loads((folder / "inventory.json").read_text(encoding="utf-8"))
assert len(inventory["notes"]) == 70
assert len(inventory["jokbo"]) == 2
assert len(inventory["mapping_draft"]) == 81
assert len({n["key"] for n in inventory["notes"]}) == 70
assert {k for r in inventory["mapping_draft"] for k in r["previous_keys"]} == {
    n["key"] for n in inventory["notes"]
}
timetable = Path(inventory["timetable"])
assert hashlib.sha256(timetable.read_bytes()).hexdigest() == inventory["timetable_sha256"]
source_paths = {}
for source in inventory["notes"] + inventory["jokbo"]:
    path = Path(source["path"])
    stat = path.stat()
    assert stat.st_size == source["size_bytes"], path
    data = path.read_bytes()
    assert hashlib.sha256(data).hexdigest() == source["sha256"], path
    with fitz.open(stream=data, filetype="pdf") as doc:
        assert len(doc) == source["page_count"] > 0
    if source.get("key"):
        source_paths[source["key"]] = path
plan_path = folder / "upload-plan.json"
plan = json.loads(plan_path.read_text(encoding="utf-8"))
assert len(plan["files"]) == 68
assert len(plan["lectures"]) == 71
assert len(plan["not_linked"]) == 10
expected = {**{str(p): s["sha256"] for s in inventory["notes"] for p in [Path(s["path"])]},
            **{f["path"]: f["sha256"] for f in plan["files"]}}
rendered = 0
cache = {}
for artifact in plan["files"]:
    path = Path(artifact["path"])
    assert hashlib.sha256(path.read_bytes()).hexdigest() == artifact["sha256"]
    with fitz.open(path) as doc:
        assert len(doc) == artifact["page_count"] == len(artifact["page_sources"])
        for i, ref in enumerate(artifact["page_sources"]):
            key = ref["source_key"]
            if key not in cache:
                cache[key] = fitz.open(source_paths[key])
            original = cache[key][ref["source_page"] - 1]
            copied = doc[i]
            assert original.rect == copied.rect, (path, i)
            # Font deduplication exposes two Wingdings private-use glyphs as
            # their Unicode equivalents. Their rendered pixels must still match.
            glyphs = {0xF0FC: 0x2713, 0xF0E0: 0x2192}
            assert original.get_text().translate(glyphs) == copied.get_text().translate(glyphs), (path, i, "text")
            a = original.get_pixmap(matrix=fitz.Matrix(.3, .3), alpha=False)
            b = copied.get_pixmap(matrix=fitz.Matrix(.3, .3), alpha=False)
            assert a.width == b.width and a.height == b.height and a.samples == b.samples, (path, i, "render")
            rendered += 1
for doc in cache.values():
    doc.close()
counts = {"notes_prev": 0, "jokbo": 0}
for lecture in plan["lectures"]:
    assert lecture["subject"] == inventory["subject"]
    assert lecture["lecture_payload"]["runId"] == lecture["run_id"]
    assert lecture["lecture_payload"]["version"] is None
    assert len({u["kind"] for u in lecture["uploads"]}) == len(lecture["uploads"])
    for upload in lecture["uploads"]:
        assert upload["kind"] in counts
        counts[upload["kind"]] += 1
        assert upload["path"] in expected
assert counts == {"notes_prev": 71, "jokbo": 67}
result = {"status": "passed", "source_pdfs": 72, "source_pages": sum(s["page_count"] for s in inventory["notes"] + inventory["jokbo"]),
          "derived_pdfs": 68, "original_pages_compared": rendered, "uploads": counts,
          "plan_sha256": hashlib.sha256(plan_path.read_bytes()).hexdigest(),
          "visual_review": "Four first/last-page contact sheets inspected; original question images and annotations preserved."}
(folder / "materials-verification.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result, ensure_ascii=False))

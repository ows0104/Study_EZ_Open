"""Verify fixed source identity, extraction regions, preserved pages and mapping."""
from pathlib import Path
import hashlib
import json
import re
import pymupdf as fitz

HERE=Path(__file__).resolve().parent
plan_path=HERE/"upload-plan.json"
plan=json.loads(plan_path.read_text(encoding="utf-8"))
source_path=Path(plan["source"]["path"])
assert hashlib.sha256(source_path.read_bytes()).hexdigest()==plan["source"]["sha256"]
source=fitz.open(source_path)
assert len(source)==183
assert len(plan["files"])==69 and len(plan["lectures"])==80
assert len({p["run_id"] for p in plan["lectures"]})==80
assert len({p["section"] for p in plan["lectures"]})==69
assert {r["run_id"] for r in plan["not_applicable"]}=={"261119_07"}

glyphs={0xF0FC:0x2713,0xF0E0:0x2192}
def text_norm(value):
    return re.sub(r"\s+","",value.translate(glyphs))

cache={}
checked=0
max_mean_difference=0.0
for key,artifact in plan["files"].items():
    path=Path(artifact["path"])
    assert hashlib.sha256(path.read_bytes()).hexdigest()==artifact["sha256"]
    doc=fitz.open(path)
    assert len(doc)==len(artifact["page_sources"])==artifact["page_count"]
    assert "2026" in doc[0].get_text()
    assert {"문제","정답"}<={row[1] for row in doc.get_toc()}
    parts={}
    for i,ref in enumerate(artifact["page_sources"]):
        if "generated" in ref:
            assert i==0
            continue
        pno=ref["source_page"]
        rect=fitz.Rect(ref["clip"]) if ref["clip"] else None
        ck=(pno,tuple(rect) if rect is not None else None)
        if ck not in cache:
            pix=source[pno-1].get_pixmap(matrix=fitz.Matrix(1,1),clip=rect,alpha=False)
            cache[ck]=(pix.width,pix.height,pix.samples,source[pno-1].get_text(clip=rect))
        width,height,expected_pixels,text=cache[ck]
        actual=doc[i].get_pixmap(matrix=fitz.Matrix(1,1),alpha=False)
        assert (width,height)==(actual.width,actual.height),(key,i,"dimensions")
        actual_pixels=actual.samples
        if expected_pixels!=actual_pixels:
            # Integer CropBox translations can change edge antialiasing slightly.
            # Require low pixel error AND byte-identical PDF content streams.
            differences=[abs(a-b) for a,b in zip(expected_pixels,actual_pixels) if a!=b]
            mean=sum(differences)/len(actual_pixels)
            max_mean_difference=max(max_mean_difference,mean)
            assert mean<=1.0,(key,i,"render",mean)
        assert [source.xref_stream(x) for x in source[pno-1].get_contents()]==[doc.xref_stream(x) for x in doc[i].get_contents()],(key,i,"content streams")
        original_images={r[7]:hashlib.sha256(source.xref_stream(r[0])).hexdigest() for r in source[pno-1].get_images()}
        copied_images={r[7]:hashlib.sha256(doc.xref_stream(r[0])).hexdigest() for r in doc[i].get_images()}
        assert original_images==copied_images,(key,i,"embedded images")
        assert text_norm(text)==text_norm(doc[i].get_text()),(key,i,"text")
        if ref.get("part"):
            parts.setdefault(ref["part"],[]).append(text)
        checked+=1
    assert set(parts)=={"문제","정답"}
    if key in {"49","50","51","52","53","54","55","56","57","58","59","60","61","62","63","64","65","66"}:
        assert "2025" in " ".join(parts["문제"]),(key,"latest question year")
        assert "2025" in " ".join(parts["정답"]),(key,"latest answer year")
    if key=="CBL6":
        assert "문제가 출제되지 않았습니다" in " ".join(parts["문제"])
    doc.close()

before=json.loads((HERE/"remote-before.json").read_text(encoding="utf-8"))
archive=json.loads((HERE/"previous-jokbo-archive.json").read_text(encoding="utf-8"))
assert before["quiz_banks"]==0 and len(archive)==67
for row in archive:
    assert hashlib.sha256(Path(row["preserved_local_path"]).read_bytes()).hexdigest()==row["sha256"]
for row in plan["lectures"]:
    assert row["path"]==plan["files"][row["section"]]["path"]
    assert row["lecture_payload"]["runId"]==row["run_id"]

result={"status":"passed","source_pages":183,"derived_pdfs":69,"lecture_targets":80,
        "source_regions_compared":checked,"previous_jokbo_preserved":67,"max_mean_pixel_difference":max_mean_difference,
        "plan_sha256":hashlib.sha256(plan_path.read_bytes()).hexdigest()}
(HERE/"materials-verification.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(result,ensure_ascii=False))

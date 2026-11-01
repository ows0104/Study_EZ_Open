"""Read-only appearance/text checks of the single compatibility copy."""
from pathlib import Path
import hashlib
import json
import re
import subprocess
import pymupdf as fitz

HERE=Path(__file__).resolve().parent
record=json.loads((HERE/"artifact.json").read_text(encoding="utf-8"))
source=Path(record["source_path"])
output=Path(record["output_path"])
assert hashlib.sha256(source.read_bytes()).hexdigest()==record["source_sha256"]==record["server_sha256"]
assert hashlib.sha256(output.read_bytes()).hexdigest()==record["output_sha256"]
a=fitz.open(source);b=fitz.open(output)
assert len(a)==len(b)==48
assert sum(1 for p in b for x in p.annots())==0
assert sum(1 for p in a for x in p.annots())==215
def norm(text):
    return re.sub(r"\s+","",text)
max_error=0.0
text_equal=0
for i in range(len(a)):
    assert a[i].rect==b[i].rect
    assert norm(a[i].get_text())==norm(b[i].get_text()),(i+1,"text")
    text_equal+=1
    x=a[i].get_pixmap(alpha=False);y=b[i].get_pixmap(alpha=False)
    assert (x.width,x.height)==(y.width,y.height)
    if x.samples!=y.samples:
        error=sum(abs(v-w) for v,w in zip(x.samples,y.samples))/len(x.samples)
        max_error=max(max_error,error)
        assert error<=1.0,(i+1,"render",error)
    if i in [0,1,2,10,46]:
        y.save(HERE/"qa"/f"compat-p{i+1}.png")

# Independent renderer: retain sample pages for visual inspection.
for label,path in [("original",source),("compat",output)]:
    subprocess.run(["pdftoppm","-f","1","-l","2","-r","90","-png",str(path),str(HERE/"qa"/f"poppler-{label}")],check=True,capture_output=True)
result={"status":"passed","pages":48,"pages_with_matching_text":text_equal,
        "original_annotations":215,"output_annotations":0,"max_mean_pixel_error":max_error,
        "source_and_server_identical":True,"chatgpt_preview_retested":False,
        "model_reading_accuracy_verified":False}
(HERE/"verification.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(result,ensure_ascii=False))

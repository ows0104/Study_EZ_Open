"""원본 xlsx의 셀 내장 이미지를 라벨 문맥과 함께 추출한다.

    uv run --python 3.13 python scripts/extract_images.py

출력:
    images/<source>/<sheet>/<row>_<col>.<ext>
    data/image_manifest.json   추출된 모든 이미지 + 행 라벨 문맥

엑셀 "셀 안의 그림"(rich value)은 drawing이 아니라
metadata.xml -> rdrichvalue.xml -> richValueRel.xml.rels 체인으로 media에 연결된다.
"""

import hashlib
import json
import os
import re
import shutil
import sys
import xml.etree.ElementTree as ET
import zipfile

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "기생충학")
OUT = os.path.join(ROOT, "images")
DATA = os.path.join(ROOT, "data")

NS = {
    "m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}


def qn(prefix, tag):
    """이름공간이 붙은 태그 이름 하나. ElementTree 는 `{uri}tag` 꼴을 쓴다.

    붙여 쓰는 이유는 읽기 때문이다 — f-string 으로 쓰면 중괄호를 두 겹으로
    겹쳐야 해서(`f"{{{NS[prefix]}}}{tag}"`) 무엇이 리터럴이고 무엇이 값인지
    한눈에 안 보인다.
    """
    return "{" + NS[prefix] + "}" + tag


JMS = os.path.join(SRC, "기생충학 실습 정리본_전민서", "기생충학 실습 정리본_전민서")

# (파일경로, 소스 슬러그, 레이아웃)
SOURCES = [
    (os.path.join(SRC, "2026 실습사진통합.xlsx"), "tonghap", "tonghap"),
    (os.path.join(JMS, "기생충학 실습_전민서 - 충란.xlsx"), "jms_egg", "jms"),
    (os.path.join(JMS, "기생충학 실습_전민서 - 선충.xlsx"), "jms_nematoda", "jms"),
    (os.path.join(JMS, "기생충학 실습_전민서 - 흡충 (1).xlsx"), "jms_trematoda", "jms"),
    (os.path.join(JMS, "기생충학 실습_전민서 - 조충.xlsx"), "jms_cestoda", "jms"),
    (os.path.join(JMS, "기생충학 실습_전민서 - 원충.xlsx"), "jms_protozoa", "jms"),
    (os.path.join(JMS, "기생충 실습_전민서 - 의용곤충.xlsx"), "jms_arthropoda", "jms"),
]

# 전민서 파일 1행 헤더 -> 정규화한 섹션 이름
SECTION_MAP = {
    "종류": "name",
    "염색법": "stain",
    "매개질병": "vector_disease",
    "실습 사진": "실습",
    "실습 사진 (jelly mount 표본은 위가 M, 아래가 F)": "실습",
    "강의록 사진": "강의록",
    "강의록사진": "강의록",
    "크기": "size",
    "주요 특징": "features",
    "땡시판별법": "features",
    "설명": "features",
    "기타": "기타",
    "족보": "jokbo",
}


def col_letter(ref):
    return re.match(r"([A-Z]+)", ref).group(1)


def col_index(letters):
    n = 0
    for ch in letters:
        n = n * 26 + (ord(ch) - 64)
    return n


class Book:
    def __init__(self, path):
        self.z = zipfile.ZipFile(path)
        names = self.z.namelist()
        self.sst = []
        if "xl/sharedStrings.xml" in names:
            root = ET.fromstring(self.z.read("xl/sharedStrings.xml"))
            for si in root.findall("m:si", NS):
                self.sst.append("".join(t.text or "" for t in si.iter(qn("m", "t"))))
        wb = ET.fromstring(self.z.read("xl/workbook.xml"))
        rels = ET.fromstring(self.z.read("xl/_rels/workbook.xml.rels"))
        relmap = {r.get("Id"): r.get("Target") for r in rels}
        self.sheets = [
            (sh.get("name"), relmap[sh.get(qn("r", "id"))])
            for sh in wb.find("m:sheets", NS)
        ]
        self.rel_targets, self.rvlist, self.vm = [], [], []
        if "xl/richData/richValueRel.xml" in names:
            rvrel = ET.fromstring(self.z.read("xl/richData/richValueRel.xml"))
            rvrels = ET.fromstring(self.z.read("xl/richData/_rels/richValueRel.xml.rels"))
            rvrelmap = {r.get("Id"): r.get("Target") for r in rvrels}
            self.rel_targets = [
                rvrelmap[e.get(qn("r", "id"))] for e in rvrel
            ]
            rv = ET.fromstring(self.z.read("xl/richData/rdrichvalue.xml"))
            self.rvlist = [[v.text for v in item] for item in rv]
            md = ET.fromstring(self.z.read("xl/metadata.xml"))
            for vmd in md.iter(qn("m", "valueMetadata")):
                for bk in vmd:
                    self.vm.append(int(bk[0].get("v")))

    def media_for_vm(self, vmidx):
        try:
            target = self.rel_targets[int(self.rvlist[self.vm[vmidx - 1]][0])]
        except (IndexError, ValueError, TypeError):
            return None
        return "xl/" + target.replace("../", "")

    def rows(self, target):
        path = target if target.startswith("xl/") else "xl/" + target
        sx = ET.fromstring(self.z.read(path))
        for row in sx.iter(qn("m", "row")):
            cells = {}
            for c in row:
                ref = c.get("r")
                letters = col_letter(ref)
                if c.get("vm"):
                    media = self.media_for_vm(int(c.get("vm")))
                    if media:
                        cells[letters] = ("IMG", media)
                    continue
                v = c.find("m:v", NS)
                val = v.text if v is not None else ""
                if c.get("t") == "s" and val:
                    val = self.sst[int(val)]
                if val:
                    cells[letters] = ("TXT", val)
            yield int(row.get("r")), cells


def clean(s):
    return re.sub(r"\s+", " ", (s or "").replace("\n", " ")).strip()


def sections_from_header(header_cells):
    """1행 헤더로 열 구간을 나눈다. {col_letters: section}"""
    marks = []
    for letters, (kind, val) in header_cells.items():
        if kind != "TXT":
            continue
        sec = SECTION_MAP.get(clean(val))
        if sec:
            marks.append((col_index(letters), sec))
    marks.sort()
    spans = []
    for i, (start, sec) in enumerate(marks):
        end = marks[i + 1][0] if i + 1 < len(marks) else 10**6
        spans.append((start, end, sec))
    return spans


def section_of(letters, spans):
    idx = col_index(letters)
    for start, end, sec in spans:
        if start <= idx < end:
            return sec
    return "기타"


def extract_tonghap(book, slug, records):
    """통합xlsx: A=한글명 B=영문명 C=크기, D 이후 전부 실습 사진."""
    for sheet_name, target in book.sheets:
        for rno, cells in book.rows(target):
            if rno == 1:
                continue
            name_ko = clean(cells.get("A", (None, ""))[1]) if cells.get("A", ("", ""))[0] == "TXT" else ""
            name_en = clean(cells.get("B", (None, ""))[1]) if cells.get("B", ("", ""))[0] == "TXT" else ""
            size = clean(cells.get("C", (None, ""))[1]) if cells.get("C", ("", ""))[0] == "TXT" else ""
            if not (name_ko or name_en):
                continue
            for letters, (kind, val) in sorted(cells.items(), key=lambda kv: col_index(kv[0])):
                if kind != "IMG":
                    continue
                records.append({
                    "source": slug,
                    "sheet": sheet_name,
                    "row": rno,
                    "cell": letters + str(rno),
                    "section": "실습",
                    "name_ko": name_ko,
                    "name_sub": "",
                    "name_en": name_en,
                    "stage": "",
                    "stain": "",
                    "size": size,
                    "features": "",
                    "_media": val,
                })


def extract_jms(book, slug, records):
    """전민서 파일: 헤더로 섹션을 나누고 이름 열은 위에서 아래로 이월한다."""
    for sheet_name, target in book.sheets:
        spans, carry = None, {"A": "", "B": "", "C": "", "D": ""}
        for rno, cells in book.rows(target):
            if rno == 1:
                spans = sections_from_header(cells)
                continue
            if rno == 2 or spans is None:
                continue
            for key in ("A", "B", "C", "D"):
                cur = cells.get(key)
                if cur and cur[0] == "TXT":
                    carry[key] = clean(cur[1])
                    # 상위 분류가 바뀌면 하위 이름은 초기화
                    if key == "B":
                        carry["C"] = ""
            stain, size, features = "", "", []
            for letters, (kind, val) in cells.items():
                if kind != "TXT" or letters in ("A", "B", "C", "D"):
                    continue
                sec = section_of(letters, spans)
                # 두 칸이 같은 자리에 들어간다 — 매개질환은 염색 칸을 빌려 쓴다.
                if sec in ("stain", "vector_disease"):
                    stain = clean(val)
                elif sec == "size":
                    size = clean(val)
                elif sec == "features":
                    features.append(clean(val))
            for letters, (kind, val) in sorted(cells.items(), key=lambda kv: col_index(kv[0])):
                if kind != "IMG":
                    continue
                sec = section_of(letters, spans)
                if sec not in ("실습", "강의록", "기타"):
                    sec = "기타"
                records.append({
                    "source": slug,
                    "sheet": sheet_name,
                    "row": rno,
                    "cell": letters + str(rno),
                    "section": sec,
                    "name_ko": carry["B"],
                    "name_sub": carry["C"],
                    "name_en": carry["D"],
                    "stage": stain,
                    "stain": stain,
                    "size": size,
                    "features": " / ".join(f for f in features if f),
                    "_media": val,
                })


def main():
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    records = []
    hashes = {}

    for path, slug, layout in SOURCES:
        if not os.path.exists(path):
            print(f"  건너뜀 (없음): {os.path.basename(path)}")
            continue
        book = Book(path)
        before = len(records)
        (extract_tonghap if layout == "tonghap" else extract_jms)(book, slug, records)

        for rec in records[before:]:
            blob = book.z.read(rec.pop("_media"))
            ext = ".png"
            if blob[:3] == b"\xff\xd8\xff":
                ext = ".jpg"
            digest = hashlib.sha1(blob).hexdigest()
            sheet_dir = re.sub(r"[^\w가-힣]+", "_", rec["sheet"]).strip("_")
            rel = os.path.join(slug, sheet_dir, f"{rec['row']:03d}_{rec['cell']}{ext}")
            dest = os.path.join(OUT, rel)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with open(dest, "wb") as fh:
                fh.write(blob)
            rec["path"] = rel.replace("\\", "/")
            rec["bytes"] = len(blob)
            rec["sha1"] = digest
            rec["duplicate_of"] = hashes.get(digest)
            hashes.setdefault(digest, rec["path"])

        print(f"  {slug:16s} {len(records) - before:4d}장")

    with open(os.path.join(DATA, "image_manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(records, fh, ensure_ascii=False, indent=2)

    dups = sum(1 for r in records if r["duplicate_of"])
    total_mb = sum(r["bytes"] for r in records) / 1e6
    print()
    print(f"총 {len(records)}장 / {total_mb:.0f}MB (중복 {dups}장)")
    from collections import Counter
    for sec, n in Counter(r["section"] for r in records).most_common():
        print(f"    {sec:8s} {n:4d}")


if __name__ == "__main__":
    main()

"""족보 PDF에서 과거 문항을 복원한다.

    uv run --python 3.13 --with pymupdf python scripts/parse_jokbo.py

출력:
    questions/<year>/q<NN>_<k>.png   문항별 사진
    data/past_questions.json         문항 텍스트 + 보기 + 정답 + 사진 경로

족보를 읽을 때 걸리는 것들:
  - 2단 조판이고 읽는 순서는 '왼쪽 단 전체 -> 오른쪽 단 전체'다.
  - 문항 번호는 마침표(1.), 보기 번호는 닫는 괄호(1))·가나다·①을 쓴다.
  - 정답표가 문제와 같은 페이지의 반대쪽 단에 들어있는 해가 있다.
  - 2016-1·2017은 정답이 번호가 아니라 답 텍스트로 적혀 있다.
  - 2016-2는 사진도 보기도 없는 복원 목록이라 문항으로 만들 수 없다.
"""

import json
import os
import re
import shutil
import statistics
import sys
from collections import defaultdict

import pymupdf

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "기생충학", "족보")
OUT_IMG = os.path.join(ROOT, "questions")
DATA = os.path.join(ROOT, "data")

PDFS = [
    os.path.join(SRC, "2026 감염의 기초(기생충학) 족보.pdf"),
    os.path.join(SRC, "2025 기생충학 족보.pdf"),
]

COL_SPLIT = 300
MIN_IMG_PX = 40

YEAR_RE = re.compile(r"(?:감염의\s*기초\s*\(기생충학\)|기생충학)\s*(\d{4}(?:-\d)?)\s*(?:학기\s*)?땡시")
HEADER_RE = re.compile(r"감염의\s*기초\s*\(기생충학\)\s*\d{4}\s*족보")
EXAM_RE = re.compile(r"(\d{4}(?:-\d)?)\s*기생충학\s*실습\s*?시험")
Q_RE = re.compile(r"^\s*(\d{1,2})\s*\.\s*(.*)$")
NUMLINE_RE = re.compile(r"^\s*(\d{1,2})\s*\.\s*(.+)$")
OPT_PATTERNS = [
    (re.compile(r"^\s*([①②③④⑤])\s*(.*)$"), "①②③④⑤"),
    (re.compile(r"^\s*•?\s*([가나다라마])\s*[.:]\s*(.*)$"), "가나다라마"),
    (re.compile(r"^\s*([1-5])\s*\)\s*(.*)$"), "12345"),
]
NOISE_KW = ("기생충학 실습시험", "기생충학실습시험", "기생충학 실습 시험",
            "실습시험 준비사항", "족보 제작", "주의사항", "TIP)",
            "참고만 하시기", "정답", "복원되지 않았습니다")


def classify_option(text):
    for pat, order in OPT_PATTERNS:
        m = pat.match(text)
        if m:
            return order.index(m.group(1)), m.group(2).strip()
    return None, None


def page_items(page):
    texts, images = [], []
    for blk in page.get_text("dict")["blocks"]:
        if blk.get("type") != 0:
            continue
        for line in blk["lines"]:
            t = "".join(sp["text"] for sp in line["spans"]).strip()
            if t:
                bb = line["bbox"]
                texts.append({"col": 0 if bb[0] < COL_SPLIT else 1,
                              "y": bb[1], "x": bb[0], "text": t})
    for info in page.get_image_info():
        bb = info["bbox"]
        if info["width"] < MIN_IMG_PX or info["height"] < MIN_IMG_PX:
            continue
        if bb[3] - bb[1] < 20 or bb[2] - bb[0] < 20:
            continue
        images.append({"col": 0 if bb[0] < COL_SPLIT else 1,
                       "y": bb[1], "x": bb[0], "bbox": list(bb)})
    texts.sort(key=lambda i: (i["col"], i["y"], i["x"]))
    images.sort(key=lambda i: (i["col"], i["y"], i["x"]))
    return texts, images


def is_list_region(lines):
    """번호가 촘촘하고 짧고 물음표가 없으면 정답표 또는 복원 목록이다."""
    nums = [(int(m.group(1)), m.group(2)) for m in
            (NUMLINE_RE.match(t) for t in lines) if m]
    if len(nums) < 8:
        return False
    # 정답표는 미복원 문항이 통째로 빠져 있어 번호가 듬성듬성한 해가 있다 (2021, 2022).
    span = max(n for n, _ in nums) - min(n for n, _ in nums) + 1
    if len(nums) / span < 0.6:
        return False
    bodies = [b for _, b in nums]
    if sum("?" in b for b in bodies) / len(bodies) > 0.2:
        return False
    if statistics.median(len(b) for b in bodies) > 45:
        return False
    return True


def scan(doc):
    """페이지·단 단위로 훑어 연도, 목록 영역, 본문 영역을 가른다."""
    pages = []
    year = None
    for pno in range(doc.page_count):
        page = doc[pno]
        texts, images = page_items(page)
        flat = " ".join(t["text"] for t in texts)
        m = YEAR_RE.search(flat) or EXAM_RE.search(flat)
        if m:
            year = m.group(1)
        cols = {}
        for col in (0, 1):
            lines = [t["text"] for t in texts if t["col"] == col]
            cols[col] = is_list_region(lines)
        pages.append({"pno": pno, "year": year, "texts": texts,
                      "images": images, "list_col": cols})
    return pages


def parse_lists(pages):
    """목록 영역(정답표 또는 복원 목록)을 연도별로 모은다."""
    out = defaultdict(dict)
    for pg in pages:
        for col in (0, 1):
            if not pg["list_col"][col]:
                continue
            year = pg["year"]
            lines = [t["text"] for t in pg["texts"] if t["col"] == col]
            for t in lines:
                m = EXAM_RE.search(t)
                if m:
                    year = m.group(1)
                    continue
                # 목록 안에서는 번호 뒤 마침표가 빠진 줄도 받아준다 (2016-2 19번)
                m = NUMLINE_RE.match(t) or re.match(r"^\s*(\d{1,2})\s+(.+)$", t)
                if m and year:
                    out[year].setdefault(int(m.group(1)), m.group(2).strip())
    return out


def parse_questions(pages, pdf_name, questions):
    cur = None
    for pg in pages:
        if not pg["year"]:
            continue
        stream = []
        for col in (0, 1):
            if pg["list_col"][col]:
                continue
            stream += [dict(i, kind="text") for i in pg["texts"] if i["col"] == col]
            stream += [dict(i, kind="image") for i in pg["images"] if i["col"] == col]
        stream.sort(key=lambda i: (i["col"], i["y"], i["x"]))
        for it in stream:
            if it["kind"] == "image":
                if cur is not None:
                    cur["images"].append({"page": pg["pno"], "bbox": it["bbox"]})
                continue
            text = it["text"]
            if YEAR_RE.search(text) or HEADER_RE.search(text):
                continue
            if re.match(r"^-?\s*\d{1,3}\s*-?$", text):
                continue
            if any(k in text for k in NOISE_KW):
                continue
            oi, otext = classify_option(text)
            if oi is not None and cur is not None:
                cur["options"].append((oi, otext))
                continue
            m = Q_RE.match(text)
            if not m and cur is not None:
                m2 = re.match(r"^\s*(\d{1,2})\s+([가-힣A-Za-z(].*)$", text)
                if m2 and int(m2.group(1)) == cur["no"] + 1:
                    m = m2
            if m and 1 <= int(m.group(1)) <= 60:
                if cur:
                    questions.append(cur)
                cur = {"year": pg["year"], "no": int(m.group(1)),
                       "stem": m.group(2).strip(), "options": [], "images": [],
                       "source_pdf": pdf_name, "page": pg["pno"] + 1}
                continue
            if cur is None:
                continue
            if cur["options"]:
                last = cur["options"][-1]
                cur["options"][-1] = (last[0], (last[1] + " " + text).strip())
            else:
                cur["stem"] = (cur["stem"] + " " + text).strip()
    if cur:
        questions.append(cur)


def resolve_answer(raw, options):
    """정답 표기를 보기 번호로 바꾼다. 번호, (번호), 가나다, 답 텍스트를 모두 받는다."""
    if not raw:
        return None, None
    raw = raw.strip()
    m = re.match(r"^\(?([1-5])\)?\s*(.*)$", raw)
    if m:
        return int(m.group(1)) - 1, m.group(2).strip() or None
    letters = {"가": 0, "나": 1, "다": 2, "라": 3, "마": 4}
    if raw and raw[0] in letters and (len(raw) == 1 or not raw[1].isalnum()):
        return letters[raw[0]], None
    key = re.sub(r"[^0-9a-z가-힣]", "", raw.lower())
    if key:
        for i, opt in enumerate(options):
            o = re.sub(r"[^0-9a-z가-힣]", "", opt.lower())
            if o and (o == key or key in o or o in key):
                return i, raw
    return None, raw


def main():
    if os.path.isdir(OUT_IMG):
        shutil.rmtree(OUT_IMG)
    questions, lists, docs = [], {}, {}
    for path in PDFS:
        name = os.path.basename(path)
        doc = pymupdf.open(path)
        docs[name] = doc
        pages = scan(doc)
        parse_questions(pages, name, questions)
        for y, table in parse_lists(pages).items():
            lists.setdefault(y, {}).update(table)

    years_with_q = {q["year"] for q in questions}
    recall = {y: t for y, t in lists.items() if y not in years_with_q}
    answers = {y: t for y, t in lists.items() if y in years_with_q}

    for q in questions:
        opts = [t for _, t in sorted(q["options"], key=lambda o: o[0])]
        inline = None
        cleaned = []
        for o in opts:
            # 보기 끝에 다음 문항 안내가 흘러든 경우를 잘라낸다
            o = re.sub(r"\s*\d{1,2}\s*[~-]\s*\d{1,2}\s*복원.*$", "", o)
            o = re.sub(r"\s*\d{1,2}\s*복원안됨.*$", "", o)
            m = re.search(r"\s*답\s*[:：]?\s*([1-4])\s*$", o)
            if m:
                inline = m.group(1)
                o = o[:m.start()].strip()
            cleaned.append(o)
        q["options"] = [o for o in cleaned if o]
        raw = answers.get(q["year"], {}).get(q["no"]) or inline
        idx, text = resolve_answer(raw, q["options"])
        q["answer_raw"] = raw
        q["answer_index"] = idx
        q["answer_text"] = text
        q["stem"] = re.sub(r"\s*-\s*가급적 실습시간에.*$", "", q["stem"]).strip()
        q["stem"] = re.sub(r"\s*성한 부분이 많으니.*$", "", q["stem"]).strip()
        if q["stem"] and len(q["options"]) >= 3:
            q["format"] = "mcq"
        elif q["stem"] and (q["answer_text"] or q["answer_raw"]):
            q["format"] = "short_answer"
        else:
            q["format"] = "unrestored"
        q["restored"] = q["format"] != "unrestored"
        paths = []
        for k, im in enumerate(q["images"], 1):
            page = docs[q["source_pdf"]][im["page"]]
            pix = page.get_pixmap(clip=pymupdf.Rect(im["bbox"]), dpi=200)
            rel = f"{q['year']}/q{q['no']:02d}_{k}.png"
            dest = os.path.join(OUT_IMG, rel)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            pix.save(dest)
            paths.append(rel)
        q["image_paths"] = paths
        del q["images"]

    questions.sort(key=lambda q: (q["year"], q["no"]))
    payload = {
        "questions": questions,
        "recall_lists": [{"year": y, "no": n, "text": t}
                         for y, tbl in sorted(recall.items())
                         for n, t in sorted(tbl.items())],
    }
    with open(os.path.join(DATA, "past_questions.json"), "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)

    print(f"복원 문항 {len(questions)}개, 복원 목록 {len(payload['recall_lists'])}줄\n")
    print("연도      문항  객관식  단답  미복원  정답  사진")
    def row(label, qs):
        c = lambda f: sum(1 for q in qs if q["format"] == f)
        print(f"{label:9s} {len(qs):4d}  {c('mcq'):5d}  {c('short_answer'):4d}"
              f"  {c('unrestored'):6d}  {sum(1 for q in qs if q['answer_index'] is not None):4d}"
              f"  {sum(1 for q in qs if q['image_paths']):4d}")
    for year in sorted(years_with_q):
        row(year, [q for q in questions if q["year"] == year])
    row("합계", questions)
    print()
    for year in sorted(years_with_q):
        qs = [q for q in questions if q["year"] == year]
        nums = sorted(q["no"] for q in qs)
        gaps = [n for n in range(1, max(nums) + 1) if n not in nums]
        dup = [n for n in set(nums) if nums.count(n) > 1]
        if gaps or dup:
            print(f"  {year}: 빠진 번호 {gaps or '없음'}, 중복 번호 {dup or '없음'}")


if __name__ == "__main__":
    main()

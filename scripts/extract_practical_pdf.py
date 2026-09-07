"""실제실습본 PDF의 슬라이드 사진을 추출한다 (세 번째 이미지 소스).

    uv run --python 3.13 --with pymupdf python scripts/extract_practical_pdf.py

이 PDF는 페이지마다 맨 위에 종 이름이 오고 그 아래에 실습 슬라이드 사진이 깔린다.
사진은 inline image라 xref가 없어서 bbox로 잘라내야 한다.
사진 옆·아래의 짧은 텍스트가 배율·염색·구조물 캡션이다.

출력: images/practical/<페이지>_<n>.png
      data/practical_manifest.json
"""

import json
import os
import re
import shutil
import sys

import pymupdf

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
OUT = os.path.join(ROOT, "images", "practical")
PDF = os.path.join(ROOT, "기생충학",
                   "실제실습본 (본인만 만든게 아니라 안 그럴거같지만 반출금지!! ㅠㅠ).pdf")

MIN_SIDE = 120          # 페이지 좌표 기준. 이보다 작으면 장식·아이콘
TITLE_MAX_Y = 60        # 이 위쪽 텍스트를 제목으로 본다
DPI_MIN = 200           # 이 아래로는 안 내려간다
DPI_MAX = 600           # 이 위로는 파일만 커진다
LATIN_RE = re.compile(r"\b([A-Z][a-z]{3,})\s+([a-z]{3,})\b")
# 이어지는 페이지는 제목 자리에 캡션(male, 40x, Schizont)이 온다.
# 학명이나 한국어 기생충 이름이 있을 때만 제목을 새로 잡고, 아니면 앞 제목을 이어쓴다.
KO_NAME_RE = re.compile(
    r"(회충|편충|구충|요충|분선충|선모충|사상충|고래회충|간흡충|폐흡충|요코가와흡충"
    r"|간질|주걱흡충|큰입흡충|주혈흡충|조충|낭미충|고충|아메바|편모충|섬모충"
    r"|열원충|포자충|말라리아|진드기|모기|벼룩)")


def render_dpi(info):
    """이 사진을 페이지에서 잘라낼 때 쓸 해상도.

    사진은 inline image라 xref로 원본을 꺼낼 수 없고 페이지를 래스터화해서
    잘라내야 한다 — 잘라내는 해상도가 곧 결과물의 해상도다.

    **200dpi로 일률적으로 잘랐더니 323장 중 143장이 손해였다.** 페이지에
    놓인 폭(포인트)과 내장 원본의 픽셀 폭의 비가 그 사진이 실제로 가진
    해상도인데, 그 값이 200을 넘는 것이 44%고 600을 넘는 것도 49장이다
    (최대 1264dpi). 넘는 만큼은 그대로 버려졌다.

    그래서 사진마다 자기 해상도로 자른다. 원본이 흐린 쪽(하위 10%가 73dpi)은
    올려 봐야 없는 detail이 생기지 않으므로 `DPI_MIN`에서 멈추고, 위쪽은
    파일 크기가 제곱으로 늘기 때문에 `DPI_MAX`에서 끊는다.
    """
    w_pt = info["bbox"][2] - info["bbox"][0]
    if w_pt <= 0:
        return DPI_MIN
    native = info["width"] / (w_pt / 72.0)
    return int(min(max(native, DPI_MIN), DPI_MAX))


def wipe_text(page):
    """이 페이지의 **글자만** 지운다. 사진과 화살표는 그대로 둔다.

    정리본은 사진 위에 설명을 얹어 놓는다 — 「male, 400x / dorsal costa」,
    「oral cavity」 같은 것들이다. 페이지를 통째로 래스터화해서 잘라내므로
    그 글자가 사진에 같이 구워지고, **그건 곧 정답을 적어 둔 문항이 된다.**
    실제로 무작위 6장 중 2장에 그런 글자가 있었다.

    다행히 얹힌 것이 PDF 텍스트라 지우면 사진이 온전히 남는다. 픽셀에 구워진
    글자였다면 덧칠밖에 방법이 없고 그건 표본 위를 뭉개는 일이다.

      · `fill=None`  — 지운 자리에 흰 상자를 안 그린다. 그리면 글자 대신
                       흰 얼룩이 남아서 나아진 것이 없다
      · 사진(`IMAGE_NONE`)과 선화(`LINE_ART_NONE`)는 손대지 않는다.
        **화살표는 남겨야 한다** — indicator 문항이 가리키는 것이 그것이다

    글을 읽는 일(제목·캡션)은 반드시 이 함수보다 **먼저** 끝내야 한다.
    """
    words = page.get_text("words")
    if not words:
        return 0
    for w in words:
        page.add_redact_annot(pymupdf.Rect(w[:4]), fill=None)
    page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE,
                          graphics=pymupdf.PDF_REDACT_LINE_ART_NONE,
                          text=pymupdf.PDF_REDACT_TEXT_REMOVE)
    return len(words)


def page_lines(page):
    out = []
    for blk in page.get_text("dict")["blocks"]:
        if blk.get("type") != 0:
            continue
        for line in blk["lines"]:
            t = "".join(sp["text"] for sp in line["spans"]).strip()
            if t:
                size = max(sp["size"] for sp in line["spans"])
                out.append({"text": t, "bbox": line["bbox"], "size": size})
    return out


def title_of(lines):
    """페이지 상단의 가장 큰 글씨가 종 이름이다."""
    top = [l for l in lines if l["bbox"][1] < TITLE_MAX_Y]
    if not top:
        return None
    top.sort(key=lambda l: (-l["size"], l["bbox"][1]))
    return top[0]["text"].strip()


def captions_for(bbox, lines):
    """사진 안이나 바로 아래 40pt 안에 있는 짧은 텍스트를 캡션으로 본다."""
    x0, y0, x1, y1 = bbox
    out = []
    for l in lines:
        lx0, ly0, lx1, ly1 = l["bbox"]
        inside = lx0 >= x0 - 5 and lx1 <= x1 + 5 and ly0 >= y0 - 5 and ly1 <= y1 + 5
        below = (y1 <= ly0 <= y1 + 40) and not (lx1 < x0 or lx0 > x1)
        if (inside or below) and len(l["text"]) < 80 and l["bbox"][1] > TITLE_MAX_Y:
            out.append(l["text"].strip())
    return out


SECTION_RE = [("충란", r"연충란|Helminth\s*eggs"), ("선충", r"선충류|Nematodes"),
              ("흡충", r"흡충류|Trematodes"), ("조충", r"조충류|Cestodes"),
              ("원충", r"원충|protozoa")]


def section_topics(doc):
    """섹션 표지 페이지를 찾아 페이지별 주제를 정한다.

    표지는 보통 사진이 없지만 원충 표지(p74)처럼 목차 그림이 한 장 붙은 경우가 있어
    사진 1장까지는 표지로 인정한다. 대신 페이지 앞머리에서만 제목을 찾는다.
    """
    marks = {}
    for pno in range(doc.page_count):
        page = doc[pno]
        if len(page.get_image_info()) > 1:
            continue
        head = page.get_text()[:200]
        for name, pat in SECTION_RE:
            if re.search(pat, head, re.I):
                marks[pno] = name
                break
    topics, cur = {}, None
    for pno in range(doc.page_count):
        if pno in marks:
            cur = marks[pno]
        topics[pno] = cur
    return topics


def main():
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT, exist_ok=True)
    doc = pymupdf.open(PDF)

    records = []
    title = None
    wiped = 0
    topics = section_topics(doc)
    for pno in range(doc.page_count):
        page = doc[pno]
        lines = page_lines(page)
        t = title_of(lines)
        if t and (LATIN_RE.search(t) or (KO_NAME_RE.search(t) and len(t) < 50)):
            title = t
        latin = ""
        m = LATIN_RE.search(title or "")
        if m:
            latin = f"{m.group(1)} {m.group(2)}"
        # 페이지 머리 설명(감별점)도 함께 남긴다
        header = " / ".join(l["text"] for l in lines
                            if TITLE_MAX_Y <= l["bbox"][1] < 115 and len(l["text"]) < 120)

        infos = [i for i in page.get_image_info()
                 if (i["bbox"][2] - i["bbox"][0]) >= MIN_SIDE
                 and (i["bbox"][3] - i["bbox"][1]) >= MIN_SIDE]
        infos.sort(key=lambda i: (round(i["bbox"][1] / 40), i["bbox"][0]))

        # 여기까지 글을 다 읽었다(제목·머리말·캡션·사진 자리). 이제 지운다 —
        # 아래에서 페이지를 그리면 글자가 사진에 구워지기 때문이다.
        wiped += wipe_text(page)

        for k, info in enumerate(infos, 1):
            bbox = info["bbox"]
            rel = f"practical/{pno + 1:03d}_{k}.png"
            pix = page.get_pixmap(clip=pymupdf.Rect(bbox), dpi=render_dpi(info))
            pix.save(os.path.join(ROOT, "images", rel))
            records.append({
                "source": "practical",
                "sheet": "실제실습본",
                "page": pno + 1,
                "cell": f"p{pno + 1:03d}_{k}",
                "section": "실습",
                "topic": topics.get(pno),
                "name_ko": title or "",
                "name_sub": "",
                "name_en": latin,
                "stage": " / ".join(captions_for(bbox, lines))[:120],
                "size": "",
                "features": header[:200],
                "path": rel,
                "px_w": info["width"],
                "px_h": info["height"],
            })
        if not infos and t:
            pass

    with open(os.path.join(DATA, "practical_manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(records, fh, ensure_ascii=False, indent=2)

    from collections import Counter as _C
    print("─ 섹션별", dict(_C(r["topic"] for r in records)))
    print(f"추출 {len(records)}장 · 사진에 구워질 뻔한 글자 {wiped}낱말 지움")
    named = sum(1 for r in records if r["name_en"])
    print(f"학명이 붙은 것 {named}장 / 제목만 있는 것 {len(records) - named}장")
    from collections import Counter
    print("\n─ 페이지 제목별 장수 (상위 25)")
    for t, n in Counter(r["name_ko"] for r in records).most_common(25):
        print(f"    {n:3d}  {t[:60]}")


if __name__ == "__main__":
    main()

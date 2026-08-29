"""강의 필기 PDF를 증거 채널로 정규화한다.

필기본 PDF 하나에서 세 가지를 만든다.

  clean.pdf       annotation을 걷어낸 강의록. 질문·정답의 근거가 될 수 있다.
  annotated.pdf   원본 그대로. 모델이 실제로 보는 페이지다.
  prep.json/.md   슬라이드별 사이드카. 무엇이 강의록이고 무엇이 필기인지 코드가 확정해 준다.

위계는 색이나 필기자 규약이 아니라 구조에서 나온다.
페이지 컨텐트 = 강의록, annotation 객체 = 필기. 어떤 필기본에서도 참이다.
필기의 연도는 annotation의 creationDate에서 얻는다. 색 규약을 읽지 않는다.

사용:
    python -m pdf2anki.prep "필기_예시/....pdf" -o out/lec03
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

import fitz

# 근거가 될 수 있는 그림으로 볼 최소 크기 (pt)
MIN_FIGURE_PT = 150
# 라벨(오클루전 후보)로 볼 필기 최대 길이.
# 18자였을 때 `type II 폐포세포 재생` 같은 **핵심 용어**가 후보에서 빠졌다.
# 가릴 만한 것은 대개 짧지만, 영문 용어가 섞이면 금세 18자를 넘는다.
MAX_LABEL_CHARS = 24
# 오클루전은 라벨처럼 작은 대상을 가리는 형식이다. FreeText 상자가 그림의 큰 부분을
# 차지하면 실제 텍스트보다 넓은 기본 입력 상자이거나 설명 메모인 경우가 많다.
MAX_LABEL_AREA_RATIO = 0.18
MAX_LABEL_HEIGHT_RATIO = 0.35
# 반복 스탬프를 '마커 어휘'로 볼 최소 등장 횟수
MARKER_MIN_COUNT = 3
# 슬라이드 번호 배지 크기 (pt)
BADGE_W, BADGE_H = 78, 22

EMPHASIS_TYPES = {"Square", "Highlight", "Underline", "Line", "Polygon", "Ink", "StrikeOut"}
GENERIC_SUBJECTS = {"stamp", "스탬프", "도장", ""}


def usable_occlusion_label(text: str, label_rect: list, figure_bbox: list) -> bool:
    """필기 FreeText가 실제로 가릴 만한 작은 라벨인지 기계적으로 거른다.

    중요도 자체는 모델이 승인된 학습 목표와 대조해야 한다. 여기서는 그보다 앞단의
    명백한 잡음(문자 없는 표시, 그림 대부분을 덮는 설명 상자)을 후보에서 없앤다.
    """
    text = text.strip()
    if not text or len(text) > MAX_LABEL_CHARS:
        return False
    if not re.search(r"[0-9A-Za-z가-힣]", text):
        return False

    nr, fr = fitz.Rect(label_rect), fitz.Rect(figure_bbox)
    if not nr.is_valid or not fr.is_valid or fr.get_area() <= 0:
        return False
    inter = nr & fr
    if not inter.is_valid or inter.get_area() <= 0.6 * max(nr.get_area(), 1):
        return False
    if nr.get_area() / fr.get_area() > MAX_LABEL_AREA_RATIO:
        return False
    if nr.height / fr.height > MAX_LABEL_HEIGHT_RATIO:
        return False
    return True


def annot_year(a: fitz.Annot) -> str:
    m = re.match(r"D:(\d{4})", a.info.get("creationDate") or "")
    return m.group(1) if m else "unknown"


def figures_of(page: fitz.Page) -> list[dict]:
    """근거가 될 만한 크기의 래스터 그림."""
    out = []
    for blk in page.get_text("dict")["blocks"]:
        if blk["type"] != 1:
            continue
        x0, y0, x1, y1 = blk["bbox"]
        if (x1 - x0) < MIN_FIGURE_PT or (y1 - y0) < MIN_FIGURE_PT:
            continue
        out.append({"id": f"fig_p{page.number + 1:02d}_{len(out) + 1:02d}",
                    "bbox": [round(v, 1) for v in blk["bbox"]],
                    "px": [blk.get("width"), blk.get("height")]})
    return out


def covered_text(clean_page: fitz.Page, rect: fitz.Rect) -> list[str]:
    """형광펜·밑줄·상자가 덮은 강의록 텍스트.

    무엇이 강조됐는지가 어디에 카드를 몰지를 정한다. 표시 개수만으로는 알 수 없다.
    래스터 슬라이드에는 텍스트 레이어가 없어 빈 목록이 나온다 — 그건 정상이다.
    """
    out = []
    for blk in clean_page.get_text("dict")["blocks"]:
        if blk["type"] != 0:
            continue
        for ln in blk["lines"]:
            lr = fitz.Rect(ln["bbox"])
            if (lr & rect).get_area() > 0.30 * max(lr.get_area(), 1):
                t = "".join(sp["text"] for sp in ln["spans"]).strip()
                if t:
                    out.append(t)
    return out[:3]


def classify_stamps(doc: fitz.Document) -> dict[str, str | None]:
    """스탬프 name → 마커 라벨. 1회성 스탬프는 None(붙여넣은 자료)."""
    counts = Counter()
    subjects: dict[str, Counter] = {}
    for page in doc:
        for a in page.annots():
            if a.type[1] != "Stamp":
                continue
            name = a.info.get("name", "")
            counts[name] += 1
            subjects.setdefault(name, Counter())[(a.info.get("subject") or "").strip()] += 1
    labels: dict[str, str | None] = {}
    anon = 0
    for name, n in counts.items():
        if n < MARKER_MIN_COUNT:
            labels[name] = None
            continue
        subj = subjects[name].most_common(1)[0][0]
        if subj.lower() in GENERIC_SUBJECTS:
            anon += 1
            subj = f"marker_{chr(64 + anon)}"      # 이름 없는 반복 스탬프
        labels[name] = subj
    return labels


def stamp_slide_numbers(doc: fitz.Document) -> list[int]:
    """페이지 아래에 띠를 덧대고 거기에 슬라이드 번호를 적는다.

    모서리에 얹으면 전면 이미지 슬라이드에서 내용을 가린다. 아래로 늘리면
    좌상단 원점 기준 좌표가 그대로라 prep.json의 rect가 전부 유효하다.
    늘리지 못한 페이지는 번호를 반환해 호출자가 알 수 있게 한다.
    """
    failed = []
    for page in doc:
        mb = page.mediabox                       # PDF 좌표계 (원점 좌하단)
        try:
            page.set_mediabox(fitz.Rect(mb.x0, mb.y0 - BADGE_H, mb.x1, mb.y1))
        except Exception:
            failed.append(page.number + 1)
            continue
        w, h = page.rect.width, page.rect.height
        band = fitz.Rect(0, h - BADGE_H, w, h)
        page.draw_rect(band, color=(0.8, 0.8, 0.8), fill=(1, 1, 1), width=0.5, overlay=True)
        # insert_textbox 는 상자에 안 맞으면 조용히 실패한다. baseline 기준 insert_text 를 쓴다.
        page.insert_text(fitz.Point(8, h - 6), f"Slide {page.number + 1}",
                         fontsize=12, fontname="helv", color=(0, 0, 0), overlay=True)
        if not any("Slide" in "".join(s["text"] for s in ln["spans"])
                   for b in page.get_text("dict")["blocks"] if b["type"] == 0
                   for ln in b["lines"]):
            failed.append(page.number + 1)
    return failed


def build(src: Path, outdir: Path) -> dict:
    outdir.mkdir(parents=True, exist_ok=True)
    ann = fitz.open(src)
    stamp_labels = classify_stamps(ann)

    # clean = annotation 제거본. 원본 파일은 건드리지 않는다.
    clean = fitz.open(src)
    for page in clean:
        # `list(page.annots())` 로 미리 담아도 안 된다. 답글(IRT)이 달린 주석이 하나라도
        # 있으면 앞의 것을 지우는 순간 뒤의 것이 페이지에서 떨어져
        # `Annot is not bound to a page` 로 죽는다. `[260820_01] 소아질환(1)` 이
        # 그랬다 — 주석 374개 중 IRT 가 달린 것은 단 하나였다.
        # delete_annot 은 다음 주석을 돌려주므로 그 사슬을 따라간다.
        a = page.first_annot
        while a:
            a = page.delete_annot(a)

    slides, covered_report = [], []
    for i in range(ann.page_count):
        ap, cp = ann[i], clean[i]
        lecture_text = cp.get_text().strip()
        lecture_figs = figures_of(cp)

        notes, markers, pasted = [], [], []
        opaque: list[fitz.Rect] = []
        for a in ap.annots():
            t, yr, r = a.type[1], annot_year(a), [round(v, 1) for v in a.rect]
            if t == "FreeText":
                txt = re.sub(r"[\r\n]+", " ", a.info.get("content", "")).strip()
                if txt:
                    notes.append({"year": yr, "text": txt, "rect": r})
                opaque.append(a.rect)
            elif t == "Stamp":
                label = stamp_labels.get(a.info.get("name", ""))
                if label:
                    markers.append({"kind": "stamp", "label": label, "year": yr, "rect": r})
                    opaque.append(a.rect)
                else:
                    pasted.append({"year": yr, "rect": r})
            elif t in EMPHASIS_TYPES:
                markers.append({"kind": a.type[1].lower(), "year": yr, "rect": r,
                                "covers": covered_text(cp, a.rect)})

        # 필기가 강의록을 덮었는가 (덮었으면 그 슬라이드만 clean 렌더가 따로 필요하다)
        covered = []
        for kind, rect in ([("text", fitz.Rect(line["bbox"]))
                            for b in cp.get_text("dict")["blocks"] if b["type"] == 0
                            for line in b["lines"]]
                           + [("figure", fitz.Rect(f["bbox"])) for f in lecture_figs]):
            if rect.get_area() < 60:
                continue
            ov = sum((rect & o).get_area() for o in opaque if (rect & o).is_valid)
            if ov / rect.get_area() > 0.35:
                covered.append({"kind": kind, "bbox": [round(v, 1) for v in rect],
                                "ratio": round(ov / rect.get_area(), 2)})
        if covered:
            covered_report.append(i + 1)

        # 오클루전 후보: 그림 위에 얹힌 짧고 작은 필기 라벨.
        # Square는 강조 신호일 뿐 "상자 안 무엇이 답인지"가 정해져 있지 않다. 예전에는
        # label=None 후보로 넘겼고, 모델이 엉뚱한 구조나 중요하지 않은 영역을 고르는 가장
        # 큰 통로가 됐다. markers에는 그대로 남기되 자동 오클루전 후보로 만들지 않는다.
        occl = []
        for n in notes:
            for f in lecture_figs:
                if usable_occlusion_label(n["text"], n["rect"], f["bbox"]):
                    occl.append({"id": f"occ_p{i + 1:02d}_{len(occl) + 1:02d}",
                                 "label": n["text"], "label_rect": n["rect"],
                                 "kind": "annotation_label",
                                 "figure_id": f["id"], "figure_bbox": f["bbox"],
                                 "year": n["year"]})
                    break

        slides.append({"slide": i + 1, "size": [round(ap.rect.width), round(ap.rect.height)],
                       "lecture_text": lecture_text, "lecture_figures": lecture_figs,
                       "annotations": notes, "markers": markers, "pasted_images": pasted,
                       "occlusion_candidates": occl, "covered_by_annotation": covered})

    badge_failed = stamp_slide_numbers(ann) + stamp_slide_numbers(clean)
    ann.save(outdir / "annotated.pdf", deflate=True)
    clean.save(outdir / "clean.pdf", deflate=True)

    years = Counter(n["year"] for s in slides for n in s["annotations"])
    prep = {
        "source": src.name,
        "slides": ann.page_count,
        "annotated_pdf": "annotated.pdf",
        "clean_pdf": "clean.pdf",
        "channel_policy": {
            "lecture_text": "근거 가능",
            "lecture_figures": "근거 가능",
            "annotations": "기본 근거 불가 · 중요도 신호. 기출이 그 지점을 실제로 물었으면 근거로 승격",
            "markers": "우선순위 신호만. 근거 아님",
            "pasted_images": "필기자가 붙인 외부 자료. 근거 아님",
        },
        "annotation_years": dict(sorted(years.items(), reverse=True)),
        "stamp_markers": {v: k for k, v in stamp_labels.items() if v},
        "badge_failed_slides": sorted(set(badge_failed)),
        "slides_with_covered_lecture_content": covered_report,
        "pages": slides,
    }
    (outdir / "prep.json").write_text(json.dumps(prep, ensure_ascii=False, indent=2), encoding="utf-8")
    (outdir / "prep.md").write_text(to_markdown(prep), encoding="utf-8")
    return prep


def where(bbox: list, size: list) -> str:
    """슬라이드 안에서의 대략적인 위치. 모델이 그림과 사이드카 id 를 짝지을 수 있게 한다."""
    w, h = size
    cx, cy = (bbox[0] + bbox[2]) / 2 / w, (bbox[1] + bbox[3]) / 2 / h
    col = "좌" if cx < 0.38 else ("우" if cx > 0.62 else "중앙")
    row = "상" if cy < 0.38 else ("하" if cy > 0.62 else "중")
    return f"[{col}{row}]"


def to_markdown(prep: dict) -> str:
    """프롬프트에 그대로 붙일 사이드카."""
    L = [f"# 슬라이드 사이드카 — {prep['source']} ({prep['slides']}장)", "",
         "채널 위계 (코드가 확정한 것이며 뒤집지 말 것):"]
    for k, v in prep["channel_policy"].items():
        L.append(f"- `{k}` — {v}")
    if prep["annotation_years"]:
        L.append("")
        L.append("필기 작성연도별 개수: " +
                 " · ".join(f"{y} {n}개" for y, n in prep["annotation_years"].items()) +
                 "  (최근 연도일수록 올해 강의의 강조점에 가깝다)")
    if prep["stamp_markers"]:
        L.append("반복 스탬프 마커: " + ", ".join(prep["stamp_markers"]))
    if prep["slides_with_covered_lecture_content"]:
        L.append(f"⚠ 필기가 강의록을 덮은 슬라이드: {prep['slides_with_covered_lecture_content']}"
                 " — 이 슬라이드는 clean.pdf를 따로 확인할 것")
    L.append("")
    for s in prep["pages"]:
        L.append(f"## Slide {s['slide']}")
        if s["lecture_text"]:
            L.append("강의록 본문:")
            L.append("```")
            L.append(s["lecture_text"])
            L.append("```")
        if s["lecture_figures"]:
            L.append("강의록 그림:")
            for f in s["lecture_figures"]:
                L.append(f"  - {f['id']} {where(f['bbox'], s['size'])} "
                         f"{round(f['bbox'][2] - f['bbox'][0])}x{round(f['bbox'][3] - f['bbox'][1])}pt "
                         f"(원본 {f['px'][0]}x{f['px'][1]}px)")
        for n in s["annotations"]:
            L.append(f"- 필기({n['year']}): {n['text']}")
        if s["markers"]:
            c = Counter(f"{m.get('label') or m['kind']}" for m in s["markers"])
            L.append("- 표시: " + ", ".join(f"{k}×{v}" for k, v in c.items()))
            for m in s["markers"]:
                if m.get("covers"):
                    L.append(f"  - {m['kind']}가 덮은 문구: " +
                             " / ".join(f"{t!r}" for t in m["covers"]))
        for o in s["occlusion_candidates"]:
            pos = where(o["label_rect"], s["size"])
            L.append(f"- 오클루전 후보 {o['id']}: {pos} "
                     + (f"라벨 {o['label']!r} on {o['figure_id']}" if o["label"]
                        else f"영역 상자 on {o['figure_id']} (이름 미상)"))
        if s["pasted_images"]:
            L.append(f"- 필기자가 붙인 그림 {len(s['pasted_images'])}개 (근거 아님)")
        L.append("")
    return "\n".join(L)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="강의 필기 PDF를 증거 채널로 정규화한다")
    ap.add_argument("pdf")
    ap.add_argument("-o", "--out", required=True)
    args = ap.parse_args(argv)

    prep = build(Path(args.pdf), Path(args.out))
    p = prep["pages"]
    print(f"슬라이드 {prep['slides']}장 → {args.out}/annotated.pdf, clean.pdf, prep.json, prep.md")
    bad = prep["badge_failed_slides"]
    print(f"슬라이드 번호: 페이지 하단에 {BADGE_H}pt 띠를 덧대 각인"
          + (f"  ⚠ 실패 {bad}" if bad else "  (전 페이지 성공, 내용 가림 없음)"))
    print(f"필기 {sum(len(s['annotations']) for s in p)}개 "
          f"(연도별 {prep['annotation_years']})")
    print(f"반복 스탬프 마커: {prep['stamp_markers'] or '없음'}")
    print(f"강의록 본문이 있는 슬라이드: {sum(1 for s in p if s['lecture_text'])}/{prep['slides']}")
    print(f"강의록 그림 {sum(len(s['lecture_figures']) for s in p)}개 · "
          f"오클루전 후보 {sum(len(s['occlusion_candidates']) for s in p)}개 · "
          f"필기자가 붙인 그림 {sum(len(s['pasted_images']) for s in p)}개")
    cov = prep["slides_with_covered_lecture_content"]
    print(f"필기가 강의록을 덮은 슬라이드: {cov if cov else '없음'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

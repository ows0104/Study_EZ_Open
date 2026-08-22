"""검증을 통과한 카드를 Anki 덱(.apkg)으로 만든다.

빌드는 파이프라인의 마지막 칸이다. 입력은 **재현 검사를 거친 카드**다.
`items.reproduced.json` 이 있으면 그걸 쓰고, 없으면 재현 검사를 아직 안 돌린 것이므로
멈춘다(`--skip-reproduce` 로 넘길 수는 있다 — 넘겼다는 사실은 출력에 남는다).
재현 불가로 판정된 카드가 남아 있으면 덱을 만들지 않는다. 답이 재현되지 않는 카드는
외워도 시험장에서 꺼내 쓸 수 없으므로, 덱에 들어가면 안 된다.

빌드는 그 판정을 **읽기만 한다.** 여기서 내용을 새로 판단하지는 않는다.

카드마다 **출처 슬라이드 전체 이미지**를 뒷면에 붙인다. 답을 확인한 뒤 원본 맥락을
바로 볼 수 있어야 한다. 강의록 기원과 기출 기원은 하위 덱으로 나눈다.

이미지 카드의 크롭은 정답이 함께 잘려 들어오기 쉽다 — 필기자가 슬라이드를 통째로
스크린샷해 붙였기 때문에 '그림' 이 곧 '캡션 포함 슬라이드' 인 경우가 많다.
그래서 `media.crop` 으로 그림 안에서 다시 잘라낼 수 있게 열어 둔다(그림 기준 비율).
캡션이 픽셀이라 코드로는 못 찾는다. 접촉 시트로 눈검사하는 수밖에 없다.

사용:
    python -m pdf2anki.build out/lec03 --deck "병리학::17 소아질환의 병태생리(2)"
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sqlite3
import sys
import tempfile
import zipfile
from collections import Counter
from pathlib import Path

import fitz
import genanki

from .textutil import norm_key

# 재현 검사에서 '카드 결함' 으로 갈린 이유. lecture_specific · genuinely_wrong 은 결함이 아니다.
DEFECT_REASONS = ("question_ambiguous", "needs_options", "answer_underspecified")

RENDER_ZOOM = 2.0          # 크롭 렌더 배율
SLIDE_ZOOM = 1.6           # 뒷면에 붙는 슬라이드 전체 렌더 배율
JOKBO_ZOOM = 1.5           # 뒷면에 붙는 족보 지면 렌더 배율
CROP_MARGIN = 6            # 그림 둘레 여백 (pt)
MASK_FILL = (0.86, 0.86, 0.88)
MASK_EDGE = (0.80, 0.20, 0.20)

CSS = """
.card { font-family: -apple-system, "Segoe UI", "Malgun Gothic", sans-serif;
        font-size: 20px; line-height: 1.6; text-align: center;
        color: #1a1a1a; background: #ffffff; padding: 16px; }
.nightMode.card, .card.nightMode { color: #e8e8e8; background: #1e1e1e; }
.q { font-size: 22px; font-weight: 600; margin-bottom: 12px; white-space: pre-line; }
.a { font-size: 24px; font-weight: 700; color: #0b5cad; margin: 12px auto;
     display: inline-block; text-align: left; max-width: 100%; white-space: pre-line; }
.nightMode .a { color: #7ab8f5; }
.a ul { text-align: left; margin: 4px 0; padding-left: 1.15em; }
.a li { margin: 3px 0; }
.a ul ul { margin: 2px 0 2px 0; padding-left: 1.0em; font-size: 0.94em; font-weight: 600; }
.a .lead { margin-bottom: 5px; }
img { max-width: 100%; height: auto; border-radius: 4px; }
hr { border: none; border-top: 1px solid #d8d8d8; margin: 14px 0; }
.nightMode hr { border-top-color: #3a3a3a; }
.warn { border-left: 4px solid #d08700; background: #fff8e6; padding: 8px 12px;
        margin: 12px auto; font-size: 16px; border-radius: 3px;
        display: inline-block; text-align: left; max-width: 100%; }
.warn .h { font-weight: 700; color: #8a5a00; }
.nightMode .warn { background: #33290f; border-left-color: #d0a040; }
.nightMode .warn .h { color: #e8bc60; }
.exp { font-size: 17px; color: #444; margin: 10px auto 0;
       display: block; text-align: center; max-width: 100%; }
.nightMode .exp { color: #b8b8b8; }
.src { font-size: 14px; color: #888; margin-top: 6px; text-align: center; }
.ox { font-size: 30px; font-weight: 800; letter-spacing: 6px; margin-top: 12px; }
.slide { margin-top: 16px; border: 1px solid #ddd; display: inline-block;
         line-height: 0; background: #fff; }
.nightMode .slide { border-color: #444; }
.slide img { display: block; }
.fold { margin: 14px auto 0; text-align: center; max-width: 100%; display: block; }
.fold > summary { cursor: pointer; font-size: 15px; color: #6a6a6a; list-style: none;
                  padding: 6px 0; border-top: 1px solid #e2e2e2; user-select: none; }
.fold > summary::before { content: "▸ "; }
.fold[open] > summary::before { content: "▾ "; }
.nightMode .fold > summary { color: #9a9a9a; border-top-color: #3a3a3a; }
.origin { margin-top: 12px; }
.exam { font-size: 15px; color: #555; text-align: center; margin: 10px auto 0;
        white-space: pre-line; }
.exam .h { font-weight: 700; color: #0b5cad; }
.nightMode .exam { color: #b0b0b0; }
.nightMode .exam .h { color: #7ab8f5; }
"""

# 뒷면 공통 꼬리.
#
# 답 바로 아래에 **원본 이미지**가 온다 — 출처 슬라이드, 기출이면 족보 지면. 접지 않는다.
# 답이 맞았는지 확인하는 동작과 원본 맥락을 보는 동작은 사실상 같은 동작이라
# 한 번 더 누르게 만들 이유가 없다.
#
# 글로 된 출처와 해설은 그 아래로 내려 **한 덩어리로** 접는다. 따로 접으면 두 번 눌러야 한다.
# 경고는 접지 않는다 — 자료가 미덥지 않다는 사실은 답과 같이 보여야 한다.
#
# SlideImage 는 원본 이미지, Source 는 출처 한 줄 + 기출 원문 텍스트를 담는다.
# 필드 구성을 바꾸면 이미 임포트한 덱과 어긋나므로 이름은 그대로 두고 내용만 나눴다.
FOLD = ('<details class="fold"><summary>출처 · 해설</summary>'
        '<div class="src">{{Source}}</div>'
        '{{#Explanation}}<div class="exp">{{Explanation}}</div>{{/Explanation}}'
        '</details>')
TAIL = ('{{#SlideImage}}<div class="origin">{{SlideImage}}</div>{{/SlideImage}}'
        '{{#Warning}}<div class="warn">{{Warning}}</div>{{/Warning}}' + FOLD)


def _mid(name: str) -> int:
    """이름에서 안정적인 모델/덱 ID 를 만든다. 다시 빌드해도 같아야 한다."""
    return int(hashlib.sha256(name.encode()).hexdigest()[:8], 16)


FIELDS = [{"name": n} for n in
          ("Question", "Answer", "Explanation", "Warning", "Source", "Image", "SlideImage")]


def _model(name: str, qfmt: str, afmt: str) -> genanki.Model:
    return genanki.Model(_mid(name), name, fields=FIELDS,
                         templates=[{"name": "Card 1", "qfmt": qfmt, "afmt": afmt}], css=CSS)


# 답 앵커. **이것이 뒷면의 스크롤 구조 전부다.**
#
# Anki 는 뒷면을 그린 뒤 `id="answer"` 인 요소를 찾아 그 자리로 스크롤한다. 그래서
# 질문은 화면 위로 밀려나고 답이 맨 위에 서며, 질문을 다시 보려면 위로 올리면 된다.
# 앵커가 없으면 Anki 는 스크롤을 건드리지 않는다 — 뒷면이 맨 위에서 시작해 질문이
# 화면을 차지한 채 답은 그 아래 남는다. 실제로 네 형식 모두 그 상태였다.
#
# 이미지 카드에서는 앵커가 **그림 뒤**에 온다. 그래야 답이 맨 위에 서고, 위로 올리면
# 질문 → 그림 순으로 보인다.
ANCHOR = '<hr id="answer">'

MODELS = {
    "basic": _model("PDF2ANKI Basic",
                    '<div class="q">{{Question}}</div>',
                    '<div class="q">{{Question}}</div>' + ANCHOR +
                    '<div class="a">{{Answer}}</div>' + TAIL),
    "ox": _model("PDF2ANKI OX",
                 '<div class="q">{{Question}}</div><div class="ox">O / X</div>',
                 '<div class="q">{{Question}}</div>' + ANCHOR +
                 '<div class="ox">{{Answer}}</div>' + TAIL),
    # 이미지 카드는 질문이 사진 **위**에 온다. 질문이 비어 있어도 성립한다.
    "image_basic": _model("PDF2ANKI Image",
                          '{{#Question}}<div class="q">{{Question}}</div>{{/Question}}'
                          '<div>{{Image}}</div>',
                          '{{#Question}}<div class="q">{{Question}}</div>{{/Question}}'
                          '<div>{{Image}}</div>' + ANCHOR +
                          '<div class="a">{{Answer}}</div>' + TAIL),
    "image_occlusion": _model("PDF2ANKI Occlusion",
                              '{{#Question}}<div class="q">{{Question}}</div>{{/Question}}'
                              '<div>{{Image}}</div>',
                              '{{#Question}}<div class="q">{{Question}}</div>{{/Question}}'
                              + ANCHOR + '<div>{{Answer}}</div>' + TAIL),
}
CLOZE_MODEL = genanki.Model(
    _mid("PDF2ANKI Cloze"), "PDF2ANKI Cloze",
    fields=[{"name": "Text"}, {"name": "Extra"}, {"name": "Warning"},
            {"name": "Source"}, {"name": "SlideImage"}],
    templates=[{"name": "Cloze",
                "qfmt": '<div class="q">{{cloze:Text}}</div>',
                "afmt": '<div class="q">{{cloze:Text}}</div>'
                        '{{#Warning}}<div class="warn">{{Warning}}</div>{{/Warning}}'
                        '{{#SlideImage}}<div class="origin">{{SlideImage}}</div>'
                        '{{/SlideImage}}'
                        '<details class="fold"><summary>출처 · 해설</summary>'
                        '<div class="src">{{Source}}</div>'
                        '{{#Extra}}<div class="exp">{{Extra}}</div>{{/Extra}}'
                        '</details>'}],
    css=CSS, model_type=genanki.Model.CLOZE)

FLAG_LABEL = {
    "points_at_source": "질문이 원본 자료를 가리킨다",
    "answer_leaked_in_question": "정답 단서가 질문에 노출됐을 수 있다",
    "similar_duplicate": "다른 카드와 회수 방향이 겹칠 수 있다",
    "too_many_items": "한 번에 회수할 항목이 많다",
    "question_too_long": "질문이 길다 — 축을 여럿 물고 있지 않은지 볼 것",
    "too_many_clozes": "가린 곳이 많다",
    "annotation_evidence_without_exam_hit": "필기에만 있는 내용이다 — 강의록으로 확인할 것",
    "ox_is_question_not_statement": "O/X 카드인데 진술문이 아니다",
    "occlusion_answer_leaked_in_question": "가린 라벨이 질문에 그대로 나온다",
    "media_on_text_card": "그림이 붙지 않는 형식인데 media 가 있었다 (제거됨)",
    "exam_hit_on_jokbo": "기출 카드에 exam_hit 이 잘못 붙어 있었다 (제거됨)",
}


class Jokbo:
    """기출 카드의 **원본**을 뒷면에 붙인다.

    강의록 기원 카드는 출처 슬라이드가 원본이지만, 기출 기원 카드는 원본이 족보다.
    붙이지 않으면 선지·이의제기 답변 같은 것을 확인할 길이 카드 안에 없다.
    문항 텍스트(선지·정답·이의제기)와 족보 지면 이미지를 함께 넣는다.
    """

    def __init__(self, slice_path: Path | None, pdf_path: Path | None,
                 lecture_id: str, outdir: Path):
        self.q: dict[tuple[str, str], dict] = {}
        self.doc = None
        self.lecture_id, self.dir, self.files = lecture_id, outdir, {}
        if slice_path and slice_path.exists():
            data = json.loads(slice_path.read_text(encoding="utf-8"))
            self.q = {(str(q["year"]), str(q["no"])): q for q in data["questions"]}
        if pdf_path and Path(pdf_path).exists():
            self.doc = fitz.open(pdf_path)
            self.dir.mkdir(parents=True, exist_ok=True)

    def page(self, no: int) -> str | None:
        if not self.doc or not (1 <= no <= self.doc.page_count):
            return None
        name = f"{self.lecture_id}_jokbo_p{no:03d}.png"
        path = self.dir / name
        if name not in self.files:
            self.doc[no - 1].get_pixmap(matrix=fitz.Matrix(JOKBO_ZOOM, JOKBO_ZOOM),
                                        alpha=False).save(path)
            self.files[name] = path
        return name

    def block(self, ref: dict) -> tuple[str, str]:
        """(기출 원문 텍스트, 족보 지면 이미지). 문항을 못 찾으면 둘 다 빈 문자열.

        텍스트는 접히는 쪽으로, 지면 이미지는 답 바로 아래 보이는 쪽으로 간다.
        """
        q = self.q.get((str(ref["year"]), str(ref["no"])))
        if not q:
            return "", ""
        bits = [f'<span class="h">기출 {ref["year"]}-{ref["no"]} 원문</span>',
                html.escape(q.get("stem") or "")]
        bits += [html.escape(o) for o in (q.get("options") or [])]
        if q.get("answer"):
            bits.append(f'<span class="h">정답</span> {html.escape(str(q["answer"]))}')
        if q.get("objection"):
            bits.append(f'<span class="h">이의제기 답변</span> '
                        f'{html.escape(str(q["objection"]))}')
        text = f'<div class="exam">{"<br>".join(b for b in bits if b)}</div>'
        imgs = ""
        for pno in (q.get("pages") or [])[:2]:
            name = self.page(pno)
            if name:
                imgs += f'<div class="slide"><img src="{name}"></div>'
        return text, imgs


class Media:
    """필요한 크롭과 슬라이드 전체를 그 자리에서 렌더한다."""

    def __init__(self, prep_dir: Path, prep: dict, lecture_id: str, outdir: Path):
        self.ann = fitz.open(prep_dir / prep["annotated_pdf"])
        # 그림 크롭은 clean 에서 뜬다. 필기가 그림을 가리거나 정답(캡션·라벨)을 흘리는
        # 경우가 잦기 때문이다. 좌표는 그대로 쓸 수 있다 — lecture_figures 는 애초에
        # clean 페이지에서 뽑은 것이고(prep.figures_of(cp)), 두 판은 같은 원본의 사본이다.
        self.clean = fitz.open(prep_dir / prep["clean_pdf"])
        if self.clean.page_count != self.ann.page_count:
            raise RuntimeError("clean.pdf 와 annotated.pdf 의 쪽수가 다르다 — prep 을 다시 돌려라")
        self.lecture_id, self.dir = lecture_id, outdir
        self.dir.mkdir(parents=True, exist_ok=True)
        self.figs, self.occs, self.notes_on = {}, {}, {}
        for s in prep["pages"]:
            for f in s["lecture_figures"]:
                self.figs[f["id"]] = (s["slide"], f["bbox"])
            for o in s["occlusion_candidates"]:
                self.occs[o["id"]] = o
            self.notes_on[s["slide"]] = ([n["rect"] for n in s["annotations"]]
                                         + [m["rect"] for m in s["markers"]])
        self.files: dict[str, Path] = {}

    def _save(self, pix, name: str) -> str:
        path = self.dir / f"{self.lecture_id}_{name}.png"
        if name not in self.files:
            pix.save(path)
            self.files[name] = path
        return path.name

    def slide(self, no: int) -> str:
        """카드 뒷면에 붙는 출처 슬라이드 전체(필기 포함)."""
        page = self.ann[no - 1]
        pix = page.get_pixmap(matrix=fitz.Matrix(SLIDE_ZOOM, SLIDE_ZOOM), alpha=False)
        return self._save(pix, f"slide{no:02d}")

    def _crop_rect(self, bbox: list, crop: list | None) -> fitz.Rect:
        r = fitz.Rect(bbox)
        if crop:                              # 그림 기준 비율로 다시 자른다
            w, h = r.width, r.height
            r = fitz.Rect(r.x0 + crop[0] * w, r.y0 + crop[1] * h,
                          r.x0 + crop[2] * w, r.y0 + crop[3] * h)
        return r

    def _render(self, slide: int, rect: fitz.Rect, name: str, masks: list | None = None,
                doc=None) -> str:
        page = (doc or self.ann)[slide - 1]
        clip = (rect + (-CROP_MARGIN, -CROP_MARGIN, CROP_MARGIN, CROP_MARGIN)) & page.rect
        z = RENDER_ZOOM
        pix = page.get_pixmap(matrix=fitz.Matrix(z, z), clip=clip, alpha=False)
        # 클립 렌더한 픽스맵의 좌표계는 0 기준이 아니라 (pix.x, pix.y) 만큼 밀려 있다.
        painted = 0
        for m in masks or []:
            box = fitz.IRect(round((m[0] - 2) * z), round((m[1] - 2) * z),
                             round((m[2] + 2) * z), round((m[3] + 2) * z)) & pix.irect
            if box.is_empty:
                continue
            painted += 1
            pix.set_rect(box, tuple(round(v * 255) for v in MASK_EDGE))
            inner = box + (2, 2, -2, -2)
            if not inner.is_empty:
                pix.set_rect(inner, tuple(round(v * 255) for v in MASK_FILL))
        if masks and painted != len(masks):
            raise RuntimeError(f"{name}: 가림 상자 {len(masks)}개 중 {painted}개만 그려졌다")
        return self._save(pix, name)

    def figure(self, fid: str, crop: list | None = None) -> str:
        """image_basic 앞면. **clean 에서 뜬다** — 필기가 그림을 가리거나 답을 흘린다."""
        slide, bbox = self.figs[fid]
        tag = "" if not crop else "_c" + "-".join(str(round(v, 2)) for v in crop)
        return self._render(slide, self._crop_rect(bbox, crop), f"{fid}{tag}",
                            doc=self.clean)

    def _with_annotations(self, slide: int, rect: fitz.Rect) -> fitz.Rect:
        """그림에 걸친 필기·마커를 **온전히** 품도록 넓힌다.

        그림 bbox 로만 자르면 경계에 걸친 필기가 단어 중간에서 잘린다. 반쯤 잘린
        한국어 구절은 읽히지도 않으면서 시선만 끈다. 오클루전 카드에서 필기 라벨은
        배경이 아니라 내용이다 — 가리는 대상이 그것이고 그림을 설명하는 것도 그것이라,
        도해가 조금 작아지는 값을 치르는 편이 낫다. (실측 1.3~1.7배)
        """
        grown = fitz.Rect(rect)
        for r in self.notes_on.get(slide, []):
            nr = fitz.Rect(r)
            inter = nr & rect
            if inter.is_valid and inter.get_area() > 0:
                grown |= nr
        return grown

    def occlusion(self, fid: str, occ_ids: list[str], crop: list | None = None):
        """오클루전은 **annotated 에서 뜬다.** 가리는 대상이 필기 라벨 자체라,
        clean 으로 뜨면 라벨이 사라져 빈 자리를 가리게 된다."""
        slide, bbox = self.figs[fid]
        rect = self._crop_rect(bbox, crop)
        # crop 은 모델이 정답이 새는 구간을 일부러 도려낸 것이다. 넓히면 그걸 되돌릴
        # 수 있으므로, crop 이 지정된 경우에는 넓히지 않는다.
        if not crop:
            rect = self._with_annotations(slide, rect)
        masks = [self.occs[o]["label_rect"] for o in occ_ids]
        key = "-".join(o.replace("occ_", "") for o in occ_ids)
        return (self._render(slide, rect, f"{fid}_{key}_front", masks=masks),
                self._render(slide, rect, f"{fid}_{key}_back"))


RE_BULLET = re.compile(r"^(\s*)[-•*]\s+(.*)$")


def render_answer(a: str) -> str:
    """답을 HTML 로 만든다. `- ` 로 시작하는 줄이 둘 이상이면 목록으로 낸다.

    `white-space: pre-line` 은 줄바꿈은 살리지만 **선행 공백을 뭉갠다.** 그리고 한 항목이
    한 줄을 넘기면 둘째 줄이 왼쪽 끝으로 돌아와 항목 경계가 무너진다. `<ul>` 로 내면
    걸린 들여쓰기가 유지돼 긴 항목도 한눈에 갈린다.

    한 단계 중첩까지 본다. 목록 앞뒤에 붙은 머리말·꼬리말은 그대로 문단으로 둔다.
    """
    lines = a.strip().splitlines()
    marks = [RE_BULLET.match(ln) for ln in lines]
    if sum(1 for m in marks if m) < 2:
        return html.escape(a)

    base = min(len(m.group(1)) for m in marks if m)
    out, in_list, in_sub = [], False, False
    for ln, m in zip(lines, marks):
        if not m:
            text = ln.strip()
            if not text:
                continue
            if in_sub:
                out.append("</ul>")
                in_sub = False
            if in_list:
                out.append("</ul>")
                in_list = False
            out.append(f'<div class="lead">{html.escape(text)}</div>')
            continue
        if not in_list:
            out.append("<ul>")
            in_list = True
        if len(m.group(1)) > base and not in_sub:
            out.append("<ul>")
            in_sub = True
        elif len(m.group(1)) <= base and in_sub:
            out.append("</ul>")
            in_sub = False
        out.append(f"<li>{html.escape(m.group(2).strip())}</li>")
    out += ["</ul>"] * (in_sub + in_list)
    return "".join(out)


def layer_of(c: dict) -> str:
    if c["source_type"] == "jokbo" or c.get("exam_hit"):
        return "1-기출직결"
    return "2-핵심" if c["importance"] == "core" else "3-세부"


def tags_of(c: dict, lecture_id: str) -> list[str]:
    t = [f"강의::{lecture_id}", f"층::{layer_of(c)}", f"형식::{c['card_format']}",
         f"유형::{c['card_type']}", f"중요도::{c['importance']}", f"출처::{c['source_type']}"]
    if c.get("slide_no"):
        t.append(f"슬라이드::{c['slide_no']:02d}")
    if c.get("exam_hit"):
        t.append("기출적중")
    if c.get("jokbo_ref"):
        t.append(f"기출::{c['jokbo_ref']['year']}-{c['jokbo_ref']['no']}")
    if c.get("review_flags"):
        t.append("검토필요")
    r = c.get("reproduce") or {}
    if r.get("verdict"):
        t.append(f"재현::{r['verdict']}")
    elif r.get("status") == "skipped":
        t.append("재현::그림카드제외")
    return t


def warning_of(c: dict) -> str:
    parts = []
    if c.get("review_note"):
        parts.append(f'<span class="h">족보 검토</span><br>{html.escape(c["review_note"])}')
    flags = [FLAG_LABEL[f] for f in c.get("review_flags", []) if f in FLAG_LABEL]
    if flags:
        parts.append('<span class="h">자료 주의</span><br>' + " · ".join(flags))
    return "<br><br>".join(parts)


def source_of(c: dict, title: str) -> str:
    bits = [title]
    if c.get("slide_no"):
        bits.append(f"Slide {c['slide_no']}")
    if c.get("jokbo_ref"):
        r = c["jokbo_ref"]
        bits.append(f"기출 {r['year']}-{r['no']}"
                    + ("" if r.get("role") == "source" else " (출제 근거)"))
    return html.escape(" · ".join(bits))


def pick_input(prep_dir: Path, skip_reproduce: bool) -> tuple[Path, str]:
    """어느 카드 파일로 빌드할지 정한다. 재현 검사를 건너뛴 경우를 조용히 넘기지 않는다."""
    done = prep_dir / "items.reproduced.json"
    if done.exists():
        return done, "재현 검사 반영"
    if skip_reproduce:
        return prep_dir / "items.checked.json", "⚠ 재현 검사 건너뜀 (--skip-reproduce)"
    raise FileNotFoundError(done)


IMAGE_FORMATS = ("image_basic", "image_occlusion")


def guid_of(seed: str, qkey: str, c: dict) -> str:
    """노트 guid. 씨앗은 `(강의 ID, 질문)` 이고 **이미지 카드는 그림까지 넣는다.**

    질문이 그림을 가리키는 카드는 문장이 같아도 서로 다른 카드다 —
    「이 육안 소견은 어떤 종류의 경색인가」가 적색 경색 한 장, 백색 경색 한 장으로 나온다.
    그림을 씨앗에 안 넣으면 두 장의 guid 가 같아지고, Anki 는 나중 것을 **기존 노트의
    수정**으로 처리한다. 한 장이 조용히 사라진다. 28강에서 4장이 그러고 있었다
    (충수돌기/담낭 · 태아 폐 18주/23주 · 적색/백색 경색 · 침윤/핵다형성).

    그림이 없는 카드에는 **아무것도 덧붙이지 않는다.** 빈 문자열이라도 붙이면 해시가
    달라져 텍스트 카드 전부의 guid 가 바뀐다 — `guid_for` 는 인자를 `__` 로 잇는다.

    씨앗에 넣는 것은 렌더된 파일명을 결정하는 값과 같다 (그림 ID · 가림 상자 · 크롭).
    같은 그림을 같은 크롭으로 두 번 물으면 그건 실제로 같은 카드다.
    """
    parts = [seed, qkey]
    m = c.get("media") or {}
    if c.get("card_format") in IMAGE_FORMATS and m:
        tag = [str(m.get("figure_id") or "")]
        if m.get("occlusion_ids"):
            tag += sorted(m["occlusion_ids"])
        if m.get("crop"):
            tag.append("-".join(str(round(v, 3)) for v in m["crop"]))
        parts.append("|".join(tag))
    return genanki.guid_for(*parts)


class GuidClash(RuntimeError):
    """guid 가 겹치는데 내용이 다르다. 그대로 두면 한 장이 사라진다."""


def _identity(c: dict) -> str:
    return json.dumps([c.get("q"), c.get("a"), c.get("card_format"), c.get("media")],
                      ensure_ascii=False, sort_keys=True)


def check_guids(cards: list[dict], seed: str, qkey=norm_key) -> tuple[list[dict], int]:
    """guid 가 겹치는 카드를 **덱을 만들기 전에** 잡는다.

    Anki 는 guid 로 노트의 정체를 잡아, 같은 guid 의 두 번째 노트를 **기존 노트의
    수정**으로 처리한다. 그래서 겹치면 한 장이 조용히 사라진다. 덱에서는 카드 수가
    하나 모자란 것으로만 드러나고, 세지 않으면 아무도 모른다 — 28강에서 4장이 그렇게
    사라지고 있었고 `bundle.py` 로 한데 담다가 겨우 잡혔다.

    씨앗을 아무리 촘촘히 해도 **겹칠 수 있는 카드는 언제든 나온다.** 씨앗을 늘리는 것과
    별개로, 겹쳤을 때 조용하지 않게 하는 것이 이 함수의 일이다.

    질문·답·형식·그림까지 같으면 그건 정말 중복이라 접는다(세어서 보고한다).
    하나라도 다르면 **덱을 만들지 않는다** — 어느 쪽을 버릴지는 코드가 정할 일이 아니다.
    """
    order: dict[str, list[dict]] = {}
    for c in cards:
        order.setdefault(guid_of(seed, qkey(c["q"]), c), []).append(c)

    folded, bad = 0, []
    for g, group in order.items():
        if len(group) == 1:
            continue
        if len({_identity(c) for c in group}) == 1:
            folded += len(group) - 1
        else:
            bad.append((g, group))

    if bad:
        lines = [f"guid 가 겹치는데 내용이 다른 카드 {len(bad)}쌍이 있다. "
                 "그대로 덱을 만들면 한 장이 조용히 사라진다."]
        for g, group in bad[:6]:
            lines.append(f"  [{g}] {group[0]['q'][:60]}")
            for c in group:
                m = c.get("media") or {}
                lines.append(f"     - {c['card_format']} · 그림 {m.get('figure_id') or '없음'}"
                             f" · 답 {str(c.get('a'))[:44]}")
        lines.append("  질문을 갈라 쓰거나 한쪽을 지워라 (②부터 다시 돌린다).")
        raise GuidClash("\n".join(lines))

    return [g[0] for g in order.values()], folded


def reproduce_gate(cards: list[dict]) -> tuple[Counter, list[dict]]:
    """재현 결과를 세고, 결함으로 갈린 카드를 골라낸다."""
    tally = Counter()
    for c in cards:
        r = c.get("reproduce") or {}
        tally[r.get("verdict") or r.get("status") or "not_run"] += 1
    bad = [c for c in cards if (c.get("reproduce") or {}).get("reason") in DEFECT_REASONS]
    return tally, bad


def build(prep_dir: Path, deck_name: str, lecture_id: str,
          src: Path | None = None, jokbo_slice: Path | None = None,
          jokbo_pdf: Path | None = None) -> dict:
    prep = json.loads((prep_dir / "prep.json").read_text(encoding="utf-8"))
    src = src or (prep_dir / "items.checked.json")
    cards = json.loads(src.read_text(encoding="utf-8"))["cards"]
    cards, folded = check_guids(cards, lecture_id)
    if folded:
        print(f"  같은 카드 {folded}장을 접었다 (질문·답·그림이 전부 같다)")
    title = deck_name.split("::")[-1]
    media = Media(prep_dir, prep, lecture_id, prep_dir / "media")
    jokbo = Jokbo(jokbo_slice, jokbo_pdf, lecture_id, prep_dir / "media")

    # 강의록 기원과 기출 기원을 하위 덱으로 나눈다
    decks = {k: genanki.Deck(_mid(f"{deck_name}::{v}"), f"{deck_name}::{v}")
             for k, v in (("lecture", "강의록"), ("jokbo", "기출"))}
    stats = Counter()

    for c in cards:
        fmt, src = c["card_format"], c["source_type"]
        guid = guid_of(lecture_id, norm_key(c["q"]), c)
        warn, srctxt, tags = warning_of(c), source_of(c, title), tags_of(c, lecture_id)
        exp = html.escape(c.get("explanation") or "").replace("\n", "<br>")
        # 원본 이미지는 답 바로 아래 보이고, 기출 원문 텍스트는 출처와 함께 접힌다.
        origin = (f'<div class="slide"><img src="{media.slide(c["slide_no"])}"></div>'
                  if c.get("slide_no") else "")
        if c.get("jokbo_ref"):
            exam_text, exam_imgs = jokbo.block(c["jokbo_ref"])
            origin += exam_imgs
            srctxt += exam_text
            stats["기출원문:" + ("붙임" if exam_text else "못찾음")] += 1
        m = c.get("media") or {}
        crop = m.get("crop")

        if fmt == "cloze":
            note = genanki.Note(model=CLOZE_MODEL, guid=guid, tags=tags,
                                fields=[c["q"], exp, warn, srctxt, origin])
        else:
            img, answer = "", render_answer(c["a"])
            if fmt == "image_basic":
                img = f'<img src="{media.figure(m["figure_id"], crop)}">'
            elif fmt == "image_occlusion":
                front, back = media.occlusion(m["figure_id"], m["occlusion_ids"], crop)
                img, answer = f'<img src="{front}">', f'<img src="{back}">'
            note = genanki.Note(model=MODELS[fmt], guid=guid, tags=tags,
                                fields=[html.escape(c["q"]), answer, exp, warn,
                                        srctxt, img, origin])
        decks[src].add_note(note)
        stats[fmt] += 1
        stats["deck:" + src] += 1
        stats["layer:" + layer_of(c)] += 1

    contact = contact_sheet(prep_dir, cards, media, lecture_id)
    apkg = prep_dir / f"{lecture_id}.apkg"
    pkg = genanki.Package([d for d in decks.values() if d.notes])
    pkg.media_files = [str(p) for p in media.files.values()] +                       [str(p) for p in jokbo.files.values()]
    pkg.write_to_file(apkg)
    return {"apkg": apkg, "n_notes": len(cards),
            "n_media": len(media.files) + len(jokbo.files),
            "stats": dict(stats), "contact": contact}


def contact_sheet(prep_dir: Path, cards: list, media: Media, lecture_id: str) -> Path | None:
    """이미지 카드의 앞·뒤를 나란히 놓은 검수용 PDF.

    가장 중요한 확인은 **앞면 크롭 안에 정답이 인쇄돼 있는지**다.
    필기자가 슬라이드를 통째로 붙였다면 캡션이 곧 정답이며, 픽셀이라 코드로는 못 잡는다.
    """
    img_cards = [c for c in cards if c["card_format"] in ("image_basic", "image_occlusion")]
    if not img_cards:
        return None
    W, H, PAD, TOP = 1400, 640, 12, 86
    doc = fitz.open()
    for i, c in enumerate(img_cards, 1):
        m = c["media"]
        crop = m.get("crop")
        if c["card_format"] == "image_occlusion":
            key = "-".join(o.replace("occ_", "") for o in m["occlusion_ids"])
            names = [f"{m['figure_id']}_{key}_front", f"{m['figure_id']}_{key}_back"]
            caps = ("앞면 (가림)", "뒷면 (공개)")
        else:
            tag = "" if not crop else "_c" + "-".join(str(round(v, 2)) for v in crop)
            names = [f"{m['figure_id']}{tag}"]
            caps = ("앞면 (크롭)",)
        page = doc.new_page(width=W, height=H)
        page.insert_textbox(
            fitz.Rect(PAD, 8, W - PAD, TOP - 6),
            f"{i}. [{c['card_format']}] Slide {c['slide_no']} · {m['figure_id']}"
            f"{' · crop ' + str(crop) if crop else ''}\nQ. {c['q']}\nA. {c['a']}",
            fontsize=11, fontname="korea")
        span = (W - PAD * (len(names) + 1)) / len(names)
        for j, nm in enumerate(names):
            box = fitz.Rect(PAD + j * (span + PAD), TOP,
                            PAD + j * (span + PAD) + span, H - PAD)
            page.insert_image(box, filename=str(media.dir / f"{lecture_id}_{nm}.png"),
                              keep_proportion=True)
            page.draw_rect(box, color=(0.7, 0.7, 0.7), width=0.5)
    out = prep_dir / f"{lecture_id}_image_check.pdf"
    doc.save(out)
    doc.close()
    return out


def counts(apkg: Path) -> dict:
    """.apkg 를 다시 열어 **실제로 든 것**을 센다. 기대값을 받지 않는다.

    `verify` 에서 떼어낸 이유는 세는 자리와 판정하는 자리가 다르기 때문이다.
    배포 직전 검문(`studyez.gate`)은 빌드가 끝난 한참 뒤에 파일만 보고 다시 세야
    하는데, 그때는 기대값이 손에 없고 오히려 **덱이 스스로 주장하는 수와 어긋나는지**
    가 알고 싶은 것이다.
    """
    with zipfile.ZipFile(apkg) as z:
        names = set(z.namelist())
        db = next((n for n in ("collection.anki2", "collection.anki21") if n in names), None)
        if db is None:
            return {"db": False}
        media_map = json.loads(z.read("media").decode("utf-8")) if "media" in names else {}
        blobs = {n for n in names if n.isdigit()}
        with tempfile.TemporaryDirectory() as td:
            z.extract(db, td)
            con = sqlite3.connect(Path(td) / db)
            n_notes = con.execute("SELECT count(*) FROM notes").fetchone()[0]
            n_cards = con.execute("SELECT count(*) FROM cards").fetchone()[0]
            n_decks = con.execute("SELECT count(*) FROM cards GROUP BY did").fetchall()
            refs = con.execute("SELECT flds FROM notes").fetchall()
            con.close()
    packaged = set(media_map.values())
    missing = sorted({m for (f,) in refs for m in re.findall(r'<img src="([^"]+)"', f)
                      if m not in packaged})
    return {"db": True, "n_notes": n_notes, "n_cards": n_cards,
            "n_media": len(media_map), "n_blobs": len(blobs), "n_decks": len(n_decks),
            "missing_media": missing}


def verify(apkg: Path, expect_notes: int, expect_media: int) -> dict:
    """생성기가 성공을 반환했다는 것과 별개로 .apkg 를 다시 열어 대조한다."""
    got = counts(apkg)
    if not got["db"]:
        return {"ok": False, "problems": ["패키지에 collection DB 가 없다"]}

    problems = []
    if got["n_notes"] != expect_notes:
        problems.append(f"노트 수 불일치: 기대 {expect_notes}, 실제 {got['n_notes']}")
    if got["n_media"] != expect_media:
        problems.append(f"미디어 항목 수 불일치: 기대 {expect_media}, 실제 {got['n_media']}")
    if got["n_blobs"] != got["n_media"]:
        problems.append(f"미디어 파일 수 불일치: 목록 {got['n_media']}, 실파일 {got['n_blobs']}")
    if got["missing_media"]:
        problems.append(f"본문이 참조하는데 패키지에 없는 이미지: {got['missing_media'][:5]}")
    return {"ok": not problems, "problems": problems, "n_notes": got["n_notes"],
            "n_cards": got["n_cards"], "n_media": got["n_media"], "n_decks": got["n_decks"]}


def find_jokbo_source(prep_dir: Path, jokbo_dir: Path, slice_arg: str | None,
                      pdf_arg: str | None) -> tuple[Path | None, Path | None]:
    """이 강의에 물린 족보 조각과 원본 PDF 를 찾는다.

    조각은 assemble 이 쓰는 규칙(목차 제목 대조)을 그대로 다시 쓴다 —
    카드를 만들 때 본 조각과 붙이는 조각이 달라지면 안 되기 때문이다.
    """
    from .assemble import find_jokbo

    slice_path = Path(slice_arg) if slice_arg else None
    if slice_path is None and (jokbo_dir / "index.json").exists():
        prep = json.loads((prep_dir / "prep.json").read_text(encoding="utf-8"))
        slice_path, score, _ = find_jokbo(prep, jokbo_dir)
        if score < 0.2:
            slice_path = None

    pdf_path = Path(pdf_arg) if pdf_arg else None
    if pdf_path is None and (jokbo_dir / "index.json").exists():
        name = json.loads((jokbo_dir / "index.json").read_text(encoding="utf-8")).get("source")
        if name:
            hits = [q for q in Path(".").rglob(name) if q.is_file()]
            pdf_path = hits[0] if hits else None
    return slice_path, (pdf_path if pdf_path and pdf_path.exists() else None)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="검증된 카드를 .apkg 로 만든다")
    ap.add_argument("prep_dir")
    ap.add_argument("--deck", required=True, help='덱 이름. "과목::강의" 형태 권장')
    ap.add_argument("--id", help="강의 ID (태그·파일명·guid). 기본은 덱 이름 끝마디")
    ap.add_argument("--skip-reproduce", action="store_true",
                    help="재현 검사 없이 items.checked.json 으로 빌드한다")
    ap.add_argument("--allow-defects", action="store_true",
                    help="재현 불가로 갈린 카드를 그대로 덱에 넣는다")
    ap.add_argument("--jokbo", help="족보 조각 json. 생략하면 assemble 과 같은 규칙으로 찾는다")
    ap.add_argument("--jokbo-dir", default="out/jokbo")
    ap.add_argument("--jokbo-pdf", help="족보 원본 PDF. 생략하면 index.json 의 이름으로 찾는다")
    args = ap.parse_args(argv)

    prep_dir = Path(args.prep_dir)
    lecture_id = args.id or re.sub(r"[^0-9A-Za-z가-힣]+", "-",
                                   args.deck.split("::")[-1]).strip("-")
    try:
        src, how = pick_input(prep_dir, args.skip_reproduce)
    except FileNotFoundError as e:
        print(f"{e} 가 없다 — 재현 검사를 아직 돌리지 않았다.")
        print(f"   python -m pdf2anki.reproduce check {prep_dir.as_posix()}")
        print("   검사 없이 만들려면 --skip-reproduce (권장하지 않는다)")
        return 1

    cards = json.loads(src.read_text(encoding="utf-8"))["cards"]
    tally, bad = reproduce_gate(cards)
    print(f"입력 {src.name} — {how}")
    if not args.skip_reproduce:
        print(f"  재현 { {k: v for k, v in tally.items()} }")
    if bad and not args.allow_defects:
        print(f"\n재현 불가 {len(bad)}장이 남아 있어 덱을 만들지 않는다. "
              "질문을 고치고 ②부터 다시 돌리거나, --allow-defects 로 강행해라.")
        for c in bad[:12]:
            r = c["reproduce"]
            print(f"   [{r['reason']}] {c['q'][:64]}")
        return 1
    if bad:
        print(f"⚠ 재현 불가 {len(bad)}장을 그대로 넣는다 (--allow-defects)")

    jslice, jpdf = find_jokbo_source(prep_dir, Path(args.jokbo_dir),
                                     args.jokbo, args.jokbo_pdf)
    print(f"기출 원본: {jslice.name if jslice else '조각 없음'}"
          f" · {jpdf.name if jpdf else 'PDF 없음 (지면 이미지 생략)'}")

    try:
        res = build(prep_dir, args.deck, lecture_id, src=src,
                    jokbo_slice=jslice, jokbo_pdf=jpdf)
    except GuidClash as e:
        print(f"\n{e}")
        return 1
    chk = verify(res["apkg"], res["n_notes"], res["n_media"])
    s = res["stats"]
    print(f"덱: {args.deck}   (강의 ID {lecture_id})")
    print(f"  하위덱 강의록 {s.get('deck:lecture', 0)}장 · 기출 {s.get('deck:jokbo', 0)}장")
    print(f"노트 {res['n_notes']}장 · 미디어 {res['n_media']}개 → {res['apkg']}")
    print(f"형식 { {k: v for k, v in s.items() if ':' not in k} }")
    print(f"층   { {k[6:]: v for k, v in s.items() if k.startswith('layer:')} }")
    if res["contact"]:
        print(f"\n⚠ 이미지 카드 검수: {res['contact']}")
        print("   **앞면 크롭 안에 정답이 인쇄돼 있는지**를 반드시 눈으로 확인할 것")
    print()
    if chk["ok"]:
        print(f"APKG 재개봉 검증 통과 — 하위덱 {chk['n_decks']}개 · 노트 {chk['n_notes']} "
              f"· 카드 {chk['n_cards']} · 미디어 {chk['n_media']}")
        return 0
    print("APKG 재개봉 검증 실패:")
    for p in chk["problems"]:
        print(f"   {p}")
    return 1


if __name__ == "__main__":
    sys.exit(main())

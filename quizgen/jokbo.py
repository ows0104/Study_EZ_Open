"""족보 PDF 사전 절단기.

과목 전체 족보 PDF 한 개를 받아서 강의별 조각으로 미리 잘라 둔다.
강의마다 다시 돌릴 필요 없이 과목당 한 번만 실행한다.

코드가 책임지는 것: 구역 분리, 섹션/연도/문항 경계, 정답 결합, 이의제기 결합,
                    그림 첨부, 교수 표 파싱, 문항 반복률 계산.
모델이 책임지는 것: 이 조각들 중 무엇이 이번 강의 소관인지, 무엇을 카드로 낼지.

사용:
    python -m quizgen.jokbo "족보_예시/2026 질병의 병리학적 이해 족보.pdf" -o out/jokbo
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

import fitz

from . import cutmark
from .textutil import norm_key as norm
from .textutil import word_tokens

# ─────────────────────────────────────────────────────────────── 정규식/상수

CIRCLED = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮"
# 연도 머리글. **한 해에 시험이 둘이면 `2016-1` · `2016-2` 로 적는다** — 약리학·기생충학
# 2020판이 그렇다. 맨 `2016` 만 받던 동안 두 회차의 문항이 앞 머리글(2017)에 붙어
# 약리학 2020판의 「2017」이 310문항(다른 해 100 안팎)이었고, 정답도 같은 열쇠
# (2017, 번호)로 들어가 번호가 겹치는 20개는 서로 덮였다(2026-10-05).
RE_YEAR = re.compile(r"^\s*(19|20)\d{2}(\s*-\s*\d)?\s*$")


def year_key(text: str) -> str:
    """머리글을 회차 이름으로. `2016 - 1` → `2016-1`. 실습 족보의 회차 이름과 같은 꼴이다."""
    return re.sub(r"\s", "", text)


def yy(year: str) -> str:
    """교수 표의 열 이름. `2016-1` 도 `16` 열을 본다 — 표는 회차를 가르지 않는다."""
    return year[2:4]


def year_professors(cells: dict, year: str) -> list[str]:
    """회차별 열이 있으면 그 열을 우선하고, 연도만 있는 표는 연도 열로 조회한다."""
    short = year_key(year)[2:] if len(year_key(year)) >= 4 else year_key(year)
    if short in cells:
        return cells[short] or []
    base = short[:2]
    if base in cells:
        return cells[base] or []
    # 회차를 모르는 문항에는 여러 회차의 교수가 모두 같은 경우만 적용한다.
    if "-" not in short:
        sittings = [v for k, v in cells.items() if k.startswith(base + "-")]
        if sittings and all(set(v) == set(sittings[0]) for v in sittings):
            return sittings[0]
    return []


RE_QSTART = re.compile(r"^\s*(R?\d{1,3})\s*\.\s*(\S.*)$")
RE_ANSWER = re.compile(r"^\s*(R?\d{1,3})\s*\.\s*([\d]+(?:\s*,\s*\d+)*)\s*$")
RE_OPTION = re.compile(rf"^\s*([{CIRCLED}])\s*(.*)$")
RE_OBJECTION = re.compile(r"\[?\s*(R?\d{1,3})\s*번?\s*이의제기\s*\]?")
RE_TOC_NOTE = re.compile(r"\s*\((?:변경|신설|폐지|추가)\)\s*$")
RE_BARE_NUM = re.compile(r"^\s*(\d{1,3}(?:\s*-\s*\d{1,3})?)\s*$")
# 이 기출이 **그림을 보고 푸는 문항인가.** 실습 족보는 거의 전부가 그렇다.
#
# **이 정규식이 판정을 가르는 자리는 하나뿐이다** — 조각에서 그림을 못 찾은
# 문항(`needs_figure = bool(figures) or 이 정규식`). 그림이 붙었으면 이미 True 다.
# 그래서 「전체 몇 %를 맞히는가」는 이 규칙을 재는 자가 아니다.
#
# 2026-09-14 에 잰 값이다. 실습 족보 277문항 중 조각에 그림이 없는 것이 40개고,
# 그중 **29개는 사실 그림 문항**이었다(땡시가 같은 족보에서 그 사진을 찾아 뒀다).
#
#     놓친 그림 29개 중 알아본 것        옛 2개  →  새 26개
#     땡시도 사진이 없는 11개 중 헛침     옛 0개  →  새 3개
#     needs_figure 합계 (277문항)       옛 239  →  새 266
#
# 옛 규칙이 「그림·사진·현미경」 같은 **낱말만** 찾았기 때문이다. 실습 문항은
# 대개 그 말을 안 쓰고 **가리키기만 한다** —
#
#     다음충란을가지는기생충은?        다음원충의발육단계는?
#     indicator가 가리키는 기관은?     화살표로 표시된 구조물은?
#     관찰되는 원충의 이름?            잉어를 먹고 감염된 환자에서 검출된 …
#
# **헛치는 3건은 눈으로 보면 전부 그림 문항이다**(「다음 기생충에서 볼 수 있는
# 구조물은?」·「관찰되는 원충의 발육 단계는?」). 땡시 쪽이 그 사진을 못 붙인
# 것이라 실제로 헛친 것은 아마 없다. 남은 3개는 「…충체이다」처럼 지문이 잘렸다.
#
# 잰 자가 땡시의 사진 유무라는 것이 이 값의 한계다. **그쪽도 완전하지 않다.**
# `docs/archive/refactor-plan.md` Phase 3 ① 의 산출물이고, 거기 표가 더 있다.
#
# 읽는 쪽은 `quizgen/validate.py` 의 `jokbo_figure_dropped` 하나이고 **세기만
# 한다.** 그래서 이 값을 고치면 그 표시가 실습 편에서 는다 — 늘어난 것이
# 새 결함이 아니라 **원래 있었는데 안 세어지던 것**이다.
RE_FIGURE_WORD = re.compile(
    r"그림|사진|이미지|소견|모식도|도식|현미경"          # 그림이라고 말하는 것
    r"|다음|indicator|화살표|표본"                      # 가리키는 것
    r"|위\s*의?\s*(?:기생충|충란|충체|원충|사진)"
    r"|관찰|검출|적출|발견",                            # 「…에서 나온 것이다」
    re.I,
)
# 공용 답가지 묶음의 머리글: "[문항 7,8] 아래 답가지(1-15) 중에서 …", "[42-43] 아래 답가지(1-10)는 …"
RE_BANK_HEAD = re.compile(r"^\s*\[\s*(?:문항\s*)?(\d{1,3}(?:\s*[,·]\s*\d{1,3})*|\d{1,3}\s*[-~–]\s*\d{1,3})\s*\]")
RE_BANK_SPAN = re.compile(r"답가지\s*\(?\s*(\d{1,3})\s*[-~–]\s*(\d{1,3})\s*\)?")
MAX_BANK_SPAN = 12        # "[42-45]" 처럼 범위로 적힌 문항 번호를 펼칠 상한

# 2단 조판 경계 (A4 595pt 기준, 실측 x0 군집 80 / 300)
COLUMN_SPLIT_RATIO = 0.5


# ─────────────────────────────────────────────────────────────── 자료 구조


@dataclass
class Question:
    year: str
    no: str
    stem: str = ""
    options: list[str] = field(default_factory=list)
    answer: str | None = None
    objection: str | None = None
    pages: list[int] = field(default_factory=list)      # 1-based
    figures: list[dict] = field(default_factory=list)   # {page, bbox}
    needs_figure: bool = False
    grouped: bool = False       # 답가지가 문항 밖에 한 번만 인쇄된 연결형
    # `pages`가 가리키는 PDF. None이면 과목 족보 원본(`index.source_path`)이고,
    # 정수면 조각의 `sources[src]`다 — 실습 족보는 파일이 여럿이라 문항마다 다르다.
    src: int | None = None
    # 이 문항을 낸 교수. None 이면 조각의 `professors_by_year` 에서 그 해 칸을 본다.
    # 옛 판에서 덧붙인 문항만 든다 — 옛 판의 섹션이 이번 판의 다른 섹션에 흡수되면
    # (2020판 `세포의 손상 (3)~(4)` → 2026판 `2-3`) 그 해 칸의 교수가 이 문항의 것이 아니다.
    by: list[str] | None = None
    # 올해 교수가 낸 해가 아니다 — 조각 뒤 「참고」로 간다(`split_by_professor`)
    reference: bool | None = None
    # 파싱 중에만 쓰는 작업 영역 (finalize에서 stem/options로 접힌다)
    body: list[dict] = field(default_factory=list, repr=False)
    span: list[tuple] = field(default_factory=list, repr=False)
    bank: list[str] = field(default_factory=list, repr=False)   # 묶음이 공유하는 답가지

    @property
    def key(self) -> tuple[str, str]:
        return (self.year, self.no)

    def finalize(self) -> None:
        """줄 조각 목록을 stem과 options로 접는다."""
        for item in self.body:
            if item["kind"] == "option":
                self.options.append(item["text"])
            elif self.options:
                self.options[-1] += " " + item["text"]
            else:
                self.stem += (" " if self.stem else "") + item["text"]
        self.stem = re.sub(r"\s+", " ", self.stem).strip()
        self.options = [re.sub(r"\s+", " ", o).strip() for o in self.options]
        if self.bank and not self.options:
            # 연결형은 보기가 문항 안에 없다. 묶음이 공유하는 답가지를 여기서 붙인다.
            self.options = [re.sub(r"\s+", " ", o).strip() for o in self.bank]
        self.body, self.bank = [], []


@dataclass
class Section:
    lecture_key: str                 # 목차의 번호 표기 ("16-18", "7")
    title: str
    questions: list[Question] = field(default_factory=list)
    # 본문에 헤더가 없어 이 조각에 섞여 들어왔을 수 있는 강의들
    may_contain: list = field(default_factory=list)


# ─────────────────────────────────────────────────────────────── 저수준 추출


def page_lines(page: fitz.Page) -> list[dict]:
    """줄 목록을 원본 읽기 순서 그대로 낸다.

    이 문서는 2단 조판이지만 PyMuPDF의 블록 순서가 이미 단 순서를 지킨다.
    직접 (단, y)로 다시 정렬하면 두 단에 걸친 전폭 섹션 제목이 쪼개지므로
    재정렬하지 않는다. `col`은 그림 첨부용 보조 정보로만 쓴다.
    """
    split_x = page.rect.width * COLUMN_SPLIT_RATIO
    out = []
    for blk in page.get_text("dict")["blocks"]:
        if blk["type"] != 0:
            continue
        for ln in blk["lines"]:
            text = "".join(sp["text"] for sp in ln["spans"])
            if not text.strip():
                continue
            x0, y0, x1, y1 = ln["bbox"]
            spans_cols = x0 < split_x < x1
            out.append({"col": None if spans_cols else (0 if x0 < split_x else 1),
                        "y0": y0, "y1": y1, "text": text})
    return out


def page_images(page: fitz.Page) -> list[dict]:
    split_x = page.rect.width * COLUMN_SPLIT_RATIO
    out = []
    for blk in page.get_text("dict")["blocks"]:
        if blk["type"] != 1:
            continue
        x0, y0, x1, y1 = blk["bbox"]
        if (x1 - x0) < 40 or (y1 - y0) < 40:      # 장식용 세선 제외
            continue
        out.append({"col": 0 if x0 < split_x else 1, "y0": y0, "y1": y1,
                    "bbox": [round(v, 1) for v in blk["bbox"]]})
    return out


# ─────────────────────────────────────────────────────────────── 구역 분리


# 실습 구역이 시작하는 본문 표제. `2025 기생충학 실습시험` 같은 짧은 줄이다.
# **`★` 로 시작하는 것은 아니다** — 그건 필기 구역 안의 자리표시이고(기생충학 p48
# `★ 기생충학 실습시험` + "실습시험은 드라이브를 참고 바랍니다"), 거기서 자르면
# 필기 문항 절반이 실습으로 넘어간다.
RE_PRACTICAL_HEAD = re.compile(r"^(?!★).{0,14}실습\s*시험$")


def split_regions(doc: fitz.Document) -> dict[str, list[int]]:
    """페이지 머리글과 정답행 밀도로 네 구역을 가른다. 값은 0-based 페이지 목록."""
    practical, written = [], []
    for i in range(doc.page_count):
        head = (doc[i].get_text().split("\n") or [""])[0]
        (practical if "실습" in head else written).append(i)

    # **머리글이 안 갈라 주는 족보가 있다.** 병리학은 실습 쪽 머리글이 통째로
    # 다르지만(`질병의 병리학적 이해 실습 2026 족보`), 기생충학 2026 은 70쪽 전부가
    # 같은 머리글이고 실습은 본문 표제로만 시작한다(p60). 그대로 두면 실습 문항
    # 9쪽·정답 2쪽이 「필기정답」으로 삼켜져 실습 카드가 한 장도 안 나온다 —
    # 2026-08-30 에 실제로 "실습문항 없음" 으로 찍고 넘어갔다.
    if not practical:
        for i in written:
            if any(RE_PRACTICAL_HEAD.match(d["text"].strip()) for d in page_lines(doc[i])):
                practical = [p for p in written if p >= i]
                written = [p for p in written if p < i]
                break

    def cut(pages: list[int]) -> tuple[list[int], list[int]]:
        """문항 구역과 정답 구역의 경계를 찾는다. 정답 구역은 끝까지 이어진다."""
        first_ans = None
        for i in pages:
            lines = [d["text"] for d in page_lines(doc[i])]
            n_ans = sum(1 for t in lines if RE_ANSWER.match(t))
            n_q = sum(1 for t in lines if RE_QSTART.match(t) and not RE_ANSWER.match(t))
            if n_ans >= 5 and n_ans > n_q * 2:
                first_ans = i
                break
        if first_ans is None:
            return pages, []
        return [p for p in pages if p < first_ans], [p for p in pages if p >= first_ans]

    wq, wa = cut(written)
    pq, pa = cut(practical)
    # 목차/표지는 문항 구역에서 뺀다.
    #
    # **1쪽이 늘 표지인 것은 아니다.** 약리학 2026판은 목차도 표지도 없이 1쪽부터
    # `1 약리학 소개` · `2-4 약동학` 문항이 시작한다. 1쪽을 무조건 빼면 그 두 섹션의
    # 머리가 사라진다. 문항 줄이 둘 이상 있으면 본문으로 둔다.
    front = [p for p in wq if "목차" in doc[p].get_text()[:40] or "교수님 목록" in doc[p].get_text()[:60]]
    cover = [] if wq and wq[0] == 0 and _has_questions(doc[0]) else [0]
    wq = [p for p in wq if p not in front and p not in cover]
    return {"front": cover + front, "written_q": wq, "written_a": wa,
            "practical_q": pq, "practical_a": pa}


def _has_questions(page: fitz.Page) -> bool:
    lines = [d["text"] for d in page_lines(page)]
    return sum(1 for t in lines if RE_QSTART.match(t) and not RE_ANSWER.match(t)) >= 2


# ─────────────────────────────────────────────────────────────── 목차 / 교수표


# 본문의 강의 머리 — `2-4 약동학 (1)~(3)` · `★ 표적 항암 약리`, 또는 번호만 한 줄
# (`7` / `약물대사`). 제목이 `)`·`:`·`.` 로 시작하면 보기 줄이다(`5) Labetalol`).
RE_BODY_HEAD = re.compile(r"^(★|\d{1,2}(?:\s*-\s*\d{1,2})?)(?:\s+([^\s):.,\]].*))?$")
MAX_TITLE_LINES = 2       # 본문 머리의 제목이 몇 줄까지 접히는가(`중추신경계 … 약리` / `학`)


def headers_as_toc(doc: fitz.Document, pages: list[int]) -> list[tuple[str, str]]:
    """목차가 없는 족보에서 **본문의 강의 머리로** 강의 목록을 세운다.

    약리학 2026판(2026-09-30)이 처음이다. 목차 쪽도 교수 목록 쪽도 없이 1쪽부터
    본문이고, 머리가 올해 시간표 순서로 다시 매겨져 있다. 목차로만 강의를 세우던
    때라 **강의 0개**로 잘렸다 — 그 빈 판이 `current` 가 되어 블럭 한가운데서 모든
    편의 족보가 떨어질 뻔했다.

    머리는 두 모양이다 — `번호 제목` 한 줄, 또는 번호만 한 줄에 제목이 따라오는 것.
    제목은 두 줄까지 접힌다(`25 아미노글라이코사이드계,` / `설파계/퀴놀론 항생제`).
    **머리로 인정하는 것은 제목 바로 뒤가 연도(`2025`)인 것뿐이다.** 본문의 보기나
    문항이 여기 걸리지 않는 까닭이 그 연도다. 쪽번호(맨 아래의 번호만 있는 줄)는
    처음부터 뺀다.

    **같은 번호가 두 번 나오면 뒤의 것에 번호를 붙인다**(`★` · `★2`). 2026판에는
    `★ 항암 항체 치료제` 와 `★ 표적 항암 약리` 가 따로 있다. 키가 같으면 섹션이
    하나로 합쳐진다(`open_section` 이 키로 찾는다).
    """
    header = running_header(doc, pages)
    lines = []
    for pno in pages:
        height = doc[pno].rect.height
        for ln in page_lines(doc[pno]):
            t = ln["text"].strip()
            if not t or t == header:
                continue
            if RE_BARE_NUM.match(t) and ln["y0"] > height - 60:
                continue                  # 쪽번호
            lines.append(t)

    def is_title(t: str) -> bool:
        return not (RE_YEAR.match(t) or RE_QSTART.match(t) or RE_OPTION.match(t)
                    or RE_BODY_HEAD.match(t))

    found: list[tuple[str, str]] = []
    seen: dict[str, int] = {}
    for i, t in enumerate(lines):
        m = RE_BODY_HEAD.match(t)
        if not m or RE_QSTART.match(t):
            continue
        parts = [m.group(2).strip()] if m.group(2) else []
        j = i + 1
        while j < len(lines) and len(parts) < MAX_TITLE_LINES + 1 and is_title(lines[j]):
            parts.append(lines[j])
            j += 1
        if not parts or j >= len(lines) or not RE_YEAR.match(lines[j]):
            continue
        if len(parts) > MAX_TITLE_LINES:
            continue
        title = " ".join(parts)
        key = m.group(1).replace(" ", "")
        seen[key] = seen.get(key, 0) + 1
        if seen[key] > 1:
            key = f"{key}{seen[key]}"
        found.append((key, title))
    return found


def _table_words(page: fitz.Page) -> list[tuple]:
    """교수 표 쪽의 낱말. **표 밖 여백에 색 글씨로 적은 메모는 뺀다.**

    약리학 2026판은 표 왼쪽에 파란 글씨로 `26년도 14-15강` · `알킬화합물/유사분열억제
    항암제` 를 적어 두었다. 그 글자가 제목 열로 들어가 9·10·11 행이 번호를 잃었고
    (9·10·11·28 의 교수가 비었다) 29·★ 행이 이웃에 붙었다. 표 본문은 검정이다.
    """
    words = page.get_text("words")
    notes = [fitz.Rect(s["bbox"]) for b in page.get_text("dict")["blocks"]
             for line in b.get("lines", []) for s in line["spans"]
             if s.get("color", 0) != 0 and s["text"].strip()]
    if not notes:
        return words
    return [w for w in words
            if not any(r.contains(fitz.Point((w[0] + w[2]) / 2, (w[1] + w[3]) / 2))
                       for r in notes)]


class ProfessorTable(dict):
    """행 번호 좌표로 구분한 표의 행. 공동 담당자의 이름 수로 행 혼입을 추정하지 않는다."""
    anchored_rows: set[str]

    def __init__(self, *args, anchored_rows=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.anchored_rows = set(anchored_rows)


def parse_toc(doc: fitz.Document) -> tuple[list[tuple[str, str]], dict, str | None]:
    """(강의목록, 교수표, 경고) 반환. 교수표 파싱이 미덥지 않으면 경고를 채운다."""
    # 목차 안내 페이지에도 "교수님 목록"이 나오므로 표 머리글("수업제목")로 특정한다
    tp = next((i for i in range(doc.page_count)
               if "수업제목" in doc[i].get_text() and "교수님 목록" in doc[i].get_text()), None)
    if tp is None:
        return [], {}, "교수님 목록 표 페이지를 찾지 못했다"

    page = doc[tp]
    words = _table_words(page)
    # **표가 다음 쪽으로 넘어간다.** 약리학 2026판은 35·36 행이 p3 머리에 머리글 없이
    # 이어진다. 못 읽으면 그 두 강의는 교수가 비어 올해 교수로 가를 때 통째로 「참고」로 간다.
    # 다음 쪽이 행 번호로 시작하면 같은 열 위치로 이어 읽는다(y 는 쪽 높이만큼 내린다).
    if tp + 1 < doc.page_count:
        nxt = doc[tp + 1]
        if "수업제목" not in nxt.get_text() and re.match(r"\s*(\d{1,2}(-\d{1,2})?|★)\s*\n",
                                                        nxt.get_text()):
            off = page.rect.height
            words += [(w[0], w[1] + off, w[2], w[3] + off, *w[4:]) for w in _table_words(nxt)]

    # 머리글 행에서 연도 열의 x 중심을 얻는다
    head_y = min((w[1] for w in words if w[4] == "수업제목"), default=None)
    if head_y is None:
        return [], {}, "표 머리글 행을 찾지 못했다"
    # **표 아래 「문제 출처」 행부터는 강의가 아니다.** 그 행의 칸(`학생 복원` · `학습부`)이
    # 가장 가까운 마지막 강의 행에 교수 이름으로 붙는다.
    foot_y = min((w[1] for w in words if w[1] > head_y + 8 and w[4] == "출처"), default=None)
    if foot_y is not None:
        words = [w for w in words if w[1] < foot_y - 2]
    year_cols: dict[str, float] = {}
    for w in words:
        if re.fullmatch(r"\d{2}(?:-\d)?", w[4]) and abs(w[1] - head_y) < 8:
            year_cols[w[4]] = (w[0] + w[2]) / 2
    if len(year_cols) < 3:
        return [], {}, "연도 열 머리글을 찾지 못했다"
    title_x_max = min(year_cols.values()) - 22

    # 행 번호를 기준으로 제목을 묶는다. 작은 글씨 표에서 14px 간격만으로 묶으면
    # 서로 다른 행(예: 16과 17-18)이 합쳐지고 교수 정보도 이웃으로 이동한다.
    anchors = [w for w in words if (w[0] + w[2]) / 2 < title_x_max and w[1] > head_y + 8
               and re.fullmatch(r"(?:★|\d{1,2}(?:-\d{1,2})?)", w[4])]
    left = min((w[0] for w in anchors), default=0)
    anchors = [w for w in anchors if w[0] <= left + 25]
    grouped = [{"ys": [w[1]], "parts": [], "anchor": w} for w in sorted(anchors, key=lambda w: w[1])]
    if grouped:
        for w in words:
            if (w[0] + w[2]) / 2 >= title_x_max or w[1] <= head_y + 8:
                continue
            row = min(grouped, key=lambda r: abs(r["anchor"][1] - w[1]))
            row["parts"].append(w)
        rows = [{"ys": r["ys"], "parts": [" ".join(w[4] for w in sorted(r["parts"], key=lambda w: (round(w[1]), w[0])))]}
                for r in grouped]
        # 번호가 여러 줄 제목의 가운데에 있을 수 있으므로 번호를 맨 앞으로 둔다.
        for row, group in zip(rows, grouped):
            a = group["anchor"]
            row["parts"] = [a[4] + " " + " ".join(w[4] for w in sorted(group["parts"], key=lambda w: (round(w[1]), w[0])) if w != a)]
    else:
        rows = []

    # 번호 좌표가 없는 특수 표는 기존 제목 줄 묶음으로 처리한다.
    tlines: dict[int, list[tuple[float, str]]] = {}
    for w in words:
        if (w[0] + w[2]) / 2 < title_x_max and w[1] > head_y + 8:
            tlines.setdefault(round(w[1]), []).append((w[0], w[4]))
    ys = sorted(tlines)
    for y in ys if not grouped else []:
        text = " ".join(t for _, t in sorted(tlines[y]))
        if rows and y - rows[-1]["ys"][-1] <= 14:
            rows[-1]["ys"].append(y)
            rows[-1]["parts"].append(text)
        else:
            rows.append({"ys": [y], "parts": [text]})

    lectures: list[tuple[str, str]] = []
    profs: dict[str, dict] = ProfessorTable()
    low_conf: list[str] = []

    entries = []
    seen_keys: dict[str, int] = {}
    for r in rows:
        joined = " ".join(r["parts"]).strip()
        if not joined or "문제 출처" in joined or "답안 출처" in joined or joined.startswith("★ 실습"):
            continue
        m = re.match(r"^(★|\d{1,2}(?:\s*-\s*\d{1,2})?)\s+(.*)$", joined)
        if not m:                       # 번호가 가운데 줄에 있는 칸 (예: "종양의 ... / 24-25 / 발암의 원인")
            nums = [p for p in r["parts"] if re.fullmatch(r"\d{1,2}(-\d{1,2})?", p.strip())]
            if not nums:
                continue                # 번호 없는 행(폐지된 강의)은 건너뛴다
            key = nums[0].strip()
            name = " ".join(p for p in r["parts"] if p.strip() != key).strip()
        else:
            key, name = m.group(1).replace(" ", ""), m.group(2).strip()
        # 표가 제목 뒤에 다는 표시는 본문 머리에 없다 — `29 유전자 표적 항암 약리 (변경)`.
        # 남기면 본문 머리와 안 맞아 그 강의 문항이 앞 섹션에 흡수된다.
        name = RE_TOC_NOTE.sub("", name).strip()
        if not name:
            continue
        # 같은 번호가 또 나오면 `★2` 처럼 센다. 본문 머리(`headers_as_toc`)와 같은 규칙이다 —
        # 안 세면 두 행의 교수가 한 칸에 섞이고, 조각 이름이 본문 머리로 세운 판과 갈린다.
        seen_keys[key] = seen_keys.get(key, 0) + 1
        if seen_keys[key] > 1:
            key = f"{key}{seen_keys[key]}"
        entries.append({"key": key, "name": name, "center": sum(r["ys"]) / len(r["ys"])})
        if grouped:
            profs.anchored_rows.add(key)

    # 연도 열의 이름을 가장 가까운 제목 행에 붙인다
    for w in words:
        cx, cy = (w[0] + w[2]) / 2, w[1]
        if cx < title_x_max or cy < head_y + 8 or not re.fullmatch(r"[가-힣]{2,4}", w[4]):
            continue
        best_year = min(year_cols, key=lambda y: abs(year_cols[y] - cx))
        if abs(year_cols[best_year] - cx) > 26 or not entries:
            continue
        row = min(entries, key=lambda e: abs(e["center"] - cy))
        profs.setdefault(row["key"], {}).setdefault(best_year, []).append(w[4])

    for e in entries:
        lectures.append((e["key"], e["name"]))
        cells = profs.setdefault(e["key"], {})
        for col in cells:
            cells[col] = list(dict.fromkeys(cells[col]))
        n_lect = 1
        if "-" in e["key"]:
            a, b = e["key"].split("-")
            n_lect = int(b) - int(a) + 1
        # 한 칸에 강의 수보다 많은 이름이 잡히면 이웃 행에서 흘러들어온 것이다
        if e["key"] not in profs.anchored_rows and any(len(v) > n_lect for v in cells.values()):
            low_conf.append(e["key"])

    warn = None
    if not lectures:
        warn = "목차 표에서 강의를 하나도 뽑지 못했다"
    elif low_conf:
        warn = (f"교수 배정 신뢰도 낮음 {len(low_conf)}건 {low_conf} — "
                f"이 행들은 모델이 p{tp+1}을 한 번 읽어 확정해야 한다")
    return lectures, profs, warn


def _crowded(key: str, cells: dict) -> bool:
    """한 칸에 강의 수보다 많은 이름이 잡혔는가. 이웃 행에서 흘러든 것이다."""
    n_lect = 1
    if "-" in key:
        a, b = key.split("-")
        if a.isdigit() and b.isdigit():
            n_lect = int(b) - int(a) + 1
    return any(len(v) > n_lect for v in cells.values())


# ─────────────────────────────────────────────────────────────── 문항 파싱


MAX_HEADER_LINES = 4      # 섹션 제목이 표 칸에서 최대 몇 줄로 쪼개지는가
MIN_ALIAS = 6             # 별칭으로 인정할 최소 글자 수 (짧으면 오탐이 난다)


def title_aliases(lectures: list[tuple[str, str]]) -> dict:
    """{정규화제목: (key, 원제목)}. 본문 헤더가 목차 제목보다 짧은 경우까지 잡는다.

    목차는 한 줄에 여러 주제를 묶어 적지만(`종양의 정의 및 분류, 암의 역학*`)
    본문 헤더는 앞 토막만 찍혀 있는 일이 있다(`종양의 정의 및 분류`).
    정확히 일치할 때만 섹션을 열면 그 강의는 통째로 앞 섹션에 흡수된다 —
    실제로 21강이 그렇게 19-20 섹션으로 흘러들어갔다.

    그래서 쉼표 앞 토막도 별칭으로 등록한다. 다만 두 강의가 같은 별칭을 만들면
    어느 쪽인지 알 수 없으므로 **그 별칭은 버린다.** 잘못 여는 것이 안 여는 것보다 나쁘다.
    """
    index: dict[str, tuple[str, str]] = {}
    dropped: set[str] = set()

    for k, t in lectures:                       # 정식 제목 먼저. 별칭이 이걸 덮지 못한다.
        for form in (f"{k}{t}", t):
            key = norm(form)
            if key:
                index.setdefault(key, (k, t))

    for k, t in lectures:
        head = t.split(",")[0]
        if head == t:
            continue
        for form in (head, f"{k}{head}"):
            key = norm(form)
            if not key or len(key) < MIN_ALIAS or key in dropped:
                continue
            if key in index and index[key][0] != k:
                index.pop(key)                  # 두 강의가 같은 별칭을 만들면 둘 다 버린다
                dropped.add(key)
            else:
                index[key] = (k, t)
    return index


# ─────────────────────────────────────────────────────────────── 답가지 묶음


def bank_targets(s: str) -> list[str]:
    """머리글의 문항 번호를 펼친다. `"7,8"` → `["7","8"]`, `"42-43"` → `["42","43"]`."""
    m = re.fullmatch(r"\s*(\d{1,3})\s*[-~–]\s*(\d{1,3})\s*", s)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        if 0 <= b - a <= MAX_BANK_SPAN:
            return [str(n) for n in range(a, b + 1)]
        return [m.group(1), m.group(2)]
    return [p.strip() for p in re.split(r"[,·]", s) if p.strip()]


@dataclass
class Bank:
    """답가지를 문항 밖에 한 번만 인쇄하는 연결형 묶음 한 덩어리.

        [문항 7,8].아래 답가지(1-15) 중에서 각 문항에 해당되는 항목을 고르시오
        1.Parietal cell  …  15.Chief cell         ← 공용 답가지
        7.다음 현미경 사진에서 …  8. 다음 현미경 …   ← 이 답가지를 쓰는 문항

    답가지 조판이 두 가지다. 동그라미(①②)면 그냥 두어도 보기로 읽히지만,
    **평번호(`1.` `2.`)는 문항 시작과 생김새가 같다.** 그대로 두면 답가지 15줄이
    전부 가짜 문항이 되고, 번호가 겹치는 진짜 문항의 정답까지 훔쳐 간다 —
    실제로 실습 2021 에서 17문항, 필기에서 40여 항목이 그랬다.

    묶음 문항은 번호가 1부터 다시 시작하는 일이 많고, 그때 정답표는 `R` 을 달아
    구분한다(`R7. 3,10`). 출제자도 같은 충돌을 겪었다는 뜻이다. 앞 문항 번호보다
    작아지면 다시 시작한 것으로 보고 `R` 을 붙인다 — `[42-43]` 처럼 이어지는
    번호는 그대로 둔다.
    """

    targets: list[str]
    restart: bool                      # 번호가 1부터 다시 시작하는가 (= 정답표에서 R)
    items: list[str] = field(default_factory=list)
    nxt: int = 1                       # 다음에 올 평번호 답가지 번호
    hi: int | None = None              # 머리글이 밝힌 답가지 상한
    circled: bool = False
    open: bool = True                  # 아직 답가지를 걷는 중인가
    head: list[str] = field(default_factory=list)   # 머리글 줄들 (범위가 줄바꿈을 탄다)

    @classmethod
    def start(cls, line: str, last_no: int | None) -> Bank | None:
        mh = RE_BANK_HEAD.match(line)
        if not mh:
            return None
        targets = bank_targets(mh.group(1))
        ms = RE_BANK_SPAN.search(line)
        nums = [int(t) for t in targets if t.isdigit()]
        return cls(targets=targets, head=[line],
                   restart=bool(nums) and last_no is not None and min(nums) <= last_no,
                   nxt=int(ms.group(1)) if ms else 1,
                   hi=int(ms.group(2)) if ms else None)

    def feed(self, line: str) -> str:
        """`item` 답가지로 먹었다 · `cont` 앞 답가지에 이어붙였다 ·
        `skip` 머리글이 다음 줄로 넘어간 것이다 · `done` 답가지가 끝났다 (이 줄은 문항)"""
        mo = RE_OPTION.match(line)
        if mo and (self.circled or not self.items):
            self.items.append(f"{mo.group(1)} {mo.group(2)}".strip())
            self.circled = True
            return "item"
        m = RE_QSTART.match(line)
        if m:
            n = m.group(1)
            if (not self.circled and n.isdigit() and int(n) == self.nxt
                    and (self.hi is None or int(n) <= self.hi)):
                self.items.append(f"{n}. {m.group(2)}")
                self.nxt += 1
                return "item"
            self.open = False           # 오름차순이 끊겼다 = 답가지 끝, 문항 시작
            return "done"
        if self.items:
            self.items[-1] += " " + line       # 답가지 한 줄이 넘어간 것
            return "cont"
        # 머리글이 여러 줄로 쪼개진 경우. 범위가 줄바꿈을 타고 끊긴다 —
        # "…아래 답가지(1-" / "8)에서 하나씩 고르시오." 그래서 이어붙여 다시 본다.
        self.head.append(line)
        ms = RE_BANK_SPAN.search("".join(self.head))
        if ms and self.hi is None:
            self.nxt, self.hi = int(ms.group(1)), int(ms.group(2))
        return "skip"

    def owns(self, no: str) -> bool:
        return not self.open and no in self.targets

    def key(self, no: str) -> str:
        return f"R{no}" if self.restart else no


def running_header(doc, pages: list[int]) -> str:
    """쪽마다 되풀이되는 머리글. 절반 넘는 쪽의 첫 줄이 같으면 그것이다.

    이 자리가 `"질병의 병리학적 이해"` 로 박혀 있었다. 다른 과목 족보에서는
    머리글이 안 걸러져 헤더 대조용 `tail` 에 매 쪽 섞였다.
    """
    heads: dict[str, int] = {}
    for pno in pages:
        lines = [d["text"].strip() for d in page_lines(doc[pno])]
        if lines and lines[0]:
            heads[lines[0]] = heads.get(lines[0], 0) + 1
    if not heads:
        return ""
    top, n = max(heads.items(), key=lambda kv: kv[1])
    return top if n * 2 > len(pages) else ""


def parse_question_region(doc, pages, title_index, *, lines_of=None,
                          page_year: dict[int, str] | None = None) -> list[Section]:
    """문항 구역을 섹션/연도/문항으로 가른다. title_index: {정규화제목: (key, 원제목)}

    섹션 제목은 원본에서 한 줄일 수도, 번호와 제목이 여러 줄로 쪼개져 있을 수도 있다
    (예: "24-25" / "종양의 생물학적 특성," / "발암의 원인"). 그래서 최근 몇 줄을
    이어붙여 가며 목차 제목과 대조하고, 맞으면 이미 문항 본문에 넣은 조각을 되돌린다.

    `lines_of`·`page_year` 는 실습 전용 족보를 위한 것이다(`parse_practical`).
    거기서는 연도가 본문의 낱줄이 아니라 **쪽마다의 머리글**에 있고, 한 쪽 안에서
    문항과 정답이 갈리기도 해서 부르는 쪽이 줄을 잘라 넘긴다.
    """
    sections: list[Section] = []
    cur_sec: Section | None = None
    cur_year = "unknown"
    cur_q: Question | None = None
    img_index: dict[int, list[dict]] = {}
    tail: list[str] = []          # 최근 줄 (헤더 대조용)
    consumed: list[bool] = []     # 그 줄이 cur_q 본문에 들어갔는지
    bank: Bank | None = None      # 지금 걷고 있는 공용 답가지 묶음
    last_no: int | None = None    # 이 연도에서 마지막으로 본 보통 문항 번호

    def close_q():
        nonlocal cur_q
        if cur_q and (cur_q.body or cur_q.stem):
            cur_sec.questions.append(cur_q)
        cur_q = None

    def open_section(key, name):
        nonlocal cur_sec, cur_year
        close_q()
        sec = next((s for s in sections if s.lecture_key == key), None)
        if sec is None:
            sec = Section(lecture_key=key, title=name)
            sections.append(sec)
        cur_sec, cur_year = sec, "unknown"

    # **실습 구역은 강의별 헤더가 없다.** 하나의 풀로 미리 열어 둔다 — 이 키가
    # 넘어오는데도 아무 데서도 안 쓰이고 있었고, 그래서 헤더가 우연히 목차 제목과
    # 맞는 족보(병리학 p99 `병리학 실습`)에서만 실습이 잡혔다. 기생충학 2026 은
    # 표제가 `2025 기생충학 실습시험` 이라 안 맞아 9쪽이 통째로 사라졌다.
    if "__practical__" in title_index:
        open_section(*title_index["__practical__"])

    header = running_header(doc, pages)
    for pno in pages:
        page = doc[pno]
        img_index[pno + 1] = page_images(page)
        if page_year and page_year.get(pno) not in (None, cur_year):
            close_q()
            cur_year = page_year[pno]
            bank, last_no = None, None
        for ln in (lines_of(pno) if lines_of else page_lines(page)):
            t = ln["text"].strip()
            if not t or (header and t == header):
                continue
            if re.fullmatch(r"\d{1,3}", t) and ln["y0"] > page.rect.height - 60:
                continue  # 쪽번호

            tail.append(t)
            consumed.append(False)
            del tail[:-MAX_HEADER_LINES]
            del consumed[:-MAX_HEADER_LINES]

            # 최근 k줄을 이어붙여 섹션 제목과 대조 (긴 조합부터)
            hit = None
            for k in range(min(len(tail), MAX_HEADER_LINES), 0, -1):
                joined = norm("".join(tail[-k:]))
                if joined and joined in title_index:
                    hit = (k, title_index[joined])
                    break
            if hit:
                k, (key, name) = hit
                # 제목 조각이 직전 문항 본문에 들어갔으면 되돌린다
                for i in range(len(tail) - k, len(tail)):
                    if consumed[i] and cur_q and cur_q.body:
                        cur_q.body.pop()
                open_section(key, name)
                bank, last_no = None, None
                tail.clear()
                consumed.clear()
                continue

            if RE_YEAR.match(t):
                close_q()
                cur_year = year_key(t)
                bank, last_no = None, None
                continue

            if cur_sec is None:
                continue

            # ── 공용 답가지 묶음 ──
            opened = Bank.start(t, last_no)
            if opened:
                close_q()
                bank = opened
                continue
            if bank is not None and bank.open and bank.feed(t) != "done":
                continue          # 답가지·머리글 잔줄은 문항이 아니다

            m = RE_QSTART.match(t)
            if m and not RE_OPTION.match(t) and len(m.group(1)) <= 3:
                close_q()
                no = m.group(1)
                if bank is not None and bank.owns(no):
                    cur_q = Question(year=cur_year, no=bank.key(no), grouped=True)
                    cur_q.bank = list(bank.items)
                else:
                    bank = None       # 묶음 밖의 문항이 나오면 그 묶음은 끝난 것이다
                    cur_q = Question(year=cur_year, no=no)
                    if no.isdigit():
                        last_no = int(no)
                cur_q.body.append({"kind": "stem", "text": m.group(2)})
                cur_q.pages.append(pno + 1)
                cur_q.span.append((pno + 1, ln["col"], ln["y0"]))
                continue

            if cur_q is None:
                continue

            cur_q.span.append((pno + 1, ln["col"], ln["y1"]))
            if pno + 1 not in cur_q.pages:
                cur_q.pages.append(pno + 1)
            mo = RE_OPTION.match(t)
            cur_q.body.append({"kind": "option" if mo else "cont",
                               "text": f"{mo.group(1)} {mo.group(2)}".strip() if mo else t})
            consumed[-1] = True

    close_q()

    for sec in sections:
        for q in sec.questions:
            q.finalize()

    # 그림 첨부: 문항이 차지한 (페이지, 단, y구간)에 걸친 이미지만 붙인다
    for sec in sections:
        for q in sec.questions:
            for pg, col in {(p, c) for p, c, _ in q.span}:
                ys = [y for p, c, y in q.span if p == pg and c == col]
                lo, hi = min(ys) - 8, max(ys) + 8
                for im in img_index.get(pg, []):
                    if im["col"] == col and im["y0"] < hi and im["y1"] > lo:
                        q.figures.append({"page": pg, "bbox": im["bbox"]})
            q.figures = list({json.dumps(f, sort_keys=True): f for f in q.figures}.values())
            q.needs_figure = bool(q.figures) or bool(RE_FIGURE_WORD.search(q.stem))
            q.span = []
    return sections


# ─────────────────────────────────────────────────────────────── 정답 파싱


class AnswerTable(dict):
    """`{(연도, 번호): 기록}` 에 **강의 섹션별 기록**을 덧붙인 것.

    정답표는 (연도, 번호)로 전역 결합한다(아래 `parse_answer_region` 머리). 그런데 한
    해 안에서 번호가 겹치는 판이 있다 — 2026-10-05 에 세어 보니 약리학 2026판 70문항 ·
    기생충학 2026판 141문항 · 약리학 2020판 272문항이 다른 섹션의 문항과 (연도, 번호)가
    같았다. 전역 열쇠 하나에 정답이 둘이면 나중 것이 앞 것을 덮어, 한쪽 문항이 남의
    정답을 받는다.

    그래서 정답표에서 **같은 열쇠가 두 번 이상 나온 것만** 섹션 머리로 갈라 다시 찾는다
    (`by_section` · `repeated`). 한 번만 나온 열쇠는 전처럼 전역으로 붙는다 — 정답 구역의
    섹션 경계가 문항 구역과 어긋나도 깨지지 않던 성질을 그대로 둔다.
    """

    def __init__(self):
        super().__init__()
        self.by_section: dict[tuple, dict] = {}
        self.repeated: set[tuple] = set()


def parse_answer_region(doc, pages, title_index) -> dict:
    """{(year, no): {'answer':..., 'objection':...}}

    한 해 시험 안에서 문항 번호는 유일하므로 (연도, 번호)만으로 전역 결합한다.
    정답 구역의 섹션 경계가 문항 구역과 한 블록 어긋나도 결합이 깨지지 않는다.
    섹션 제목은 연도 상태를 초기화하는 용도로만 읽는다.
    """
    out = AnswerTable()
    cur_year = "unknown"
    cur_sec: str | None = None
    tail: list[str] = []
    obj_target: tuple | None = None
    obj_sec: str | None = None
    obj_buf: list[str] = []

    def flush_obj():
        nonlocal obj_target, obj_buf
        if obj_target and obj_buf:
            txt = re.sub(r"\s+", " ", " ".join(obj_buf)).strip()
            for rec in (out.setdefault(obj_target, {"answer": None, "objection": None}),
                        out.by_section.setdefault((obj_sec, *obj_target),
                                                  {"answer": None, "objection": None})):
                rec["objection"] = (rec["objection"] + "\n" + txt) if rec["objection"] else txt
        obj_target, obj_buf = None, []

    for pno in pages:
        page = doc[pno]
        for ln in page_lines(page):
            t = ln["text"].strip()
            if not t or t.startswith("질병의 병리학적 이해"):
                continue
            if re.fullmatch(r"\d{1,3}", t) and ln["y0"] > page.rect.height - 60:
                continue

            tail.append(t)
            del tail[:-MAX_HEADER_LINES]
            hit = None
            for k in range(min(len(tail), MAX_HEADER_LINES), 0, -1):
                joined = norm("".join(tail[-k:]))
                if joined and joined in title_index:
                    hit = title_index[joined]
                    break
            if hit:
                flush_obj()
                cur_year = "unknown"
                cur_sec = hit[0]
                tail.clear()
                continue

            if RE_YEAR.match(t):
                flush_obj()
                cur_year = year_key(t)
                continue

            mo = RE_OBJECTION.search(t)
            if mo:
                flush_obj()
                obj_target, obj_sec = (cur_year, mo.group(1)), cur_sec
                continue

            ma = RE_ANSWER.match(t)
            if ma:
                flush_obj()
                k = (cur_year, ma.group(1))
                answer = re.sub(r"\s+", "", ma.group(2))
                if k in out and out[k].get("answer") is not None:
                    out.repeated.add(k)
                out.setdefault(k, {"answer": None, "objection": None})["answer"] = answer
                out.by_section.setdefault((cur_sec, *k),
                                          {"answer": None, "objection": None})["answer"] = answer
                continue

            if obj_target:
                obj_buf.append(t)
    flush_obj()
    return out


# ───────────────────────────────────────────── 실습 전용 족보 (회차가 여럿인 파일)

# 실습 족보는 과목 족보와 따로 돈다. 해마다 앞 해를 안고 커지는 누적본이고
# (`2023 …실습 족보.pdf` 48쪽 안에 2022~2015가 들어 있다), 한 파일에 여러 회차가
# 이어 붙는다. 그래서 `split_regions`의 「문항 구역 하나 · 정답 구역 하나」가 안 맞는다 —
# 첫 정답면 뒤로 전부를 정답으로 보면 두 번째 회차의 문항이 통째로 삼켜진다.
RE_PRAC_NUMLINE = re.compile(r"^\s*\d{1,3}\s*\.\s*\S")
RE_PRAC_MARKER = re.compile(r"^(20\d\d)\s*(?:-\s*(\d))?\s*.{0,12}실습\s*시험\s*$")
RE_PRAC_HEADYEAR = re.compile(r"(20\d\d)(?:\s*-\s*(\d)\s*학기)?\s*(?:땡시|족보)")
# 정답면 판정. 실측(2026 기생충학 실습 족보 두 권 68쪽)에서 문항면의 번호줄은
# 최대 7개, 정답면은 최소 21개였다. 그 사이를 넉넉히 잡는다.
PRAC_ANSWER_LINES = 15
# 정답이 다음 쪽으로 넘어간 자리(2025 회차 p10-11). 그림이 없고 번호줄이 이만큼
# 이어지면 앞 쪽의 정답이 계속되는 것으로 본다.
PRAC_ANSWER_TAIL = 5
# 정답면 안에서 문항이 앞머리에 남아 있는 자리(2016-1학기 p47은 33-35번 뒤에
# 정답표가 붙어 있다). `1.` 부터 번호줄이 몰려 시작하는 지점을 경계로 삼는다.
PRAC_ANSWER_RUN = 5


def _prac_year(y: str, half: str | None) -> str:
    return f"{y}-{half}" if half else y


def practical_layout(doc) -> list[dict]:
    """쪽마다 {page, year, answers, cut}. cut은 그 쪽에서 정답이 시작하는 줄 번호.

    회차는 **쪽 머리글**이 가른다(`… 2023 땡시`). 회차 이름은 본문 표제를
    우선한다 — 2025 회차는 머리글이 `2026 족보`이고 표제가 `2025 기생충학
    실습시험`이라, 머리글을 믿으면 시험 연도가 한 해 밀린다.
    """
    out, prev_head, cur, prev_ans = [], None, None, False
    for pno in range(doc.page_count):
        lines = [d["text"].strip() for d in page_lines(doc[pno])]
        mh = RE_PRAC_HEADYEAR.search(lines[0] if lines else "")
        head_year = _prac_year(mh.group(1), mh.group(2)) if mh else None
        new_sitting = bool(head_year) and head_year != prev_head
        if new_sitting or cur is None:
            cur = head_year or cur
        prev_head = head_year
        for t in lines:
            mk = RE_PRAC_MARKER.match(t)
            if mk:
                cur = _prac_year(mk.group(1), mk.group(2))
                break

        n = sum(1 for t in lines if RE_PRAC_NUMLINE.match(t))
        answers = n >= PRAC_ANSWER_LINES or (
            prev_ans and not new_sitting and n >= PRAC_ANSWER_TAIL
            and not doc[pno].get_images(full=True))
        cut = 0
        if answers:
            for i, t in enumerate(lines):
                if re.match(r"^\s*1\s*\.\s*\S", t) and sum(
                        1 for k in range(i, min(i + 7, len(lines)))
                        if RE_PRAC_NUMLINE.match(lines[k])) >= PRAC_ANSWER_RUN:
                    cut = i
                    break
        prev_ans = answers
        out.append({"page": pno, "year": cur or "unknown",
                    "answers": answers, "cut": cut})
    return out


def parse_practical_answers(doc, layout: list[dict]) -> dict:
    """{(회차, 번호): {'answer':…, 'objection': None}}

    **정답면에서는 `N.` 뒤가 무엇이든 정답이다.** 구역이 이미 그렇게 말하고 있다.
    필기 족보용 `RE_ANSWER`는 숫자만 받는데, 실습 정답은 해마다 꼴이 다르다 —
    `1. 3`(2019·2021·2023) · `1. 가`(2015·2022) · `1. 2 (A. lumbricoides, egg)`(2017)
    · `1. 방광주혈흡충 충란 (이름)`(2016-2). 숫자만 받으면 절반이 빈다.
    """
    out: dict = {}
    for row in layout:
        if not row["answers"]:
            continue
        key = None
        for ln in page_lines(doc[row["page"]])[row["cut"]:]:
            t = ln["text"].strip()
            if not t or re.fullmatch(r"\d{1,3}", t):
                continue
            m = re.match(r"^\s*(\d{1,3})\s*\.\s*(.*)$", t)
            if m:
                key = (row["year"], m.group(1))
                out[key] = {"answer": m.group(2).strip() or None, "objection": None}
            elif key and out[key]["answer"]:
                out[key]["answer"] += " " + t      # 줄을 넘긴 설명
    return {k: v for k, v in out.items() if v["answer"]}


def parse_practical(doc, title: str) -> tuple[list[Question], list[dict]]:
    """실습 전용 족보 한 권을 문항 목록으로 만든다. (문항, 쪽 배치)"""
    layout = practical_layout(doc)
    by_page = {r["page"]: r for r in layout}
    pages = [r["page"] for r in layout if not r["answers"] or r["cut"] > 0]

    def lines_of(pno):
        row = by_page[pno]
        lines = page_lines(doc[pno])
        if row["answers"]:
            lines = lines[:row["cut"]]
        # 머리글은 회차마다 달라 `running_header`가 못 걸러낸다. 여기서 뗀다.
        # 회차 표제(`2015 기생충학 실습시험`)와 `- 35 -` 꼴 쪽번호도 같이 뗀다 —
        # 둘 다 그 쪽 마지막 문항의 `stem` 꼬리에 붙는다(실측 6장·3장).
        return [ln for ln in lines
                if not RE_PRAC_HEADYEAR.search(ln["text"])
                and not RE_PRAC_MARKER.match(ln["text"].strip())
                and not re.fullmatch(r"-\s*\d{1,3}\s*-", ln["text"].strip())]

    secs = parse_question_region(
        doc, pages, {"__practical__": ("PRAC", title)},
        lines_of=lines_of, page_year={r["page"]: r["year"] for r in layout})
    questions = secs[0].questions if secs else []
    answers = parse_practical_answers(doc, layout)
    for q in questions:
        rec = answers.get((q.year, q.no))
        if rec:
            q.answer = rec["answer"]
    return questions, layout


def join_answer(answers: dict, q: Question, section: str | None = None) -> dict | None:
    """정답표에서 이 문항의 기록을 찾는다.

    연결형은 번호가 1부터 다시 시작해 정답표에서 `R` 을 달고 나온다(`R7. 3,10`).
    어느 쪽으로 찍혔는지는 해마다 흔들릴 수 있어 두 형태를 다 본다. 보통 문항은
    `R` 을 달 일이 없으므로 제 번호만 본다 — 넓게 찾으면 남의 정답을 집는다.
    """
    keys = [q.no]
    if q.grouped:
        keys.append(q.no[1:] if q.no.startswith("R") else f"R{q.no}")
    repeated = getattr(answers, "repeated", set())
    for no in keys:
        # 정답표에 같은 열쇠가 둘 이상이면 이 섹션 머리 아래 것을 쓴다(`AnswerTable`).
        if section is not None and (q.year, no) in repeated:
            rec = answers.by_section.get((section, q.year, no))
            if rec:
                return rec
        rec = answers.get((q.year, no))
        if rec:
            return rec
    return None


# ─────────────────────────────────────────────────────────────── 반복률


def _sig(q: Question) -> set[str]:
    return word_tokens(q.stem)


def repeat_stats(sec: Section, profs: dict) -> dict:
    qs = [q for q in sec.questions if len(_sig(q)) >= 4]
    pairs, matched = [], set()
    for i in range(len(qs)):
        for k in range(i + 1, len(qs)):
            a, b = qs[i], qs[k]
            if a.year == b.year:
                continue
            sa, sb = _sig(a), _sig(b)
            jac = len(sa & sb) / max(len(sa | sb), 1)
            if jac >= 0.55:
                pairs.append({"a": f"{a.year}-{a.no}", "b": f"{b.year}-{b.no}", "jaccard": round(jac, 2)})
                matched.add(a.key)
                matched.add(b.key)
    rate = round(len(matched) / len(qs), 3) if qs else 0.0

    yr = profs.get(sec.lecture_key, {})
    cur = yr.get("26") or yr.get("25")
    changed = bool(yr.get("26") and yr.get("25") and set(yr["26"]) != set(yr["25"]))
    return {"n_questions": len(sec.questions), "n_comparable": len(qs),
            "repeat_rate": rate, "repeat_pairs": pairs[:40],
            "professors_by_year": yr, "professor_2026": cur,
            "professor_changed_2026": changed,
            "jokbo_weight_hint": "low" if changed else ("high" if rate >= 0.35 else "normal")}


# ─────────────────────────────────────────────────────────────── 올해 교수 것을 앞에
#
# 2026-10-05 관리자 — 처음에는 *"이제부터 올해 실제 강의교수가 낸 족보만을 근거로
# 하자"* 였고, 같은 날 고쳤다 — *"본인 족보를 우선시하는거로. 다른 족보도 참고 정도는
# 해도 될듯."* 그래서 **빼지 않고 가른다.** 올해 교수가 낸 해를 앞에 두고 통계(반복률 ·
# 교수 유임)는 그것으로만 재며, 나머지는 조각 뒤 「참고」로 간다. 참고를 얼마나 쓸지는
# 정하지 않았다 — 「참고 정도는 해도 될듯」은 허용이지 규칙이 아니다.
#
# **올해 교수는 족보 표의 26년 열에서 읽지 않는다.** 그 열은 시간표에서 옮겨 적은
# 것이라 실제와 다르다(약리학 약동학 — 표는 유경상·이승환, 실제 허기영). 올해 교수는
# 부르는 쪽이 필기 파일명이나 `pre_target.json` 에서 읽어 넘긴다(`pack.lecture_professors`).
# **해마다의 출제 교수는 표에서 읽는다** — 그것 말고는 적힌 곳이 없다.


def same_person(a: str, b: str) -> bool:
    """두 이름이 같은 사람인가. 파일명이 이름을 붙여 쓰는 일이 있다 — `(문경철김혜령)`."""
    if a == b:
        return True
    return len(a) >= 2 and len(b) >= 2 and (a in b or b in a)


def split_by_professor(payload: dict, professors: list[str]) -> tuple[dict, dict]:
    """조각을 **올해 교수가 낸 해(앞)** 와 **참고(뒤)** 로 가른다. (새 조각, 가른 기록)

    한 해의 출제자는 족보 표의 그 해 칸이다. 칸이 비었거나(표에 없는 해 · 표를 못
    읽은 강의) 해를 모르는 문항은 참고로 간다 — 올해 교수가 냈다고 확인되지 않는다.
    참고 문항에는 `reference: true` 가 붙는다.

    한 칸에 교수가 둘이면(함께 맡은 강의) 올해 교수가 그 안에 있을 때 그 해를 통째로
    앞에 둔다. 족보는 문항마다 출제자를 적지 않아서 그 해 안에서는 가를 수 없다.
    다른 강의를 흡수한 섹션(`may_contain`)도 같다 — 흡수된 강의의 칸까지 같이 본다.

    통계는 앞의 것으로만 다시 잰다 — 그 교수가 무엇을 되풀이해 냈는가가 이제 반복률의
    뜻이다. 앞이 비면(올해 처음 맡은 교수) 통계는 전체로 재고 `professor_changed_2026`
    을 켠다 — 지금까지의 「교수 교체」 지침이 그대로 그 경우다.
    """
    stats = payload.get("stats") or {}
    by_year = stats.get("professors_by_year") or {}
    absorbed = stats.get("absorbed_professors_by_year") or {}
    own, ref, rows = [], [], {}
    for q in payload.get("questions") or []:
        year = str(q.get("year", ""))
        if q.get("by") is not None:
            cell = q["by"]          # 옛 판에서 온 문항 — 그 판의 칸 (`merge_older`)
        else:
            cell = (year_professors(by_year, year) + year_professors(absorbed, year)
                    if RE_YEAR.match(year) else None)
        if cell and any(same_person(a, b) for a in cell for b in professors):
            own.append({k: v for k, v in q.items() if k != "reference"})
            continue
        ref.append({**q, "reference": True})
        row = rows.setdefault(year, {"year": year, "n": 0, "by": cell or None})
        row["n"] += 1
    own_years = sorted({str(q["year"]) for q in own}, reverse=True)
    fields = {f for f in Question.__dataclass_fields__ if f not in ("body", "span", "bank")}
    sec = Section(lecture_key=payload.get("lecture_key", ""), title=payload.get("title", ""))
    sec.questions = [Question(**{k: v for k, v in q.items() if k in fields}) for q in (own or ref)]
    if own:
        cells = {year_key(y)[2:]: year_professors(by_year, y) for y in own_years if year_professors(by_year, y)}
        new_stats = repeat_stats(sec, {sec.lecture_key: cells})
        new_stats["professors_by_year"] = {**cells, "26": list(professors)}
        new_stats["professor_changed_2026"] = False
        new_stats["jokbo_weight_hint"] = "high" if new_stats["repeat_rate"] >= 0.35 else "normal"
    else:
        new_stats = repeat_stats(sec, {sec.lecture_key: by_year})
        new_stats["professors_by_year"] = {**by_year, "26": list(professors)}
        new_stats["professor_changed_2026"] = True
        new_stats["jokbo_weight_hint"] = "low"
    new_stats["professor_2026"] = list(professors)
    new_stats["n_reference"] = len(ref)
    if absorbed:
        new_stats["absorbed_professors_by_year"] = absorbed
    note = {"professors": list(professors), "n_total": len(own) + len(ref),
            "n_own": len(own), "n_reference": len(ref), "own_years": own_years,
            "reference": sorted(rows.values(), key=lambda r: r["year"], reverse=True)}
    new_stats["professor_filter"] = note
    return {**payload, "stats": new_stats, "questions": own + ref}, note


def split_line(note: dict) -> str:
    """가른 것을 사람이 읽는 한 줄. 조각 머리와 화면이 같은 말을 한다."""
    who = "·".join(note.get("professors") or []) or "미상"
    own = " · ".join(note.get("own_years") or []) or "없음"
    ref = " · ".join(f"{r['year']}({'/'.join(r['by']) if r.get('by') else '출제자 모름'})"
                     for r in note.get("reference") or [])
    line = f"올해 교수({who})가 낸 해 {note.get('n_own', 0)}문항({own})을 앞에 두었다"
    return line + (f" · 참고 {note.get('n_reference', 0)}문항 {ref}" if ref else "")


PRIORITY_NOTE = (
    "**올해 담당 교수가 낸 문항을 우선한다.** 기출 카드와 `jokbo_ref` 는 앞쪽(올해 교수가 "
    "낸 해)에서 먼저 고른다. 맨 뒤 「참고」는 다른 교수가 냈거나 출제자를 모르는 해다 — "
    "이 단원에서 무엇이 시험에 나올 만한 지식인지 보는 데 참고로 써도 된다.")


# ─────────────────────────────────────────────────────────────── 출력


def slug(key: str, title: str) -> str:
    t = re.sub(r"[^0-9A-Za-z가-힣]+", "-", title).strip("-")[:40]
    return f"L{key}_{t}"


def to_markdown(sec: Section, stats: dict) -> str:
    L = [f"# {sec.lecture_key} {sec.title}", ""]
    yr = stats["professors_by_year"]
    if yr:
        L.append("담당 교수: " + " | ".join(f"20{y} {'·'.join(v)}" for y, v in sorted(yr.items(), reverse=True)))
    if stats.get("professor_filter"):
        L.append(split_line(stats["professor_filter"]))
    if stats["professor_changed_2026"]:
        L.append("⚠ 2026년 교수 교체 — 족보 신뢰도를 낮춰 사용할 것")
    L.append(f"문항 {stats['n_questions']}개 · 연도간 반복률 {stats['repeat_rate']:.0%} "
             f"· 족보 가중치 권고: {stats['jokbo_weight_hint']}")
    if sec.may_contain:
        L.append("")
        L.append("⚠ **이 조각에는 다른 강의 문항이 섞여 있다.** 아래 강의는 족보 본문에 제목이 "
                 "없어 문항이 이 섹션으로 흘러들어왔다. 이번 강의 소관이 아닌 문항은 골라내라.")
        for k, t in sec.may_contain:
            L.append(f"- {k} {t}")
    own = [q for q in sec.questions if not q.reference]
    ref = [q for q in sec.questions if q.reference]
    if ref and own:
        L += ["", PRIORITY_NOTE]
    L.append("")
    _year_blocks(L, own, "")
    if ref:
        L += ["## 참고 — 올해 교수가 내지 않은 해", "",
              "아래는 다른 교수가 냈거나 출제자를 모르는 해의 문항이다. 앞의 문항이 우선이다."
              if own else
              "올해 교수가 낸 해가 이 단원 족보에 없다. 아래는 다른 교수가 냈거나 출제자를 "
              "모르는 해의 문항이다 — 참고로 써도 된다.", ""]
        _year_blocks(L, ref, "참고 · ")
    return "\n".join(L)


def _year_blocks(L: list[str], questions: list[Question], prefix: str) -> None:
    for year in sorted({q.year for q in questions}, reverse=True):
        L.append(f"## {prefix}{year}")
        for q in [q for q in questions if q.year == year]:
            head = f"### {q.no}번"
            if q.answer:
                head += f"  [정답 {q.answer}]"
            else:
                head += "  [정답 미확인]"
            if q.figures:
                head += f"  [그림 {len(q.figures)}개: p{q.pages[0]}]"
            if q.grouped:
                head += "  [연결형 — 아래 공용 답가지에서 고른다]"
            L += [head, q.stem]
            L += q.options
            if q.objection:
                L.append("> 이의제기: " + q.objection)
            L.append("")


def _caught(doc: fitz.Document, regions: dict, lectures: list[tuple[str, str]]) -> int:
    """이 강의 목록으로 섹션을 세우면 해를 아는 문항이 몇 개 잡히는가."""
    sections = parse_question_region(doc, regions["written_q"], title_aliases(lectures))
    return sum(1 for s in sections for q in s.questions if RE_YEAR.match(q.year))


def parse_edition(doc: fitz.Document) -> dict:
    """족보 한 권의 필기 구역을 강의별 섹션으로 읽는다. 정답·이의제기까지 붙인다.

    `main` 이 자르는 판과 `--older` 로 덧붙이는 옛 판이 **같은 길을 지난다.** 두 길로
    두면 한쪽에만 고친 것(목차가 없는 판 · 두 쪽짜리 목차 표)이 다른 쪽에서 다시 난다.
    """
    regions = split_regions(doc)
    lectures, profs, warn = parse_toc(doc)
    body = headers_as_toc(doc, regions["written_q"])
    if not lectures:
        # 목차가 없는 판. 본문 머리로 세운다(`headers_as_toc`). 교수 목록도 없으므로
        # 교수 교체 판정은 이 판에서 안 선다 — 그것을 경고로 남긴다.
        lectures = body
        if lectures:
            warn = (f"{warn} — 본문 머리로 강의 {len(lectures)}개를 세웠다. "
                    f"교수 목록이 없어 교수 교체 판정은 이 판에서 안 선다")
    elif len(body) > len(lectures) or (
            len(body) == len(lectures) and _caught(doc, regions, body) >= _caught(doc, regions, lectures)):
        # 같은 수면 **본문 문항을 덜 잃는 쪽**이다. 2026-10-05 에 표를 끝까지 읽게 되자
        # (`_table_words` · 다음 쪽 이어 읽기) 약리학 2026판이 표 31 · 본문 31 로 같아졌다.
        # 표로 세우면 `★ 항암 항체 치료제` 행이 29 에 붙어 있어 그 6문항이 29 로 흡수됐다.
        # 기생충학 2026판은 같은 18 · 18 인데 본문으로 세우면 568 문항 중 128 을 잃는다.
        # **목차 표가 본문보다 적게 잡혔다.** 약리학 2026 완전판(2026-10-01)이 그랬다 —
        # 표가 두 쪽에 걸쳐 둘째 쪽(35·36)을 못 읽었고, 줄 간격이 좁은 행이 이웃 행에
        # 붙었다(9→10 · 29·★→28). 그러면 놓친 강의의 문항이 앞 강의에 흡수되고
        # (10 에 46문항 · 34 에 57문항), 섞인 교수 이름으로 「교수 교체」가 잘못 선다.
        # 강의 목록은 본문 머리를 따르고, 표에서는 **깨끗한 칸의 교수만** 가져온다.
        missed = [k for k, _ in body if k not in {key for key, _ in lectures}]
        trusted = getattr(profs, "anchored_rows", set())
        crowded = [k for k, cells in profs.items() if k not in trusted and _crowded(k, cells)]
        keep = {k for k, _ in body}
        profs = ProfessorTable({k: v for k, v in profs.items() if k in keep and k not in crowded
                              and not k.startswith("★")}, anchored_rows=trusted & keep)
        warn = (f"목차 표에서 강의 {len(lectures)}개만 잡혀 본문 머리 {len(body)}개로 세웠다 "
                f"(표에서 놓친 것 {missed}). 교수가 섞인 칸 {crowded} 과 ★ 는 교수를 버렸다 — "
                f"그 강의는 교수 교체 판정이 안 선다")
        lectures = body
    title_index = title_aliases(lectures)

    sections = parse_question_region(doc, regions["written_q"], title_index)
    # 본문에 헤더가 없는 강의의 문항은 앞 섹션으로 흡수된다. 목차 순서로 누가 섞였는지 계산한다.
    order = [k for k, _ in lectures]
    found = [s.lecture_key for s in sections]
    for sec in sections:
        try:
            i = order.index(sec.lecture_key)
        except ValueError:
            continue
        nxt = next((order.index(k) for k in order[i + 1:] if k in found), len(order))
        sec.may_contain = [(k, t) for k, t in lectures[i + 1:nxt] if k != "★"]
    answers = parse_answer_region(doc, regions["written_a"], title_index)
    for sec in sections:
        for q in sec.questions:
            rec = join_answer(answers, q, sec.lecture_key)
            if rec:
                q.answer, q.objection = rec["answer"], rec["objection"]
    return {"regions": regions, "lectures": lectures, "profs": profs, "warn": warn,
            "title_index": title_index, "sections": sections, "answers": answers}


# ─────────────────────────────────────────────────────────────── 옛 판 덧붙이기
#
# 2026-10-05 관리자 — *"족보를 2026, 2020년꺼를 써서, 2026-2015까지를 커버할 수
# 있도록 하자."* 2026판은 2020·2021·2022·2023·2025 시험을, 2020판은 2015~2019
# 시험을 싣는다(병리학·미생물학 실측 — 약리학 2026판은 2017~2019 도 일부 싣는다).
#
# **강의 번호로 잇지 않고 제목으로 잇는다.** 두 판의 번호가 다르다 — 병리학
# `조직 재생 및 수복` 이 2020판 6-7 · 2026판 5-6 이다.

OLDER_MATCH_MIN = 0.5      # 제목 글자쌍 자카드. 이 아래면 잇지 않는다
OLDER_MATCH_GAP = 0.05     # 1등과 2등이 이만큼도 안 벌어지면 어느 쪽인지 모른다


# 두 판이 같은 것을 달리 적은 말. 약리학 2020판 `유전자 타겟 항암약리` = 2026판 `유전자 표적 항암 약리`.
TITLE_SYNONYMS = {"타겟": "표적"}


def _title_grams(title: str) -> set[str]:
    k = norm(title).lower()
    for a, b in TITLE_SYNONYMS.items():
        k = k.replace(a, b)
    return {k[i:i + 2] for i in range(len(k) - 1)} or {k}


def _title_sim(old: str, new: str, contained: bool = False) -> float:
    """옛 판 제목과 이번 판 목차 제목의 닮은 정도 (글자쌍 자카드).

    `contained` 면 **이번 판 제목이 옛 제목 안에 통째로 들었을 때** 0.9 로 친다. 옛 판
    제목에 덧붙은 말이 있다 — 약리학 2020판 `항염증 약리 2019년도 기준 “NSAIDs …`.
    자카드로 아무것도 못 이었을 때만 쓴다(`merge_older`). 처음부터 쓰면 `신호전달 타겟
    항암약리` 가 `31 신호전달 표적항암제`(0.70)를 두고 묶음 섹션 `★2 표적 항암 약리` 로
    갔다. 짧은 제목이 아무 데나 들어가지 않게 글자쌍 넷 이상일 때만 본다.
    """
    go, gn = _title_grams(old), _title_grams(new)
    jac = len(go & gn) / len(go | gn) if go | gn else 0.0
    if contained and len(gn) >= 4 and gn <= go:
        return max(jac, 0.9)
    return jac


def _n_lectures(key: str) -> int:
    if "-" in key:
        a, b = key.split("-", 1)
        if a.isdigit() and b.isdigit():
            return int(b) - int(a) + 1
    return 1


def _names_of(cells: dict) -> set[str]:
    return {n for names in (cells or {}).values() for n in names}


def _older_author(old: Section, old_profs: dict, yy: str, n_lect: int) -> list[str]:
    """옛 판 문항 하나의 출제 교수. 모르면 빈 목록 — 가르는 쪽이 「참고」로 보낸다.

    **옛 판 섹션이 다른 강의를 흡수했으면 그 해 칸이 문항마다의 출제자가 아니다.**
    병리학 2020판 `유전질환` 섹션에 `소아질환` 문항이 섞여 있다(본문에 소아질환
    머리가 없다). 그해 두 강의 교수가 같을 때만 그 이름을 쓴다.
    """
    cell = year_professors(old_profs.get(old.lecture_key) or {}, yy)
    if not cell or (old.lecture_key not in getattr(old_profs, "anchored_rows", set()) and len(cell) > n_lect):
        return []
    for key, _ in old.may_contain:
        other = year_professors(old_profs.get(key) or {}, yy)
        if set(other) != set(cell):
            return []
    return list(cell)


def merge_older(sections: list[Section], lectures: list[tuple[str, str]], profs: dict,
                older: dict, src: int) -> dict:
    """옛 판(`parse_edition` 결과)의 문항과 교수 칸을 이번 판에 덧붙인다.

    **잇는 상대는 이번 판의 섹션이 아니라 목차 강의다.** 이번 판 본문에 문항이 없는
    강의가 있다 — 병리학 2026판 `4 세포의 손상 및 적응 (3)~(4)` 는 목차에만 있다.
    섹션끼리만 대조하면 2020판의 그 강의가 제일 닮은 `2-3` 에 0.64 로 붙었다.

        목차 강의에 섹션이 있다          그 섹션에 붙인다
        다른 섹션에 흡수돼 있다          그 섹션에 붙인다 (`may_contain` — 이번 판과 같은 처지)
        섹션이 없다                     섹션을 새로 세운다

    - 문항은 **이번 판 그 섹션에 없는 해만** 가져온다. 약리학처럼 두 판이 같은 해를
      싣는 과목에서 한 문항이 두 번 들어가지 않게 한다. 해를 모르는 문항은 안 가져온다.
    - 가져온 문항마다 **그 해 옛 판 칸의 교수**(`by`)를 단다. 흡수된 섹션에서는 섹션의
      칸이 이 문항의 출제자가 아니기 때문이다. 칸이 비었거나 한 칸에 강의 수보다 많은
      이름이 잡혔으면(`_crowded` — 이웃 행에서 흘러든 것) 빈 목록으로 둔다 — 모른다.
    - 섹션의 교수 칸은 **바로 이은 경우에만**, 이번 판에 없는 해만 채운다.
    - 1등과 2등이 `OLDER_MATCH_GAP` 안이면 **교수가 겹치는 쪽**을 고른다. 병리학
      2020판 `분자면역병리 (3)`(배정모)은 2026판 (1)·(2) 와 제목으로는 똑같이 닮았다.
      그래도 못 가르면 잇지 않는다.
    - 가져온 문항에는 `src` 를 단다. 지면 이미지를 그 판에서 찾게 하는 표시다.

    돌려주는 것은 사람이 읽을 대조표다. 잇지 못한 옛 섹션은 **버리지 않고 적는다.**
    """
    by_key = {s.lecture_key: s for s in sections if s.lecture_key != "PRAC"}
    absorbed = {k: s for s in by_key.values() for k, _ in s.may_contain}
    titles = dict(lectures)
    for s in by_key.values():
        titles.setdefault(s.lecture_key, s.title)
    titles.pop("PRAC", None)
    have = {k: {q.year for q in s.questions} for k, s in by_key.items()}
    main_names = {k: _names_of(profs.get(k)) for k in titles}
    rows, unmatched = [], []
    for old in older["sections"]:
        scored = sorted(((_title_sim(old.title, t), k) for k, t in titles.items()),
                        key=lambda x: -x[0])
        if scored and scored[0][0] < OLDER_MATCH_MIN:
            scored = sorted(((_title_sim(old.title, t, contained=True), k)
                             for k, t in titles.items()), key=lambda x: -x[0])
        best = scored[0][0] if scored else 0.0
        near = [k for sc, k in scored if sc >= max(best - OLDER_MATCH_GAP, OLDER_MATCH_MIN)]
        old_cells = older["profs"].get(old.lecture_key) or {}
        how = "제목"
        if len(near) > 1:
            shared = [k for k in near if main_names[k] & _names_of(old_cells)]
            if len(shared) == 1:
                near, how = shared, "제목 + 교수"
        years = sorted({q.year for q in old.questions})
        if len(near) != 1:
            why = ("닮은 제목이 없다" if not near else
                   f"제목이 비슷한 강의가 여럿이고 교수로도 못 가른다 ({' · '.join(near)})")
            unmatched.append({"lecture_key": old.lecture_key, "title": old.title,
                              "n_questions": len(old.questions), "years": years,
                              "best": round(best, 2), "why": why})
            continue
        key = near[0]
        sec = by_key.get(key) or absorbed.get(key)
        if sec is None and not any(RE_YEAR.match(q.year) for q in old.questions):
            unmatched.append({"lecture_key": old.lecture_key, "title": old.title,
                              "n_questions": len(old.questions), "years": years,
                              "best": round(best, 2), "why": f"{key} 와 이었지만 해를 아는 문항이 없다"})
            continue
        if sec is None:
            sec = Section(lecture_key=key, title=titles[key])
            sections.append(sec)
            by_key[key] = sec
            have[key] = set()
            how += " · 이번 판에 섹션이 없어 새로 세웠다"
        elif sec.lecture_key != key:
            how += f" · 이번 판에서 {sec.lecture_key} 에 흡수된 강의"
        n_lect = _n_lectures(old.lecture_key)
        took = [q for q in old.questions
                if q.year not in have[sec.lecture_key] and RE_YEAR.match(q.year)]
        for q in took:
            q.src = src
            q.by = _older_author(old, older["profs"], q.year, n_lect)
        sec.questions += took
        filled = []
        if sec.lecture_key == key:
            cells = profs.setdefault(key, {})
            for col, names in sorted(old_cells.items()):
                if col not in cells and (old.lecture_key in getattr(older["profs"], "anchored_rows", set()) or len(names) <= n_lect):
                    cells[col] = names
                    filled.append(col)
        rows.append({"old_key": old.lecture_key, "old_title": old.title,
                     "lecture_key": sec.lecture_key, "matched": key, "how": how,
                     "score": round(best, 2), "took": len(took),
                     "skipped": len(old.questions) - len(took),
                     "years": sorted({q.year for q in took}), "prof_years": filled})
    return {"matched": rows, "unmatched": unmatched}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="족보 PDF를 강의별 조각으로 미리 자른다")
    ap.add_argument("pdf")
    ap.add_argument("-o", "--out", default="out/jokbo")
    ap.add_argument("--practical", nargs="+", metavar="PDF",
                    help="실습 족보 PDF (여러 개 가능). 주면 PRAC 조각을 이것으로만 만든다")
    ap.add_argument("--older", nargs="+", metavar="PDF",
                    help="옛 판 과목 족보 (예: 2020판). 이번 판에 없는 해의 필기 문항과 "
                         "교수 칸을 제목이 맞는 섹션에 덧붙인다")
    args = ap.parse_args(argv)

    doc = fitz.open(args.pdf)

    # **`-o` 는 과목 폴더를 받고 조각은 그 아래 판 폴더로 들어간다.**
    # `runs/_materials/기생충학/260915-0130/` 같은 자리다.
    #
    # 과목 이름은 **`-o` 로 받은 폴더의 이름**에서 읽는다(아래 `prac_name`). 그래서
    # 여기에 판 폴더를 직접 받으면 안 된다 — 실습 조각이 「260915-0130 실습」이라는
    # 이름으로 나온다. 그 이름은 `find_jokbo` 가 제목으로 대조하는 값이다.
    #
    # 판마다 폴더가 따로 서므로 **아무것도 덮지 않는다.** 앞 컷을 밀어내던
    # `cutmark.archive` 가 그래서 할 일이 없어졌다.
    subject_dir = Path(args.out)
    subject_dir.mkdir(parents=True, exist_ok=True)
    cut_id = cutmark.new_cut_id()
    taken = set(cutmark.cuts(subject_dir))
    base, n = cut_id, 1
    while cut_id in taken:
        n += 1
        cut_id = f"{base}.{n}"
    outdir = subject_dir / cut_id
    outdir.mkdir(parents=True, exist_ok=True)

    ed = parse_edition(doc)
    regions, lectures, profs, warn = ed["regions"], ed["lectures"], ed["profs"], ed["warn"]
    sections, answers = ed["sections"], ed["answers"]

    # 옛 판. 문항이 가리키는 지면이 그 판에 있으므로 `src` 로 원본을 가른다 —
    # 필기 조각의 `sources` 가 이 목록이다(실습 조각은 실습 족보 목록을 든다).
    older_sources: list[dict] = []
    older_merges: list[dict] = []
    for path in args.older or []:
        odoc = fitz.open(path)
        merged = merge_older(sections, lectures, profs, parse_edition(odoc),
                             src=len(older_sources))
        older_sources.append({"name": Path(path).name, "path": str(Path(path).resolve()),
                              "pages": odoc.page_count})
        older_merges.append({"source": Path(path).name, **merged})
        odoc.close()

    # 실습은 강의별 헤더가 없어 연도 블록만으로 하나의 풀로 둔다.
    # **과목 이름은 폴더에서 읽는다.** 여기에 "병리학"이 박혀 있었는데, 그러면
    # 기생충학 실습 조각이 「병리학 실습」이라는 이름으로 나온다.
    # **판 폴더가 아니라 과목 폴더의 이름이다.** 판을 읽으면 실습 조각이
    # 「260915-0130 실습」이 되고, 그 이름을 `find_jokbo` 가 제목으로 대조한다.
    prac_name = f"{subject_dir.name} 실습"
    prac_keys = {norm(f"{subject_dir.name}실습"): ("PRAC", prac_name),
                 norm(f"{subject_dir.name}실습시험"): ("PRAC", prac_name)}
    prac_sources: list[dict] = []
    prac_layouts: list[tuple[str, list[dict]]] = []
    if args.practical:
        # **실습 족보를 따로 받으면 과목 족보의 실습 구역은 안 쓴다.** 겹치기
        # 때문이다 — 2026 기생충학 족보의 실습 구역(p60-70)은 실습 족보 폴더의
        # 11쪽짜리와 같은 지면이다. 한 조각이 원본 PDF 하나를 가리키던 자리를
        # `sources`로 늘렸으므로, 섞지 않고 실습 족보 쪽으로 통일한다.
        prac = [Section(lecture_key="PRAC", title=prac_name)]
        for i, path in enumerate(args.practical):
            pdoc = fitz.open(path)
            qs, layout = parse_practical(pdoc, prac_name)
            for q in qs:
                q.src = i
            prac[0].questions += qs
            prac_sources.append({"name": Path(path).name,
                                 "path": str(Path(path).resolve()),
                                 "pages": pdoc.page_count})
            prac_layouts.append((Path(path).name, layout))
            pdoc.close()
    else:
        prac = parse_question_region(
            doc, regions["practical_q"], {"__practical__": ("PRAC", prac_name), **prac_keys})
        prac_ans = parse_answer_region(doc, regions["practical_a"], prac_keys)
        for sec in prac:
            for q in sec.questions:
                rec = join_answer(prac_ans, q)
                if rec:
                    q.answer, q.objection = rec["answer"], rec["objection"]

    # `cut_id` 를 `index.json` 에도 넣는다. **이 파일을 이미 읽는 쪽이 여럿이라**
    # (`pack.find_jokbo`·`build.find_jokbo_source`·`prequiz.assemble`) 판을 공짜로
    # 본다. 정본은 `cut.json` 이고 여기 것은 그 사본이다.
    index = {"cut_id": cut_id,
             "source": Path(args.pdf).name, "pages": doc.page_count,
             "regions": {k: [p + 1 for p in v] for k, v in regions.items()},
             "toc_warning": warn, "lectures": []}
    if prac_sources:
        index["practical_sources"] = prac_sources
    if older_sources:
        index["older_sources"] = older_sources
        index["older_merge"] = older_merges

    for sec in sections + prac:
        stats = repeat_stats(sec, profs)
        if sec.may_contain:
            # 흡수된 강의의 교수. 이 섹션의 문항은 해마다 누가 냈는지 못 가르므로 올해
            # 교수로 가를 때 이 칸도 같이 본다(`split_by_professor`). 흡수된 강의 쪽에서
            # 이 조각을 받을 때 제 해가 남아야 한다 — 받는 것은 그쪽도 이 조각이다.
            absorbed: dict[str, list[str]] = {}
            for key, _ in sec.may_contain:
                for col, names in (profs.get(key) or {}).items():
                    absorbed.setdefault(col, [])
                    absorbed[col] += [n for n in names if n not in absorbed[col]]
            stats["absorbed_professors_by_year"] = absorbed
        name = slug(sec.lecture_key, sec.title)
        drop = ("body", "span", "bank")
        qs = [{k: v for k, v in asdict(q).items()
               if k not in drop and not (k in ("src", "by", "reference") and v is None)}
              for q in sec.questions]
        payload = {"lecture_key": sec.lecture_key, "title": sec.title,
                   "may_contain": [{"lecture_key": k, "title": t} for k, t in sec.may_contain],
                   "stats": stats, "questions": qs}
        if sec.lecture_key == "PRAC" and prac_sources:
            # 조각이 자기 원본을 들고 다닌다. 빌드는 조각만 받으므로
            # (`build.Jokbo`) 여기 없으면 지면 이미지가 조용히 빠진다.
            payload["sources"] = prac_sources
        elif sec.lecture_key != "PRAC" and older_sources:
            # 옛 판에서 온 문항(`src` 가 정수)의 지면은 그 판에 있다. 이번 판 문항은
            # `src` 가 없고 지금처럼 `index.source_path` 를 본다.
            payload["sources"] = older_sources
        (outdir / f"{name}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        (outdir / f"{name}.md").write_text(to_markdown(sec, stats), encoding="utf-8")
        index["lectures"].append({
            "lecture_key": sec.lecture_key, "title": sec.title, "file": name,
            "n_questions": stats["n_questions"],
            "n_with_answer": sum(1 for q in sec.questions if q.answer),
            "n_with_objection": sum(1 for q in sec.questions if q.objection),
            "n_with_figure": sum(1 for q in sec.questions if q.figures),
            "years": sorted({q.year for q in sec.questions}),
            "repeat_rate": stats["repeat_rate"],
            "professor_changed_2026": stats["professor_changed_2026"],
            "jokbo_weight_hint": stats["jokbo_weight_hint"],
            "may_contain": [k for k, _ in sec.may_contain]})

    (outdir / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")

    # **판을 적는다.** `index.json` **뒤에** 써야 한다 — 이 줄에서 죽어도 조각과
    # 색인은 이미 서 있고, 그때 없는 것은 판뿐이다(`describe` 가 「판이 적혀 있지
    # 않다」로 읽어 준다). 반대로 두면 판은 있고 색인이 없는 컷이 생긴다.
    #
    # **여기서 죽어서는 안 된다.** 조각 37개와 색인이 다 나온 뒤인데 예외가 나가면
    # 종료 코드가 「안 만들어졌다」고 거짓말을 하고, 그것을 믿는 `run_jokbo` 가
    # `source_path` 를 안 적어 기출 카드 뒷면의 지면 이미지가 조용히 빠진다
    # (`runner/CLAUDE.md` 첫 절이 그 사고다). 판을 못 적는 것보다 그게 나쁘다.
    try:
        cutmark.write(outdir, source=Path(args.pdf), pages=doc.page_count,
                      practical=prac_sources or None, older=older_sources or None,
                      cut_id=cut_id,
                      counts={"lectures": len(index["lectures"]),
                              "questions": sum(e["n_questions"] for e in index["lectures"])})
        # **`current` 는 맨 마지막에 돌린다.** 앞에서 죽으면 지금 판이 그대로
        # 남아야 한다 — 반쯤 쓰인 판을 가리키면 다음 빌드가 그것을 읽는다.
        #
        # **강의가 하나도 안 잡힌 판으로는 안 돌린다.** 2026-09-30 약리학 2026판이
        # 목차가 없어 강의 0개로 잘렸는데 `current` 가 그 판으로 넘어갔다 — 블럭
        # 한가운데서 모든 편의 족보가 떨어질 뻔했다. 빈 판은 남겨 두되 가리키지 않는다.
        if sections:
            cutmark.set_current(subject_dir, cut_id)
        print(cutmark.describe(outdir))
    except (OSError, ValueError) as cause:
        print(f"⚠ 판({cut_id})을 못 적었다 ({cause}) — 조각은 다 나왔다. "
              f"이 컷으로 만든 덱은 어느 컷인지 물을 수 없다")

    # 콘솔 요약
    # **네 구역이 다 있다고 보면 안 된다.** 2026 기생충학 족보는 실습이 통째로
    # 없어서(예전 해들은 「실습 족보」가 별도 PDF였다) 이 줄이 IndexError로 죽었고,
    # 그 바람에 다 잘라 놓고도 `run_jokbo`가 실패로 받아 `index.json`에
    # `source_path`를 못 적었다 — 기출 카드 뒷면의 지면 이미지가 조용히 빠지는 자리다.
    # 없으면 없다고 찍는다. 그것이 사람이 봐야 할 신호다.
    def _span(pages: list[int]) -> str:
        return f"p{pages[0] + 1}-{pages[-1] + 1}" if pages else "없음"

    print(f"구역: 필기문항 {_span(regions['written_q'])} · "
          f"필기정답 {_span(regions['written_a'])} · "
          f"실습문항 {_span(regions['practical_q'])} · "
          f"실습정답 {_span(regions['practical_a'])}")
    for fname, layout in prac_layouts:
        sittings = {}
        for row in layout:
            e = sittings.setdefault(row["year"], [0, 0])
            e[1 if row["answers"] else 0] += 1
        detail = " · ".join(f"{y} 문항{q}쪽/정답{a}쪽" for y, (q, a) in sittings.items())
        print(f"실습 족보 {fname}: 회차 {len(sittings)}개 — {detail}")
        if regions["practical_q"]:
            print(f"   과목 족보의 실습 구역 {_span(regions['practical_q'])} 는 "
                  f"이것과 겹쳐 쓰지 않았다")
    for merged in older_merges:
        took = sum(r["took"] for r in merged["matched"])
        print(f"옛 판 {merged['source']}: 섹션 {len(merged['matched'])}개를 이어 문항 {took}개를 "
              f"덧붙였다 (이번 판에 이미 있는 해 · 해 모름은 안 가져왔다)")
        for r in merged["matched"]:
            years = ",".join(y[2:] for y in r["years"]) or "-"   # 16-1 처럼 회차까지 보인다
            print(f"   {r['old_key']:>6} {r['old_title'][:24]:<24} → {r['matched']:<6} "
                  f"{r['score']:.2f}  +{r['took']:<3} ({years})  교수칸 +{len(r['prof_years'])}"
                  + (f"  [{r['how']}]" if r['how'] != "제목" else ""))
        for u in merged["unmatched"]:
            print(f"   {u['lecture_key']:>6} {u['title'][:24]:<24} → 잇지 못함 "
                  f"({u['why']}) — 문항 {u['n_questions']}개를 안 가져왔다")
    if warn:
        print(f"경고: {warn}")
    print(f"목차 강의 {len(lectures)}개 / 본문에서 잡힌 섹션 {len(sections)}개\n")
    print(f"{'강의':<34}{'문항':>5}{'정답':>5}{'이의':>5}{'그림':>5}{'반복률':>8}  가중치")
    for e in index["lectures"]:
        mark = " ⚠교수교체" if e["professor_changed_2026"] else ""
        print(f"{(e['lecture_key']+' '+e['title'])[:33]:<34}{e['n_questions']:>5}{e['n_with_answer']:>5}"
              f"{e['n_with_objection']:>5}{e['n_with_figure']:>5}{e['repeat_rate']:>8.0%}  {e['jokbo_weight_hint']}{mark}")
    missed = [k for k, t in lectures if k != "★" and not any(s.lecture_key == k for s in sections)]
    if missed:
        print(f"\n본문에 기출이 없는 목차 항목: {missed}  (시간표에서 빠졌거나 수집되지 않은 강의)")

    # 연결형은 정답표가 R 을 달고 찍으므로 두 형태를 다 짝지은 것으로 친다
    used = set()
    for sec in sections:
        for q in sec.questions:
            used.add((q.year, q.no))
            if q.grouped:
                used.add((q.year, q.no.lstrip("R")))
    orphan = sorted(f"{k[0]}-{k[1]}" for k, v in answers.items() if v["answer"] and k not in used)
    if orphan:
        print(f"\n짝을 못 찾은 정답 {len(orphan)}개: {orphan[:24]}{' …' if len(orphan) > 24 else ''}")
    noans = [(sec.lecture_key, q.year, q.no) for sec in sections for q in sec.questions if not q.answer]
    if noans:
        by_sec: dict = {}
        for k in noans:
            by_sec.setdefault(k[0], []).append(f"{k[1]}-{k[2]}")
        print(f"\n정답을 못 찾은 문항 {len(noans)}개:")
        for k, v in sorted(by_sec.items(), key=lambda x: -len(x[1])):
            print(f"   [{k}] {len(v)}개  {v[:12]}{' …' if len(v) > 12 else ''}")
    if not sections:
        # 조각은 나왔지만 쓸 것이 없다. **성공으로 끝내면 부르는 쪽이 「잘렸다」고 믿는다**
        # (`run_jokbo` 가 「이 조각을 스스로 물린다」를 찍는다). 지금 판은 그대로다.
        print(f"\n⚠ 필기 섹션을 하나도 못 잡았다 — 지금 판({cutmark.resolve(subject_dir).name})을 "
              f"그대로 둔다. 이 판({cut_id})은 가리키지 않는다")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

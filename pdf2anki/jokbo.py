"""족보 PDF 사전 절단기.

과목 전체 족보 PDF 한 개를 받아서 강의별 조각으로 미리 잘라 둔다.
강의마다 다시 돌릴 필요 없이 과목당 한 번만 실행한다.

코드가 책임지는 것: 구역 분리, 섹션/연도/문항 경계, 정답 결합, 이의제기 결합,
                    그림 첨부, 교수 표 파싱, 문항 반복률 계산.
모델이 책임지는 것: 이 조각들 중 무엇이 이번 강의 소관인지, 무엇을 카드로 낼지.

사용:
    python -m pdf2anki.jokbo "족보_예시/2026 질병의 병리학적 이해 족보.pdf" -o out/jokbo
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path

import fitz

from .textutil import norm_key as norm, word_tokens

# ─────────────────────────────────────────────────────────────── 정규식/상수

CIRCLED = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮"
RE_YEAR = re.compile(r"^\s*(19|20)\d{2}\s*$")
RE_QSTART = re.compile(r"^\s*(R?\d{1,3})\s*\.\s*(\S.*)$")
RE_ANSWER = re.compile(r"^\s*(R?\d{1,3})\s*\.\s*([\d]+(?:\s*,\s*\d+)*)\s*$")
RE_OPTION = re.compile(rf"^\s*([{CIRCLED}])\s*(.*)$")
RE_OBJECTION = re.compile(r"\[?\s*(R?\d{1,3})\s*번?\s*이의제기\s*\]?")
RE_BARE_NUM = re.compile(r"^\s*(\d{1,3}(?:\s*-\s*\d{1,3})?)\s*$")
RE_FIGURE_WORD = re.compile(r"그림|사진|이미지|소견|모식도|도식|현미경|아래\s*의?\s*(그림|사진)")
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


def split_regions(doc: fitz.Document) -> dict[str, list[int]]:
    """페이지 머리글과 정답행 밀도로 네 구역을 가른다. 값은 0-based 페이지 목록."""
    practical, written = [], []
    for i in range(doc.page_count):
        head = (doc[i].get_text().split("\n") or [""])[0]
        (practical if "실습" in head else written).append(i)

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
    # 목차/표지는 문항 구역에서 뺀다
    front = [p for p in wq if "목차" in doc[p].get_text()[:40] or "교수님 목록" in doc[p].get_text()[:60]]
    wq = [p for p in wq if p not in front and p != 0]
    return {"front": [0] + front, "written_q": wq, "written_a": wa,
            "practical_q": pq, "practical_a": pa}


# ─────────────────────────────────────────────────────────────── 목차 / 교수표


def parse_toc(doc: fitz.Document) -> tuple[list[tuple[str, str]], dict, str | None]:
    """(강의목록, 교수표, 경고) 반환. 교수표 파싱이 미덥지 않으면 경고를 채운다."""
    # 목차 안내 페이지에도 "교수님 목록"이 나오므로 표 머리글("수업제목")로 특정한다
    tp = next((i for i in range(doc.page_count)
               if "수업제목" in doc[i].get_text() and "교수님 목록" in doc[i].get_text()), None)
    if tp is None:
        return [], {}, "교수님 목록 표 페이지를 찾지 못했다"

    page = doc[tp]
    words = page.get_text("words")

    # 머리글 행에서 연도 열의 x 중심을 얻는다
    head_y = min((w[1] for w in words if w[4] == "수업제목"), default=None)
    if head_y is None:
        return [], {}, "표 머리글 행을 찾지 못했다"
    year_cols: dict[str, float] = {}
    for w in words:
        if re.fullmatch(r"\d{2}", w[4]) and abs(w[1] - head_y) < 8:
            year_cols[w[4]] = (w[0] + w[2]) / 2
    if len(year_cols) < 3:
        return [], {}, "연도 열 머리글을 찾지 못했다"
    title_x_max = min(year_cols.values()) - 22

    # 제목 열의 줄을 세로 간격으로 묶어 행을 만든다 (한 칸이 여러 줄일 수 있다)
    tlines: dict[int, list[tuple[float, str]]] = {}
    for w in words:
        if (w[0] + w[2]) / 2 < title_x_max and w[1] > head_y + 8:
            tlines.setdefault(round(w[1]), []).append((w[0], w[4]))
    ys = sorted(tlines)
    rows: list[dict] = []
    for y in ys:
        text = " ".join(t for _, t in sorted(tlines[y]))
        if rows and y - rows[-1]["ys"][-1] <= 14:
            rows[-1]["ys"].append(y)
            rows[-1]["parts"].append(text)
        else:
            rows.append({"ys": [y], "parts": [text]})

    lectures: list[tuple[str, str]] = []
    profs: dict[str, dict] = {}
    low_conf: list[str] = []

    entries = []
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
        if not name:
            continue
        entries.append({"key": key, "name": name, "center": sum(r["ys"]) / len(r["ys"])})

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
        n_lect = 1
        if "-" in e["key"]:
            a, b = e["key"].split("-")
            n_lect = int(b) - int(a) + 1
        # 한 칸에 강의 수보다 많은 이름이 잡히면 이웃 행에서 흘러들어온 것이다
        if any(len(v) > n_lect for v in cells.values()):
            low_conf.append(e["key"])

    warn = None
    if not lectures:
        warn = "목차 표에서 강의를 하나도 뽑지 못했다"
    elif low_conf:
        warn = (f"교수 배정 신뢰도 낮음 {len(low_conf)}건 {low_conf} — "
                f"이 행들은 모델이 p{tp+1}을 한 번 읽어 확정해야 한다")
    return lectures, profs, warn


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
    def start(cls, line: str, last_no: int | None) -> "Bank | None":
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


def parse_question_region(doc, pages, title_index) -> list[Section]:
    """문항 구역을 섹션/연도/문항으로 가른다. title_index: {정규화제목: (key, 원제목)}

    섹션 제목은 원본에서 한 줄일 수도, 번호와 제목이 여러 줄로 쪼개져 있을 수도 있다
    (예: "24-25" / "종양의 생물학적 특성," / "발암의 원인"). 그래서 최근 몇 줄을
    이어붙여 가며 목차 제목과 대조하고, 맞으면 이미 문항 본문에 넣은 조각을 되돌린다.
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

    for pno in pages:
        page = doc[pno]
        img_index[pno + 1] = page_images(page)
        for ln in page_lines(page):
            t = ln["text"].strip()
            if not t or t.startswith("질병의 병리학적 이해"):
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
                cur_year = t.strip()
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


def parse_answer_region(doc, pages, title_index) -> dict:
    """{(year, no): {'answer':..., 'objection':...}}

    한 해 시험 안에서 문항 번호는 유일하므로 (연도, 번호)만으로 전역 결합한다.
    정답 구역의 섹션 경계가 문항 구역과 한 블록 어긋나도 결합이 깨지지 않는다.
    섹션 제목은 연도 상태를 초기화하는 용도로만 읽는다.
    """
    out: dict = {}
    cur_year = "unknown"
    tail: list[str] = []
    obj_target: tuple | None = None
    obj_buf: list[str] = []

    def flush_obj():
        nonlocal obj_target, obj_buf
        if obj_target and obj_buf:
            rec = out.setdefault(obj_target, {"answer": None, "objection": None})
            txt = re.sub(r"\s+", " ", " ".join(obj_buf)).strip()
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
                tail.clear()
                continue

            if RE_YEAR.match(t):
                flush_obj()
                cur_year = t.strip()
                continue

            mo = RE_OBJECTION.search(t)
            if mo:
                flush_obj()
                obj_target = (cur_year, mo.group(1))
                continue

            ma = RE_ANSWER.match(t)
            if ma:
                flush_obj()
                k = (cur_year, ma.group(1))
                rec = out.setdefault(k, {"answer": None, "objection": None})
                rec["answer"] = re.sub(r"\s+", "", ma.group(2))
                continue

            if obj_target:
                obj_buf.append(t)
    flush_obj()
    return out


def join_answer(answers: dict, q: Question) -> dict | None:
    """정답표에서 이 문항의 기록을 찾는다.

    연결형은 번호가 1부터 다시 시작해 정답표에서 `R` 을 달고 나온다(`R7. 3,10`).
    어느 쪽으로 찍혔는지는 해마다 흔들릴 수 있어 두 형태를 다 본다. 보통 문항은
    `R` 을 달 일이 없으므로 제 번호만 본다 — 넓게 찾으면 남의 정답을 집는다.
    """
    keys = [q.no]
    if q.grouped:
        keys.append(q.no[1:] if q.no.startswith("R") else f"R{q.no}")
    for no in keys:
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


# ─────────────────────────────────────────────────────────────── 출력


def slug(key: str, title: str) -> str:
    t = re.sub(r"[^0-9A-Za-z가-힣]+", "-", title).strip("-")[:40]
    return f"L{key}_{t}"


def to_markdown(sec: Section, stats: dict) -> str:
    L = [f"# {sec.lecture_key} {sec.title}", ""]
    yr = stats["professors_by_year"]
    if yr:
        L.append("담당 교수: " + " | ".join(f"20{y} {'·'.join(v)}" for y, v in sorted(yr.items(), reverse=True)))
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
    L.append("")
    for year in sorted({q.year for q in sec.questions}, reverse=True):
        L.append(f"## {year}")
        for q in [q for q in sec.questions if q.year == year]:
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
    return "\n".join(L)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="족보 PDF를 강의별 조각으로 미리 자른다")
    ap.add_argument("pdf")
    ap.add_argument("-o", "--out", default="out/jokbo")
    args = ap.parse_args(argv)

    doc = fitz.open(args.pdf)
    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)

    regions = split_regions(doc)
    lectures, profs, warn = parse_toc(doc)
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
            rec = join_answer(answers, q)
            if rec:
                q.answer, q.objection = rec["answer"], rec["objection"]

    # 실습은 강의별 헤더가 없어 연도 블록만으로 하나의 풀로 둔다
    prac_index = {"__practical__": ("PRAC", "병리학 실습")}
    prac = parse_question_region(
        doc, regions["practical_q"],
        {**prac_index, norm("병리학실습"): ("PRAC", "병리학 실습")})
    prac_ans = parse_answer_region(doc, regions["practical_a"], {norm("병리학실습"): ("PRAC", "병리학 실습")})
    for sec in prac:
        for q in sec.questions:
            rec = join_answer(prac_ans, q)
            if rec:
                q.answer, q.objection = rec["answer"], rec["objection"]

    index = {"source": Path(args.pdf).name, "pages": doc.page_count,
             "regions": {k: [p + 1 for p in v] for k, v in regions.items()},
             "toc_warning": warn, "lectures": []}

    for sec in sections + prac:
        stats = repeat_stats(sec, profs)
        name = slug(sec.lecture_key, sec.title)
        qs = [{k: v for k, v in asdict(q).items() if k not in ("body", "span", "bank")}
              for q in sec.questions]
        payload = {"lecture_key": sec.lecture_key, "title": sec.title,
                   "may_contain": [{"lecture_key": k, "title": t} for k, t in sec.may_contain],
                   "stats": stats, "questions": qs}
        (outdir / f"{name}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        (outdir / f"{name}.md").write_text(to_markdown(sec, stats), encoding="utf-8")
        index["lectures"].append({
            "lecture_key": sec.lecture_key, "title": sec.title, "file": name,
            "n_questions": stats["n_questions"],
            "n_with_answer": sum(1 for q in sec.questions if q.answer),
            "n_with_objection": sum(1 for q in sec.questions if q.objection),
            "n_with_figure": sum(1 for q in sec.questions if q.figures),
            "repeat_rate": stats["repeat_rate"],
            "professor_changed_2026": stats["professor_changed_2026"],
            "jokbo_weight_hint": stats["jokbo_weight_hint"],
            "may_contain": [k for k, _ in sec.may_contain]})

    (outdir / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")

    # 콘솔 요약
    print(f"구역: 필기문항 p{regions['written_q'][0]+1}-{regions['written_q'][-1]+1} · "
          f"필기정답 p{regions['written_a'][0]+1}-{regions['written_a'][-1]+1} · "
          f"실습문항 p{regions['practical_q'][0]+1}-{regions['practical_q'][-1]+1} · "
          f"실습정답 p{regions['practical_a'][0]+1}-{regions['practical_a'][-1]+1}")
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
    return 0


if __name__ == "__main__":
    sys.exit(main())

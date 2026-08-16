"""과목 족보 PDF를 강의별로 자른다.

## 왜 이쪽이 낫나

지금까지 족보는 **필기 뒤에 붙은 캡처 이미지**에서 읽었다. 필기자가 족보를
캡처해 붙이기 때문에 문항이 annotation 이미지로만 존재하고, 그래서 채널을
나누고 경계를 판정하는 일이 통째로 필요했다.

과목 족보 폴더의 원본은 다르다. 병리학 2026을 열어 보면:

    122쪽 · 텍스트 레이어 살아 있음 (평균 1,646자/쪽) · OCR 불필요
    p2   연도별 강의↔교수 매트릭스
    p4~  "1  병리학 소개 – 과거, 현재, 미래" 처럼 **강의별로 이미 분류됨**
    p78~ 실습 시험 블록 (같은 강의 번호를 다시 훑는다)

여기서 잘라 오면 족보 채널이 이미지가 아니라 원본 PDF가 되고, 경계 판정이
필요 없어진다.

## 머리글은 정규식이 아니라 서식으로 잡는다

본문은 9pt, 강의 머리글의 번호는 13.8~15pt다. 정규식으로 "숫자 + 제목"을
찾으면 본문의 문항 번호까지 걸린다. 실제로 그렇게 짰다가 30개 중 10개만
잡혔다. 크기로 거르면 거의 다 잡힌다.

    강의 머리글   size >= 13.5 이고 본문이 "7" 또는 "2-3"
    연도 머리글   size >= 14 이고 본문이 네 자리 연도
    블록 머리글   "★ ... 실습"

## 교수 매트릭스는 참고 자료다

p2의 표는 연도별 담당 교수를 담고 있어 강의 매칭에 쓸 만하지만, **교실
사정으로 교수가 바뀌면 표가 틀린다.** 색과 같은 원칙이다 - 참고로 싣되
단독 근거로 쓰지 않는다. `index.json`에 `reference_only: true`로 남긴다.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

import fitz

# 강의 머리글의 번호. "7", "2-3", "13~15" 를 받는다.
_SECTION_NO_RE = re.compile(r"^(\d{1,2})(?:\s*[-~–—]\s*(\d{1,2}))?$")
_YEAR_RE = re.compile(r"^(20\d{2})$")

# 번호 머리글의 최소 크기. 병리학 2026에서 11-12가 13.8pt로 나와 14로 두면 놓친다.
HEADING_MIN_SIZE = 13.5

# 블록 전환 표시. 필기 시험 족보가 끝나고 실습 시험 블록이 시작된다.
_BLOCK_RE = re.compile(r"실습")


@dataclass
class Section:
    """족보 PDF 안의 한 덩어리. 강의 하나 또는 연속한 여러 강의."""

    lectures: list[int]
    title: str
    block: str            # '필기' | '실습'
    start_page: int       # 1-based, 이 페이지부터
    end_page: int         # 이 페이지까지 (포함)
    years: list[int] = field(default_factory=list)
    pdf: str = ""

    @property
    def label(self) -> str:
        if not self.lectures:
            return "L00"
        if len(self.lectures) == 1:
            return f"L{self.lectures[0]:02d}"
        return f"L{self.lectures[0]:02d}-{self.lectures[-1]:02d}"


def _spans(page) -> list[dict]:
    return [
        span
        for block in page.get_text("dict")["blocks"]
        for line in block.get("lines", [])
        for span in line.get("spans", [])
        if span["text"].strip()
    ]


# 제목이 두 줄로 감기는 일이 잦다 - "종양의 생물학적 특성, / 발암의 원인" 처럼.
# 번호는 두 줄 사이에 놓이므로 한 줄만 보면 제목을 통째로 놓친다.
_TITLE_BAND = 24.0


def _title_beside(spans: list[dict], anchor: dict) -> str:
    """번호 오른쪽의 글자 뭉치. 두 줄로 감긴 제목까지 모아 붙인다."""
    top, right = anchor["bbox"][1], anchor["bbox"][2]
    beside = [
        s for s in spans
        if abs(s["bbox"][1] - top) <= _TITLE_BAND
        and s["bbox"][0] >= right - 2
        and s["size"] >= 11.5
        and not _YEAR_RE.match(s["text"].strip())
        and not _SECTION_NO_RE.match(s["text"].strip())
        and s is not anchor
    ]
    beside.sort(key=lambda s: (round(s["bbox"][1]), s["bbox"][0]))
    return " ".join(s["text"].strip() for s in beside).strip()


# 번호도 감긴다: "28-" 다음 줄에 "30". 앞부분만 보면 30번 강의로 잘못 읽는다.
_DANGLING_NO_RE = re.compile(r"^(\d{1,2})\s*[-~–—]$")


def _merge_wrapped_numbers(spans: list[dict]) -> list[tuple[dict, str]]:
    """(번호 span, 정규화된 번호 문자열) 목록. 줄바꿈으로 갈라진 번호를 붙인다."""
    big = [s for s in spans if s["size"] >= HEADING_MIN_SIZE]
    used: set[int] = set()
    result: list[tuple[dict, str]] = []
    for index, span in enumerate(big):
        if index in used:
            continue
        text = span["text"].strip()
        dangling = _DANGLING_NO_RE.match(text)
        if dangling:
            below = [
                (j, o) for j, o in enumerate(big)
                if j not in used and j != index
                and 0 < o["bbox"][1] - span["bbox"][1] < 45
                and abs(o["bbox"][0] - span["bbox"][0]) < 30
                and re.fullmatch(r"\d{1,2}", o["text"].strip())
            ]
            if below:
                j, other = min(below, key=lambda pair: pair[1]["bbox"][1])
                used.add(j)
                result.append((span, f"{dangling.group(1)}-{other['text'].strip()}"))
                continue
        if _SECTION_NO_RE.match(text):
            result.append((span, text))
    return result


def _title_from_text(page_text: str, number: str) -> str:
    """서식으로 제목을 못 잡았을 때의 보루. 같은 번호로 시작하는 줄을 찾는다."""
    escaped = re.escape(number).replace(r"\-", r"\s*[-~–—]\s*")
    pattern = re.compile(rf"^\s*{escaped}\s+(\S.{{3,60}})$", re.M)
    match = pattern.search(page_text)
    return match.group(1).strip() if match else ""


def _expand(low: int, high: int | None) -> list[int]:
    if high is None or high < low:
        return [low]
    return list(range(low, high + 1))


def scan_sections(pdf_path: str | Path, body_start: int = 4) -> list[Section]:
    """족보 PDF를 훑어 강의별 구간을 찾는다. `body_start`는 목차 다음 쪽."""
    found: list[Section] = []
    block_marks: list[int] = []
    with fitz.open(str(pdf_path)) as doc:
        total = doc.page_count
        block = "필기"
        for index in range(body_start - 1, total):
            spans = _spans(doc[index])

            for span in spans:
                text = span["text"].strip()
                if (span["size"] >= HEADING_MIN_SIZE and _BLOCK_RE.search(text)
                        and "★" not in text and not _SECTION_NO_RE.match(text)):
                    if block != "실습":
                        block = "실습"
                    block_marks.append(index + 1)

            for span, number in _merge_wrapped_numbers(spans):
                match = _SECTION_NO_RE.match(number)
                if not match:
                    continue
                low = int(match.group(1))
                high = int(match.group(2)) if match.group(2) else None
                if low > 60:                       # 강의 번호는 이만큼 크지 않다
                    continue
                title = _title_beside(spans, span)
                if not title:
                    # 제목이 번호에서 멀리 떨어져 찍힌 경우. 서식으로 못 잡으면
                    # 그 페이지 본문에서 같은 번호로 시작하는 줄을 찾는다.
                    title = _title_from_text(doc[index].get_text(), number)
                found.append(Section(
                    lectures=_expand(low, high), title=title,
                    block=block, start_page=index + 1, end_page=total,
                ))

        # 끝쪽은 다음 구간이 정한다. 같은 페이지에서 두 구간이 시작하면 그 페이지를
        # 양쪽이 나눠 갖는다 - 잘라낸 PDF에 남의 문항이 한 쪽 섞이는 편이,
        # 한 쪽을 통째로 잃는 것보다 낫다.
        for current, following in zip(found, found[1:]):
            current.end_page = max(current.start_page, following.start_page - 1) \
                if following.start_page > current.start_page else current.start_page

        # 마지막 구간이 문서 끝까지 삼키지 않게 한다. 병리학 2026은 p99에 블록
        # 표시가 하나 더 있고 거기부터는 강의 구분이 없는 실습 족보다.
        if found:
            last = found[-1]
            later = [p for p in block_marks if p > last.start_page]
            if later:
                last.end_page = max(last.start_page, min(later) - 1)
                tail_start = min(later)
                if tail_start <= total:
                    found.append(Section(
                        lectures=[], title="강의 구분 없는 실습 족보",
                        block="실습", start_page=tail_start, end_page=total))

        # 각 구간에 어느 연도 기출이 들어 있는지
        with fitz.open(str(pdf_path)) as doc2:
            for section in found:
                years: set[int] = set()
                for index in range(section.start_page - 1, section.end_page):
                    for span in _spans(doc2[index]):
                        year = _YEAR_RE.match(span["text"].strip())
                        if year and span["size"] >= 14:
                            years.add(int(year.group(1)))
                section.years = sorted(years, reverse=True)

    return found


def parse_professor_matrix(pdf_path: str | Path, page: int = 2) -> dict:
    """p2의 연도별 강의↔교수 표. **참고 자료다.**

    교실 사정으로 담당이 바뀌면 표가 틀린다. 강의 매칭의 보조로만 쓰고
    단독 근거로 쓰지 않는다.
    """
    with fitz.open(str(pdf_path)) as doc:
        if page > doc.page_count:
            return {"reference_only": True, "rows": []}
        spans = _spans(doc[page - 1])

    # 표의 칸은 줄마다 따로 찍혀 있어 줄 단위로 읽으면 대부분 놓친다(실측 5/20행).
    # y로 묶어 행을 복원하고 x로 정렬해 칸 순서를 되살린다.
    bands: dict[int, list[dict]] = {}
    for span in spans:
        bands.setdefault(round(span["bbox"][1] / 6), []).append(span)

    rows: list[dict] = []
    for _, band in sorted(bands.items()):
        band.sort(key=lambda s: s["bbox"][0])
        cells = [s["text"].strip() for s in band if s["text"].strip()]
        if len(cells) < 3:
            continue
        head = _SECTION_NO_RE.match(cells[0])
        if not head:
            continue
        rest = cells[1:]
        title = rest[0] if rest and not re.fullmatch(r"[가-힣]{2,4}", rest[0]) else ""
        names = [c for c in rest if re.fullmatch(r"[가-힣]{2,4}", c)]
        if not names:
            continue
        rows.append({
            "lectures": _expand(int(head.group(1)),
                                int(head.group(2)) if head.group(2) else None),
            "title": title,
            "professors_by_year": names,   # 표의 열 순서 그대로 (최신 → 과거)
        })
    return {
        "reference_only": True,
        "note": "교실 사정으로 담당 교수가 바뀔 수 있다. 매칭의 보조로만 쓰고 "
                "단독 근거로 쓰지 마라.",
        "rows": rows,
    }


def _safe(text: str) -> str:
    value = re.sub(r'[\\/*?:"<>|]+', "", text).strip()
    return re.sub(r"\s+", "_", value)[:48] or "untitled"


def split(pdf_path: str | Path, out_dir: str | Path, body_start: int = 4) -> dict:
    """구간마다 PDF를 잘라 내고 인덱스를 쓴다."""
    pdf_path = Path(pdf_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    sections = scan_sections(pdf_path, body_start)
    with fitz.open(str(pdf_path)) as doc:
        for section in sections:
            name = f"{section.label}_{section.block}_{_safe(section.title)}.pdf"
            target = out_dir / name
            piece = fitz.open()
            piece.insert_pdf(doc, from_page=section.start_page - 1,
                             to_page=section.end_page - 1)
            # 조각마다 리소스 트리가 통째로 복제돼 합계가 원본보다 커진다
            # (실측 109MB → 112MB). 안 쓰는 객체를 걷어내고 압축한다.
            piece.save(str(target), garbage=4, deflate=True, clean=True)
            piece.close()
            section.pdf = str(target)

    by_lecture: dict[str, list[str]] = {}
    for section in sections:
        for number in section.lectures:
            by_lecture.setdefault(str(number), []).append(section.pdf)

    index = {
        "source": str(pdf_path),
        "section_count": len(sections),
        # label은 프로퍼티라 asdict가 담지 않는다. 인덱스를 읽는 쪽이 다시
        # 계산하게 두지 말고 여기서 박아 둔다.
        "sections": [{**asdict(s), "label": s.label} for s in sections],
        "by_lecture": by_lecture,
        "professor_reference": parse_professor_matrix(pdf_path),
    }
    (out_dir / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    return index


# ── 필기 ↔ 족보 연결 ──────────────────────────────────────────────────────
#
# 족보는 강의를 1~30 번호로 부르고, 필기는 `[260812_01]` 날짜_교시로 부른다.
# 둘을 잇는 건 제목뿐이다. 교수 매트릭스도 있지만 담당이 바뀌면 틀리므로
# 가산점으로만 쓴다.

LINK_CONFIDENT = 0.70
LINK_PLAUSIBLE = 0.42

# 족보 제목의 순번: "세포의 손상 및 적응 (1)~(2)" → {1, 2}
_TITLE_SEQ_RE = re.compile(r"[(（]\s*(\d{1,2})\s*[)）]")

# 실습 필기 제목의 껍데기. "질병의 병리학적 이해 실습 2-<주제>" 에서 주제만 남긴다.
_PRACTICAL_PREFIX_RE = re.compile(r"^.*?실습\s*\d*\s*[-–—:]\s*")


def _title_sequences(title: str) -> set[int]:
    """제목이 덮는 강의 순번. "(1)~(3)"이면 1,2,3 전부."""
    numbers = [int(n) for n in _TITLE_SEQ_RE.findall(title)]
    if not numbers:
        return set()
    if "~" in title or "-" in title:
        return set(range(min(numbers), max(numbers) + 1))
    return set(numbers)


def _comparable(title: str, practical: bool) -> str:
    """비교용 이름. 실습 필기는 껍데기를 벗겨 주제만 남긴다."""
    from .filenames import normalize_stem

    if practical:
        stripped = _PRACTICAL_PREFIX_RE.sub("", title)
        if stripped:
            title = stripped
    return normalize_stem(_TITLE_SEQ_RE.sub(" ", title))


def link_lectures(index: dict, lectures) -> list[dict]:
    """올해 필기 각 편에 족보 구간을 붙인다.

    `lectures`는 `studyez.filenames.LectureFile` 목록이다. 실습 필기는 실습
    블록에, 나머지는 필기 블록에 붙인다 - 같은 제목이 양쪽에 다 있어서
    블록을 안 가르면 절반이 엉뚱한 데로 간다.
    """
    from .matching import dice

    sections = index["sections"]
    results: list[dict] = []

    for lecture in lectures:
        is_practical = "실습" in lecture.title
        want = "실습" if is_practical else "필기"
        candidates = [
            s for s in sections
            if s["block"] == want and s["lectures"] and s["title"]
        ]
        mine = _comparable(lecture.title, is_practical)

        def rate(section: dict) -> float:
            # 순번 문지기. 매칭 때와 같은 이유다 - 어간만으로는
            # "세포의 손상 및 적응 (1)~(2)"와 "(3)"을 가르지 못한다.
            covered = _title_sequences(section["title"])
            if covered and lecture.seq is not None and lecture.seq not in covered:
                return 0.0
            return dice(mine, _comparable(section["title"], False))

        scored = sorted(
            ((rate(s), s) for s in candidates),
            key=lambda pair: -pair[0],
        )
        best_score, best = (scored[0] if scored else (0.0, None))
        runner = scored[1][0] if len(scored) > 1 else 0.0

        confident = bool(best) and (
            best_score >= LINK_CONFIDENT or (best_score >= LINK_PLAUSIBLE
                                             and best_score - runner >= 0.12))
        results.append({
            "key": lecture.key,
            "title": lecture.title,
            "block": want,
            "jokbo_label": best["label"] if best and best_score >= LINK_PLAUSIBLE else None,
            "jokbo_pdf": best["pdf"] if best and best_score >= LINK_PLAUSIBLE else None,
            "jokbo_title": best["title"] if best and best_score >= LINK_PLAUSIBLE else None,
            "score": round(best_score, 2),
            "confident": confident and best_score >= LINK_PLAUSIBLE,
        })
    return results

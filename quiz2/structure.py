"""0.5단계 — 강의록의 구조. **정할 문구를 내고, 쓴 것을 검증한다.**

    python -m quiz2.structure plan  runs/260819_02   # → spawn/structure.md
    #  서브에이전트 하나에게 그 파일을 읽고 그대로 따르라고만 시킨다
    python -m quiz2.structure check runs/260819_02   # 쓴 것을 검증

## 왜 코드가 쓰지 않는가

*"이 페이지가 기출문제인가"*는 의미 판단이다. 정규식으로 문구를 찾던 이전 구현이
실물에서 깨졌다 — `260813_03`은 표지 문구가 "정답"이라 못 잡았고, p34에 "족보"가
있는데도 페이지 앞부분만 읽어서 놓쳤다.

주제 덩어리는 더 그렇다. 슬라이드 47과 48 사이가 경계인지는 세어서 안 나온다.

## 왜 코드가 검증하는가

경계가 틀리면 **뒤가 전부 어긋난다.** 강의록을 족보로 오인하면 clean 채널을 잃고,
족보를 강의록으로 오인하면 기출이 통째로 사라진다. 모델 한 번의 판정에 파이프라인
전체를 걸 수는 없다. 그래서 여기서 재는 특징은 전부 **기계가 셀 수 있는 것**이다.

## 왜 둘이 한 파일에 있나

**규칙이 두 곳에 적히면 갈라진다.** `rules_section`이 검증기가 따지는 것을 그대로
문구에 옮겨 적는다 — 안 적으면 쓰고 나서 걸리고 한 바퀴가 더 돈다. 옮겨 적는 이상
둘은 한 파일에 있어야 한다.

## quiz/에서 옮겨 온 것

`quiz/structure.py`의 알맹이(특징 추출·스캐너·`verify`)를 그대로 가져왔다.
**`quiz/`는 얼어붙은 비교 기준선이므로 그쪽은 안 고친다.** 갈라지는 것이 목적이고,
아래 `verify`의 답안표 예외가 첫 갈림이다.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

import fitz

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

from quiz import timings  # noqa: E402

from . import timings as timings2


# "10.2", "23. 5" - 문항번호와 정답번호를 죽 늘어놓은 답안표.
#
# 줄 전체가 그것뿐이어야 하고 정답은 1~5여야 한다. 느슨하게 잡으면 강의록의
# "1. 2형 콜라겐" 같은 번호 목록이 답안표로 오인된다(실제로 p29에서 3번 걸렸다).
_ANSWER_ROW_RE = re.compile(r"(?m)^\s*\d{1,3}\s*[.)]\s*[1-5]\s*$")

# "2018 1/3/5(전원정답)/1/2" - 연도별 정답을 한 줄에 몰아 쓴 형태.
_ANSWER_YEAR_RE = re.compile(r"20\d{2}\s*[:：]?\s*\d(?:\s*/\s*[\d,()가-힣]+)+")

# 족보 구간임을 알리는 낱말. **페이지 전체 텍스트**에서 찾는다 - 앞부분만 보다가
# p34의 "족보"를 놓친 게 이전 구현의 실패 중 하나였다.
_JOKBO_WORD_RE = re.compile(
    r"(족보|기출|정답|작년\s*(문제|시험)|재작년|이전\s*시험|기말|중간고사)")

# 족보 구간으로 인정하는 최소 길이. 한 장짜리는 강의록의 마무리 슬라이드일 때가 많다.
MIN_JOKBO_PAGES = 2

# 족보 구간의 글자수 중앙값이 강의록의 이 비율보다 낮아야 한다.
MAX_TEXT_RATIO = 0.5


@dataclass
class PageFeature:
    """한 페이지에서 기계가 셀 수 있는 것 전부."""

    slide_no: int
    chars: int              # 인쇄된 텍스트 글자수 (annotation 제외)
    annots: int             # annotation 개수
    answer_rows: int        # 답안 나열 패턴이 걸린 횟수
    jokbo_words: int        # 족보 관련 낱말이 나온 횟수
    image_ratio: float      # 이미지가 덮은 면적 비율. 족보 문항은 대개 큰 이미지다
    clipboard_stamps: int   # 붙여넣은 이미지 수. 필기 경로에서 가장 곧은 족보 신호다


def clipboard_stamp_count(page) -> int:
    """클립보드로 붙여넣은 이미지 수.

    필기자는 족보를 **캡처해서 붙인다.** 그래서 이게 필기 경로에서 가장 곧은
    족보 신호다. 인쇄 텍스트도 답안표도 없는 족보 페이지가 실제로 있고,
    그런 쪽은 이것 말고는 잡을 방법이 없다.

    meddeck의 `_clipboard_image_stamp_count`와 같은 규칙이다.
    """
    count = 0
    try:
        for annot in (page.annots() or ()):
            kind = annot.type[1] if len(annot.type) > 1 else ""
            name = str((annot.info or {}).get("name", "")).lower()
            if kind == "Stamp" and name.startswith("clipboard.image"):
                count += 1
    except Exception:
        return 0
    return count


def page_features(pdf_path: str | Path) -> list[PageFeature]:
    """모델이 읽을 페이지별 수치. 이 함수는 의미 판단을 하지 않는다."""
    features: list[PageFeature] = []
    with fitz.open(str(pdf_path)) as doc:
        for index, page in enumerate(doc, start=1):
            text = page.get_text() or ""
            stamps = clipboard_stamp_count(page)
            try:
                annots = len(list(page.annots() or []))
            except Exception:
                annots = 0
            page_area = abs(page.rect.get_area()) or 1.0
            image_area = 0.0
            try:
                for block in page.get_text("dict").get("blocks", []):
                    if block.get("type") == 1:          # 1 = 이미지 블록
                        x0, y0, x1, y1 = block.get("bbox", (0, 0, 0, 0))
                        image_area += abs((x1 - x0) * (y1 - y0))
            except Exception:
                image_area = 0.0
            features.append(PageFeature(
                slide_no=index,
                chars=len(text.strip()),
                annots=annots,
                answer_rows=len(_ANSWER_ROW_RE.findall(text)) + len(_ANSWER_YEAR_RE.findall(text)),
                jokbo_words=len(_JOKBO_WORD_RE.findall(text)),
                image_ratio=round(min(image_area / page_area, 1.0), 3),
                clipboard_stamps=stamps,
            ))
    return features


# 족보 페이지 사이에 근거가 하나도 없는 쪽이 끼는 일이 있다(문항이 통째로
# 이미지인 경우). 이만큼은 건너뛰고 계속 거슬러 올라간다.
MAX_EVIDENCE_GAP = 1


def _is_jokbo_page(feature: PageFeature) -> bool:
    """이 쪽에 기출이라는 **양성 근거**가 있는가.

    글자가 적다는 것만으로는 안 된다. 강의록 중간의 그림 슬라이드도 글자가 0이다 -
    실제로 `260812_01`의 30쪽이 그랬고, 글자수만 보면 경계가 한 쪽 앞으로 밀렸다.

    붙여넣은 이미지(`clipboard_stamps`)를 함께 보는 이유는, 인쇄 텍스트도 답안표도
    없이 캡처 이미지만 있는 족보 페이지가 실제로 있기 때문이다. 그런 쪽은 이것
    말고는 잡히지 않는다.
    """
    return (feature.answer_rows >= 1
            or feature.jokbo_words >= 1
            or feature.clipboard_stamps >= 1)


def scan_jokbo_start(features: list[PageFeature]) -> int | None:
    """기출 근거가 이어지는 구간의 시작을 **뒤에서부터** 세어 찾는다.

    족보는 문서 꼬리에 붙은 연속 블록이다. 그러니 앞에서 훑으며 "여기서부터
    족보인가"를 묻는 것보다, 마지막 쪽에서 "여기까지 족보인가"를 묻는 편이
    경계의 정의에 맞다.

    **이 값을 모델에게 보여주지 않는다.** 힌트로 넘겼더니 네 강의 연속으로
    모델이 뒤집었고(한 장 늦음·한 장 이름·세 장 이름), 방향이 일정하지 않아
    보정할 수도 없었다. 게다가 힌트에 맞춰 라벨 추출 범위를 좁히는 바람에
    오클루전 후보를 조용히 잃었다.

    지금은 **검증에만** 쓴다 - 모델이 정한 경계가 이 수치와 크게 다르면
    사람이 볼 일이라고 알린다. 판정은 모델이 하고, 코드는 따진다.
    """
    if len(features) < 6:
        return None

    start: int | None = None
    gap = 0
    for feature in reversed(features):
        if _is_jokbo_page(feature):
            start, gap = feature.slide_no, 0
            continue
        if start is None:
            continue                      # 아직 족보 구간에 들어오지도 않았다
        gap += 1
        if gap > MAX_EVIDENCE_GAP:
            break

    if start is None:
        return None
    if len(features) - start + 1 < MIN_JOKBO_PAGES:
        return None
    if start < len(features) * 0.5:
        return None                       # 앞쪽 절반까지 내려가면 뭔가 잘못 읽은 것이다
    return start


@dataclass
class Chunk:
    """강의록 안의 주제 한 덩어리."""

    id: str
    title: str
    slides: list[int]        # [시작, 끝] 두 개
    summary: str = ""


@dataclass
class Structure:
    """모델이 내놓는 판정. `runs/<lecture_id>/structure.json`."""

    lecture_range: list[int]
    jokbo_range: list[int] | None
    jokbo_evidence: str
    chunks: list[Chunk] = field(default_factory=list)
    # 교수의 출제 성향. **0.5단계가 낸다** - 경계를 찾느라 족보 구간을 어차피 전부
    # 읽는 자리여서, 그 읽기를 버리고 1단계가 같은 쪽을 또 읽던 것을 여기로 옮겼다.
    # 이 파일은 세지 않는다(모양이 자유롭다). 1단계 조각들이 읽어 쓴다.
    exam_focus: dict | None = None

    @classmethod
    def load(cls, path: str | Path) -> "Structure":
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(
            lecture_range=list(raw["lecture_range"]),
            jokbo_range=list(raw["jokbo_range"]) if raw.get("jokbo_range") else None,
            jokbo_evidence=raw.get("jokbo_evidence", ""),
            chunks=[Chunk(**c) for c in raw.get("chunks", [])],
            exam_focus=raw.get("exam_focus"),
        )

    def save(self, path: str | Path) -> None:
        Path(path).write_text(
            json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8")


def _median(values: list[int]) -> float:
    return statistics.median(values) if values else 0.0


def verify(structure: Structure, features: list[PageFeature]) -> list[str]:
    """모델의 판정을 수치로 따진다. 빈 목록이면 통과.

    문항 하나하나가 옳은지는 보지 않는다. **경계가 자료의 모양과 맞는지**만 본다.
    """
    problems: list[str] = []
    total = len(features)
    by_no = {f.slide_no: f for f in features}

    start, end = structure.lecture_range
    if not (1 <= start <= end <= total):
        problems.append(f"lecture_range {structure.lecture_range}가 1~{total} 밖이다")
        return problems

    lecture = [by_no[n] for n in range(start, end + 1) if n in by_no]

    if structure.jokbo_range:
        jstart, jend = structure.jokbo_range

        # 외부 족보를 덧붙이면 구간이 필기 밖으로 이어진다. 필기 안쪽(꼬리에 붙은
        # 캡처본)만 특징으로 따지고, 바깥쪽은 별도 파일이라 따질 것이 없다.
        external_tail = jend > total
        jend_checked = min(jend, total)

        if jstart > total:
            # 필기에는 족보 꼬리가 없고 외부 족보만 있는 경우.
            if end != total:
                problems.append(
                    f"필기에 족보 꼬리가 없는데 강의록이 {start}-{end}뿐이다. "
                    f"필기 {total}장 전체여야 한다")
            problems.extend(_verify_chunks(structure, start, end))
            return problems

        if not (1 <= jstart <= jend_checked <= total):
            problems.append(f"jokbo_range {structure.jokbo_range}가 1~{total} 밖이다")
            return problems
        jend = jend_checked
        if jstart <= end:
            problems.append(
                f"강의록({start}-{end})과 족보({jstart}-{jend})가 겹친다")
        if jend - jstart + 1 < MIN_JOKBO_PAGES:
            problems.append(
                f"족보 구간이 {jend - jstart + 1}장뿐이다. "
                "한 장짜리는 강의록 마무리 슬라이드일 때가 많다")
        if jstart < total * 0.5:
            problems.append(
                f"족보 시작 {jstart}가 문서 앞쪽 절반이다. "
                "강의록 본문을 족보로 오인했을 가능성이 크다")

        jokbo = [by_no[n] for n in range(jstart, jend + 1) if n in by_no]

        # 양성 근거: 답안 나열이나 족보 낱말이 구간 안에 최소 한 번은 나와야 한다.
        evidence = sum(f.answer_rows for f in jokbo) + sum(f.jokbo_words for f in jokbo)
        if evidence == 0:
            problems.append(
                f"족보 구간 {jstart}-{jend}에 답안 나열도 족보 낱말도 없다. "
                "정말 기출인지 원본을 확인하라")

        # 음성 근거: 족보는 인쇄 텍스트가 확실히 적어야 한다.
        lecture_median = _median([f.chars for f in lecture])
        jokbo_median = _median([f.chars for f in jokbo])
        if lecture_median and jokbo_median > lecture_median * MAX_TEXT_RATIO:
            problems.append(
                f"족보 구간 글자수 중앙값 {jokbo_median:.0f}가 "
                f"강의록 {lecture_median:.0f}에 비해 높다. 경계가 이르지 않은지 보라")

        # 중앙값만 보면 안 된다. 족보 30-40으로 잘못 잡았을 때 앞의 세 장이
        # 961·441·645자였는데도 중앙값 67로 묻혀 검증을 통과했다.
        if lecture_median:
            # **답안표가 있는 장은 뺀다 (v2에서 갈린 자리).** 이 검사는 경계를 너무
            # 이르게 잡아 강의록 본문이 족보 구간에 남은 것을 잡으려는 건데, 필기자가
            # 족보 장에 출제경향을 길게 타이핑해 두면 헛돈다.
            #
            # `260819_02` s38이 그랬다 — 제목 `2017`, 머리글 `2017 / 9. 4 / 10. 2, 4`,
            # 답안 나열 2줄인 명백한 족보 장인데 581자라 걸렸다. 경계는 옳았다.
            #
            # 답안표를 근거로 쓰는 것은 이미 이 함수가 하고 있다 — 아래 `stragglers`가
            # **강의록 구간에** 답안표가 있으면 족보로 본다. 반대쪽도 같게 맞춘 것이다.
            intruders = [f for f in jokbo
                         if f.chars > lecture_median * MAX_TEXT_RATIO
                         and not f.answer_rows]
            if intruders:
                pages = ", ".join(f"{f.slide_no}({f.chars}자)" for f in intruders[:5])
                problems.append(
                    f"족보 구간 안에 강의록 수준의 본문이 {len(intruders)}장 있다: {pages}. "
                    "경계를 뒤로 물려야 한다")

        if end + 1 != jstart:
            problems.append(
                f"슬라이드 {end + 1}~{jstart - 1}이 어느 구간에도 없다")

        # 반대쪽 실수: 경계를 너무 늦게 잡아 족보 앞부분이 강의록에 남는 경우.
        # 답안표는 강의록에 없다. 있으면 그 페이지는 족보다.
        stragglers = [f for f in lecture if f.answer_rows >= 2]
        if stragglers:
            pages = ", ".join(str(f.slide_no) for f in stragglers[:5])
            problems.append(
                f"강의록 구간에 답안 나열이 있는 페이지가 있다: {pages}. "
                "경계를 앞으로 당겨야 한다")

        # 기계가 뒤에서부터 센 값과 견준다. 모델의 판정이 주인이지만, 크게
        # 어긋나면 둘 중 하나는 틀렸다. 실측에서 차이는 늘 3장 이내였다.
        scanned = scan_jokbo_start(features)
        if scanned is not None and abs(scanned - jstart) > 3:
            problems.append(
                f"기계는 기출 근거가 {scanned}부터 이어진다고 센다. "
                f"네 판정 {jstart}과 {abs(scanned - jstart)}장 차이다. "
                "어느 쪽이 맞는지 원본으로 가려라")
    else:
        # 족보가 없다고 했는데 답안표가 있으면 놓친 것이다.
        tail = [f for f in features if f.slide_no >= total * 0.6]
        rows = sum(f.answer_rows for f in tail)
        if rows >= 3:
            problems.append(
                f"족보가 없다고 했지만 뒤쪽에 답안 나열이 {rows}번 나온다. "
                "다시 보라")

    problems.extend(_verify_chunks(structure, start, end))
    return problems


def _verify_chunks(structure: Structure, start: int, end: int) -> list[str]:
    """주제 덩어리가 강의록을 빠짐없이·겹침없이 덮는지."""
    if not structure.chunks:
        return ["chunks가 비어 있다"]

    problems: list[str] = []
    spans = sorted((c.slides[0], c.slides[1], c.id) for c in structure.chunks)

    for low, high, cid in spans:
        if low > high:
            problems.append(f"chunk {cid}의 범위 [{low}, {high}]가 뒤집혔다")
        if low < start or high > end:
            problems.append(
                f"chunk {cid} [{low}, {high}]가 강의록 {start}-{end} 밖으로 나간다")

    cursor = start
    for low, high, cid in spans:
        if low > cursor:
            problems.append(f"슬라이드 {cursor}~{low - 1}을 덮는 chunk가 없다")
        elif low < cursor:
            problems.append(f"chunk {cid}가 앞 chunk와 겹친다 (슬라이드 {low})")
        cursor = max(cursor, high + 1)
    if cursor <= end:
        problems.append(f"슬라이드 {cursor}~{end}를 덮는 chunk가 없다")

    return problems


# 제목은 통째로, 머리글은 잘라서. 머리글은 경계를 가리키는 데만 쓰므로 앞부분이면
# 충분하고, 전문을 실으면 한 편에 1만 자가 넘는다.
HEAD_MAX = 110

# 조각 하나의 최대 슬라이드 수. **하네스의 Read 상한이 20쪽이다.**
# 조각 PDF를 `pages` 없이 통째로 읽어야 텍스트 레이어가 따라오는데(`chunks.py`),
# 20쪽을 넘기면 그 읽기가 거부되어 1단계가 그림만 보게 된다.
CHUNK_SLIDES_MAX = 20

# 실측 범위. `260819_01` 9조각이 5~14장이었다. 한도가 아니라 관찰이다.
CHUNK_SLIDES_TYPICAL = "5~14"


DO_NOT = """\
## 하지 말 것

근거는 **전부 이 문구 안에 있다.** 아래 하나를 빼고는 찾으러 가지 마라.

- **`outline.json`·`page_features.json`을 열지 마라.** 표로 아래에 실려 있다
- **강의록 본문을 통독하지 마라.** 주제 경계는 제목 줄로 보인다.
  본문이 필요한 것은 카드를 만드는 1단계의 몫이고, 여기는 경계만 정한다
- **`quiz/structure.py`를 읽거나 돌리지 마라.** 검증은 네가 쓴 뒤에 코드가 한다.
  검증기가 무엇을 보는지는 아래 「검증기가 따지는 것」에 전부 옮겨 놓았다
- **쓴 뒤에 고쳐 쓰지 마라.** 한 번에 완성해서 한 번만 써라
"""


def _text(value) -> str:
    return str(value or "").strip()


def load_features(run_dir: Path, prep: dict) -> list[PageFeature]:
    path = run_dir / "page_features.json"
    if path.exists():
        return [PageFeature(**f) for f in json.loads(path.read_text(encoding="utf-8"))]
    raise SystemExit(f"{path}가 없다. prep.py를 먼저 돌려라")


def outline_table(run_dir: Path, prep: dict) -> str:
    """슬라이드마다 제목 한 줄. **주제 경계는 여기서 보인다.**

    `260819_01`에서는 족보 경계까지 여기서 보였다 — s68의 제목이
    `2022년 족보 - 강경훈 교수님 출제`였다. 늘 그렇지는 않으므로
    (`260813_03`은 표지 문구가 "정답"이었다) 수치 표와 함께 본다.
    """
    # `prep["outline_path"]`는 저장소 뿌리 기준 상대경로라 다른 데서 부르면
    # 못 찾는다. run_dir 안을 먼저 본다.
    path = run_dir / "outline.json"
    if not path.exists():
        path = Path(_text(prep.get("outline_path")))
    if not path.exists():
        return "## 슬라이드 제목\n\n`outline.json`이 없다. 원본을 직접 봐야 한다."

    entries = json.loads(path.read_text(encoding="utf-8"))
    lines = ["| # | 제목 | 첫 줄 |", "|---|---|---|"]
    for e in entries:
        title = _text(e.get("title")).replace("|", "/")
        head = _text(e.get("head")).replace("|", "/")
        if len(head) > HEAD_MAX:
            head = head[:HEAD_MAX] + "…"
        lines.append(f"| {e.get('slide_no')} | {title} | {head} |")
    return ("## 슬라이드 제목과 첫 줄\n\n"
            "주제 덩어리를 가르는 근거는 이 표다.\n\n" + "\n".join(lines))


def feature_table(features: list[PageFeature]) -> str:
    """기계가 센 것. **족보 경계는 여기서 보인다.**"""
    lines = [
        "## 슬라이드마다 기계가 센 것",
        "",
        "    글자    인쇄된 텍스트 글자수. 족보 캡처는 이 값이 낮다",
        "    필기    주석(annotation) 개수",
        "    답안    `12. 3` 꼴의 답안 나열 줄 수. **강의록에는 없다**",
        "    족보말  족보·기출·정답·기말 같은 낱말이 나온 횟수",
        "    그림    페이지에서 그림이 차지하는 넓이 비율",
        "",
        "| # | 글자 | 필기 | 답안 | 족보말 | 그림 |",
        "|---|---|---|---|---|---|",
    ]
    for f in features:
        lines.append(f"| {f.slide_no} | {f.chars} | {f.annots} | {f.answer_rows} "
                     f"| {f.jokbo_words} | {f.image_ratio:.2f} |")
    return "\n".join(lines)


def machine_hint(features: list[PageFeature], prep: dict) -> str:
    """기계의 짐작. **판정이 아니다 — 어긋나면 네가 이기고, 근거를 적어라.**"""
    total = len(features)
    scanned = scan_jokbo_start(features)
    lines = ["## 기계의 짐작 (판정이 아니다)", ""]
    if scanned is None:
        lines.append("정규식 스캐너는 **족보 꼬리를 못 찾았다.** 없을 수도 있고, "
                     "문구가 낯설어 놓쳤을 수도 있다. 위 두 표로 직접 가려라.")
    else:
        lines.append(f"정규식 스캐너는 기출 근거가 **필기 {scanned}쪽부터** 이어진다고 센다.")
        lines.append("")
        lines.append("이건 뒤에서부터 답안표와 족보 낱말을 세어 본 값일 뿐이다. "
                     "`260813_03`에서는 이 방식이 통째로 틀렸다 — 표지 문구가 "
                     "'정답'이라 못 잡았고, 문항 본문이 이미지라 빈 페이지 폴백도 "
                     "안 걸렸다. **네 판정이 주인이다.**")
        lines.append("")
        lines.append(f"다만 검증기가 둘의 차이를 잰다. **{scanned}과 3장 넘게 "
                     "차이나면 검증이 멈춘다** — 그때는 원본을 보고 어느 쪽이 맞는지 "
                     "가려서 `jokbo_evidence`에 적어라.")

    external = prep.get("external_jokbo_range")
    if external:
        lo, hi = int(external[0]), int(external[1])
        lines += [
            "",
            f"### 외부 족보가 붙어 있다 — 슬라이드 {lo}~{hi}",
            "",
            f"필기는 {total}쪽이고 거기에 별도 족보 PDF {hi - lo + 1}장을 이어 붙여 "
            f"자료 전체가 {prep.get('total_slides')}장이 됐다.",
            "",
            f"**`jokbo_range`는 한 구간으로 적는다** — 필기 꼬리의 족보가 시작하는 "
            f"쪽부터 {hi}까지다. 필기에 꼬리가 없으면 {lo}부터다. 검증기는 필기 "
            f"안쪽({total}쪽까지)만 수치로 따지고 바깥쪽은 별도 파일이라 안 따진다.",
        ]
    return "\n".join(lines)


def read_plan(prep: dict, features: list[PageFeature]) -> str:
    """남는 읽기 하나. 필기 꼬리 족보는 캡처 이미지라 글자가 안 잡힌다."""
    scanned = scan_jokbo_start(features)
    annotated = prep.get("annotated_pdf")
    if not annotated:
        return ""
    total = len(features)
    lo = max(1, (scanned or total) - 3)
    return (
        "## 눈으로 볼 곳 하나\n\n"
        f"필기 꼬리에 붙은 족보는 **캡처 이미지**라 글자가 거의 안 잡힌다 — 위 표에서 "
        f"그 구간의 글자수가 수십 자로 떨어지는 것이 그 때문이다. 그래서 여기만 "
        f"직접 본다.\n\n"
        f"    Read(\"{Path(annotated).as_posix()}\", pages=\"{lo}-{total}\")\n\n"
        "경계가 정말 거기인지 확인하고, 그 김에 **문항을 읽어 `exam_focus`를 쓴다.** "
        "이 읽기를 여기서 한 번 하는 것이 1단계 조각들이 각자 다시 읽는 것보다 싸다."
    )


def rules_section(features: list[PageFeature]) -> str:
    """검증기가 실제로 따지는 것. `quiz/structure.py`의 `verify`를 옮겼다.

    **여기 적힌 것과 코드가 어긋나면 코드가 주인이다.** 검증이 멈추면 이 절을
    먼저 의심하라 — 규칙이 바뀌었는데 이 문구가 안 따라온 것일 수 있다.
    """
    total = len(features)
    return f"""\
## 검증기가 따지는 것

네가 쓰면 `quiz/structure.py`가 수치로 따진다. 하나라도 걸리면 멈추고 다시 시킨다.
**미리 맞춰서 써라.**

### 경계

- `lecture_range`는 1~{total} 안에 있어야 한다
- 강의록과 족보가 **겹치면 안 되고, 사이가 비어도 안 된다.**
  `lecture_range`의 끝 + 1 = `jokbo_range`의 시작
- 족보 구간은 **2장 이상**이어야 한다. 한 장짜리는 강의록 마무리 슬라이드일 때가 많다
- 족보 시작은 문서 **뒤쪽 절반**({total // 2}쪽 이후)이어야 한다
- 족보 구간에 **답안 나열이나 족보 낱말이 최소 한 번**은 나와야 한다
- 족보 구간의 글자수 중앙값이 강의록 중앙값의 **절반을 넘으면** 안 된다.
  구간 안에 강의록 수준 본문이 **한 장이라도** 섞여 있어도 걸린다
- 강의록 구간에 **답안 나열이 2줄 이상인 페이지**가 있으면 걸린다.
  답안표는 강의록에 없다 — 있으면 그 페이지는 족보다
- 족보가 없다고 적었는데 뒤쪽 40%에 답안 나열이 3번 이상 나오면 걸린다

### 주제 덩어리

- `chunks`가 `lecture_range`를 **빠짐없이·겹침없이** 덮어야 한다.
  첫 조각은 `lecture_range`의 시작에서, 마지막 조각은 그 끝에서 맺는다
- 조각 하나는 **{CHUNK_SLIDES_MAX}장을 넘기지 마라.** 1단계가 조각 PDF를 통째로
  읽어야 텍스트 레이어가 따라오는데, {CHUNK_SLIDES_MAX}쪽을 넘으면 그 읽기가
  거부되어 그림만 보게 된다
- 실측에서는 조각당 {CHUNK_SLIDES_TYPICAL}장이었다. 한도가 아니라 관찰이다 —
  **주제가 가르는 대로 갈라라.** 장수를 맞추려고 주제를 쪼개지 마라
- 표지·학습목표·참고자료도 어느 조각엔가 들어가야 한다. 덮지 않으면 검증이 멈춘다.
  1단계가 거기서 카드를 안 내는 것은 그쪽에서 판단한다"""


def output_section(run_dir: Path) -> str:
    out = run_dir / "structure.json"
    return f"""\
## 출력

`{out}`에 JSON 하나로 쓴다. 그것 말고는 아무 파일도 만들거나 고치지 않는다.

```json
{{
  "lecture_id": "{run_dir.name}",
  "lecture_range": [1, 67],
  "jokbo_range": [68, 89],
  "jokbo_evidence": "왜 거기가 경계인지. 슬라이드 번호를 대고 무엇이 보였는지 적는다.",
  "chunks": [
    {{"id": "c01", "title": "표지와 강의 개요", "slides": [1, 5],
     "summary": "이 덩어리가 무엇을 다루는지 한 줄"}}
  ],
  "exam_focus": {{"...": "모양은 자유다"}}
}}
```

- `id`는 `c01`부터 이어 붙인다. 1단계가 이 이름으로 조각 PDF와 결과 파일을 만든다
- **`jokbo_evidence`는 짧게 쓰지 마라.** 다음에 이 편을 다시 볼 사람이
  경계를 의심할 때 읽는 유일한 글이다. 무엇이 어느 쪽에서 보였는지 대라
- `jokbo_range`는 족보가 없으면 `null`로 둔다
- `exam_focus`는 **1단계 조각 전부가 읽는다.** 어느 해에 어느 교수가 무엇을
  물었는지, 어느 선지가 어떻게 뒤집혔는지가 여기 있으면 조각이 족보를 다시
  읽지 않는다. 모양은 정해두지 않았다 — 세지 않고 그대로 넘긴다"""


def spawn_prompt(run_dir: str | Path, *, with_jokbo_text: bool = True) -> str:
    run_dir = Path(run_dir)
    prep = json.loads((run_dir / "prep.json").read_text(encoding="utf-8"))
    features = load_features(run_dir, prep)
    total = len(features)

    parts = [
        f"# 0.5단계 — `{prep.get('lecture_id')}` 「{prep.get('lecture_title')}」의 구조를 정한다",
        (f"필기 {total}쪽짜리 강의록이다. 어디까지가 강의록이고 어디부터가 족보인지, "
         f"그리고 강의록을 어떤 주제 덩어리로 가를지를 정한다.\n\n"
         f"**이 판정 하나에 뒤가 전부 걸린다.** 강의록을 족보로 오인하면 clean 채널을 "
         f"잃고, 족보를 강의록으로 오인하면 기출이 통째로 사라진다."),
        outline_table(run_dir, prep),
        feature_table(features),
        machine_hint(features, prep),
        read_plan(prep, features),
        rules_section(features),
    ]

    jokbo_file = run_dir / "jokbo_text.md"
    if with_jokbo_text and jokbo_file.exists():
        parts.append(
            "## 외부 족보 원문\n\n"
            "`exam_focus`를 쓰는 데 쓴다. 필기 꼬리의 족보는 위 「눈으로 볼 곳」에서 "
            "따로 본다 — 둘은 서로를 대체하지 않는다.\n\n"
            f"```\n{jokbo_file.read_text(encoding='utf-8').strip()}\n```"
        )

    parts.append(DO_NOT)
    parts.append(output_section(run_dir))
    # 일꾼이 제 끝을 찍는다 (`quiz2/timings.py` ③). 0.5는 하나뿐이라 라벨이 없다.
    parts.append(timings2.stamp_note(run_dir, "0.5-write", ""))
    return "\n\n".join(p.strip() for p in parts if p and p.strip())


def build(run_dir: str | Path, *, with_jokbo_text: bool = True) -> dict:
    run_dir = Path(run_dir)
    text = spawn_prompt(run_dir, with_jokbo_text=with_jokbo_text)
    out_dir = run_dir / "spawn"
    out_dir.mkdir(parents=True, exist_ok=True)
    spawn_file = out_dir / "structure.md"
    spawn_file.write_text(text, encoding="utf-8")
    return {
        "spawn_prompt": str(spawn_file),
        "result": str(run_dir / "structure.json"),
        "chars": len(text),
        "approx_tokens": len(text) // 2,
        "jokbo_text_attached": with_jokbo_text and (run_dir / "jokbo_text.md").exists(),
    }


def _check_cli(run_dir: Path) -> int:
    """쓴 것을 검증한다. `quiz/structure.py`의 CLI를 옮겼다."""
    structure_path = run_dir / "structure.json"
    if not structure_path.exists():
        print(f"[structure] {structure_path}가 없다. plan부터 돌려라")
        return 2

    features_path = run_dir / "page_features.json"
    if features_path.exists():
        raw = json.loads(features_path.read_text(encoding="utf-8"))
        features = [PageFeature(**f) for f in raw]
    else:
        prep = json.loads((run_dir / "prep.json").read_text(encoding="utf-8"))
        features = page_features(prep["source_pdf"])

    structure = Structure.load(structure_path)
    problems = verify(structure, features)

    lo, hi = structure.lecture_range
    jokbo = (f"{structure.jokbo_range[0]}-{structure.jokbo_range[1]}"
             if structure.jokbo_range else "없음")
    print(f"[structure/check] {run_dir.name}")
    print(f"  강의록 {lo}-{hi} / 족보 {jokbo} / 주제 {len(structure.chunks)}덩어리")
    for chunk in structure.chunks:
        print(f"    {chunk.id} [{chunk.slides[0]:>3}-{chunk.slides[1]:>3}] {chunk.title}")
    if structure.exam_focus:
        size = len(json.dumps(structure.exam_focus, ensure_ascii=False))
        print(f"  exam_focus 있음 ({size}자)")
    elif structure.jokbo_range:
        print("  ⚠ 족보 구간이 있는데 exam_focus가 비었다 — 1단계 조각들이 족보를 "
              "각자 다시 읽게 된다")

    if problems:
        print(f"\n  검증 실패 {len(problems)}건 — 0.5단계를 다시 시켜라")
        for problem in problems:
            print(f"    ✗ {problem}")
        return 1
    print("\n  검증 통과")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="0.5단계: 구조를 정하고 검증한다")
    parser.add_argument("stage", choices=["plan", "check"])
    parser.add_argument("run_dir")
    parser.add_argument("--no-jokbo-text", action="store_true",
                        help="plan: 외부 족보 원문을 안 붙인다 (exam_focus가 얕아진다)")
    args = parser.parse_args()
    run_dir = Path(args.run_dir)

    if args.stage == "check":
        with timings.stage(run_dir, "0.5-check"):
            return _check_cli(run_dir)

    with timings.stage(run_dir, "0.5-plan"):
        row = build(run_dir, with_jokbo_text=not args.no_jokbo_text)
    print(f"[structure/plan] {row['spawn_prompt']}")
    print(f"  {row['chars']:,}자 (대략 {row['approx_tokens']:,}토큰)"
          + ("  · 족보 원문 붙임" if row["jokbo_text_attached"] else ""))
    print(timings2.spawn_note(run_dir, "0.5-write", [], what="구조 일꾼"))
    print(f"\n  → {row['result']}")
    print(f"  쓴 뒤 검증:  python -m quiz2.structure check {run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

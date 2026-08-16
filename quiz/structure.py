"""강의록의 구조 — 족보 경계와 주제 덩어리.

## 왜 모델이 정하는가

"이 페이지가 기출문제인가"는 **의미 판단**이다. 이 저장소의 역할 경계에 따르면
그건 모델의 일이고 코드의 일이 아니다. 이전 구현은 코드가 문구 몇 개를 정규식으로
찾는 방식이었고 실물에서 이렇게 깨졌다.

    [260813_03] 족보 33~40쪽인데 표지 문구가 "정답"이라 못 잡음
                p34에 "족보"가 있는데도 못 봄 - 페이지 앞부분만 읽어서
                문항 본문이 annotation 이미지라 "빈 페이지" 폴백도 안 걸림

문구는 필기자마다 다르고, 앞으로도 계속 다를 것이다. 규칙을 늘리는 대신 판단을
넘긴다.

## 왜 코드가 검증하는가

경계가 틀리면 **뒤가 전부 어긋난다.** 강의록을 족보로 오인하면 clean 채널을 잃고,
족보를 강의록으로 오인하면 기출이 통째로 사라진다. 모델 한 번의 판정에 파이프라인
전체를 걸 수는 없다.

그래서 여기서 재는 특징은 전부 **기계가 셀 수 있는 것**이다. 아래 숫자는 병리학
2026 15편에서 실제로 뽑았다.

    강의록 구간   글자 200~900   annotation 있음   답안 나열 없음
    족보 구간     글자 0~150     annotation 많음   답안 나열 있음

검증이 실패하면 조용히 넘기지 않고 멈춘다.
"""

from __future__ import annotations

import json
import re
import statistics
from dataclasses import asdict, dataclass, field
from pathlib import Path

import fitz

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


def suggest_jokbo_start(features: list[PageFeature]) -> int | None:
    """족보가 시작되는 쪽을 짐작한다. **뒤에서부터** 거슬러 올라간다.

    족보는 문서 꼬리에 붙은 연속 블록이다. 그러니 앞에서 훑으며 "여기서부터
    족보인가"를 묻는 것보다, 마지막 쪽에서 "여기까지 족보인가"를 묻는 편이
    경계의 정의에 맞다. 앞에서 훑는 방식은 본문의 숫자·낱말에 걸려 번번이
    엉뚱한 데서 멈췄다.

    어디까지나 힌트다. 경계를 정하는 건 0.5단계의 모델이다.
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

    @classmethod
    def load(cls, path: str | Path) -> "Structure":
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(
            lecture_range=list(raw["lecture_range"]),
            jokbo_range=list(raw["jokbo_range"]) if raw.get("jokbo_range") else None,
            jokbo_evidence=raw.get("jokbo_evidence", ""),
            chunks=[Chunk(**c) for c in raw.get("chunks", [])],
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

        # 외부 족보: 별도 PDF라 필기의 페이지 특징에 잡히지 않는다. 경계가 파일
        # 경계이므로 따질 것이 없다 - 강의록이 필기 전체를 덮는지만 본다.
        if jstart > total:
            if end != total:
                problems.append(
                    f"외부 족보를 쓰는데 강의록이 {start}-{end}뿐이다. "
                    f"필기 {total}장 전체여야 한다")
            problems.extend(_verify_chunks(structure, start, end))
            return problems

        if not (1 <= jstart <= jend <= total):
            problems.append(f"jokbo_range {structure.jokbo_range}가 1~{total} 밖이다")
            return problems
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
            intruders = [f for f in jokbo if f.chars > lecture_median * MAX_TEXT_RATIO]
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


def main() -> int:
    import argparse
    import sys

    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass

    parser = argparse.ArgumentParser(
        description="퀴즈 파이프라인 0.5단계 검증: 모델이 정한 구조가 자료와 맞는가")
    parser.add_argument("run_dir", help="runs/<lecture_id>")
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    structure_path = run_dir / "structure.json"
    if not structure_path.exists():
        print(f"[structure] {structure_path}가 없다. 0.5단계를 먼저 돌려라")
        return 2

    features_path = run_dir / "page_features.json"
    if features_path.exists():
        raw = json.loads(features_path.read_text(encoding="utf-8"))
        features = [PageFeature(**f) for f in raw]
    else:
        # 옛 run 디렉터리에는 없다. 원본에서 다시 뽑는다.
        prep = json.loads((run_dir / "prep.json").read_text(encoding="utf-8"))
        features = page_features(prep["source_pdf"])

    structure = Structure.load(structure_path)
    problems = verify(structure, features)

    lo, hi = structure.lecture_range
    jokbo = f"{structure.jokbo_range[0]}-{structure.jokbo_range[1]}" if structure.jokbo_range else "없음"
    print(f"[structure] {run_dir.name}")
    print(f"  강의록 {lo}-{hi} / 족보 {jokbo} / 주제 {len(structure.chunks)}덩어리")
    if structure.jokbo_evidence:
        print(f"  근거: {structure.jokbo_evidence}")
    for chunk in structure.chunks:
        print(f"    {chunk.id} [{chunk.slides[0]:>3}-{chunk.slides[1]:>3}] {chunk.title}")

    if problems:
        print(f"\n  검증 실패 {len(problems)}건 — 0.5단계를 다시 시켜라")
        for problem in problems:
            print(f"    ✗ {problem}")
        return 1

    print("\n  검증 통과")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

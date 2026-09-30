"""올해 강의를 작년 강의에 붙인다.

이건 캘린더 편의 기능이 아니라 **Main-Quiz의 전제 조건**이다. 올해 필기에도 족보가
붙어 있지만 학기 중에는 아직 없는 편이 있고, 작년 필기에는 정리가 끝난 족보가
확실히 들어 있다. 어느 쪽이든 "이 강의의 작년 판"을 알아야 출제 성향을 읽는다.

## 무엇으로 붙이나

교시 슬롯은 **연도를 넘으면 못 쓴다.** 같은 강의가 2025년엔 `250819_01`이고
2026년엔 `260814_05`다. 날짜도 마찬가지다. 남는 건 제목과 교수다.

    제목 어간 유사도(Dice bigram)   ← 주 신호
    순번 일치                       ← 문지기. 다르면 무조건 다른 강의다
    교수 일치                       ← 가산점. 교수가 바뀌는 해가 있어 필수는 아니다
                                      (병리학 소개: 2025 정두현 → 2026 정경천)

순번을 문지기로 두는 이유는 어간만으로는 "조직 재생 및 수복(1)"과 "(2)"를
가르지 못하기 때문이다. 둘의 어간은 글자 하나 안 틀리고 같다.
"""

from __future__ import annotations

from dataclasses import dataclass

from .filenames import LectureFile

# 교수까지 같으면 이만큼 얹는다. 어간이 엇비슷한 후보 둘을 가를 정도면 충분하고,
# 교수가 바뀐 강의를 혼자 힘으로 붙일 만큼 크면 안 된다.
PROFESSOR_BONUS = 0.10

# 한쪽만 순번을 가진 경우. 다른 강의일 수도 있으므로 조금 깎되 막지는 않는다.
SEQ_ASYMMETRY_PENALTY = 0.10

CONFIDENT_SCORE = 0.75      # 이 위는 그냥 붙인다
CONFIDENT_MARGIN = 0.15     # 2등과 이만큼 벌어졌으면 낮아도 붙인다
MARGIN_FLOOR = 0.60         # 다만 격차만으로 확정하려면 이 점수는 넘어야 한다
PLAUSIBLE_SCORE = 0.45      # 이 아래는 후보로도 보여주지 않는다

# 바닥을 두는 이유: 경쟁자가 없다는 건 짝이 맞다는 뜻이 아니다. 조직학 2026이
# 강의를 재편성해 "혈구와 조혈, 혈관"이 작년 "혈구와 조혈"과 "혈관, 신경조직"
# 둘에 걸쳤는데, 경쟁자가 없다는 이유로 0.50짜리가 확정으로 올라갔다.


def _bigrams(text: str) -> set[str]:
    return {text[i:i + 2] for i in range(len(text) - 1)}


def dice(left: str, right: str) -> float:
    """글자 bigram Dice 계수. 항상 0..1."""
    if not left or not right:
        return 0.0
    if left == right:
        return 1.0
    a, b = _bigrams(left), _bigrams(right)
    if not a or not b:
        return 0.0
    return 2 * len(a & b) / (len(a) + len(b))


def score(this_year: LectureFile, prev_year: LectureFile) -> float:
    """0이면 후보가 아니다."""
    if this_year.seq is not None and prev_year.seq is not None:
        if this_year.seq != prev_year.seq:
            return 0.0                      # 문지기: 다른 순번은 다른 강의다

    value = dice(this_year.stem, prev_year.stem)
    if value <= 0:
        return 0.0

    if (this_year.seq is None) != (prev_year.seq is None):
        value -= SEQ_ASYMMETRY_PENALTY

    if set(this_year.professors) & set(prev_year.professors):
        value += PROFESSOR_BONUS

    return max(0.0, min(1.0, value))


@dataclass
class Match:
    this_year: LectureFile
    prev_year: LectureFile | None
    score: float
    margin: float                 # 1등과 2등의 차이
    runner_up: LectureFile | None

    @property
    def confident(self) -> bool:
        if self.prev_year is None:
            return False
        if self.score >= CONFIDENT_SCORE:
            return True
        return self.margin >= CONFIDENT_MARGIN and self.score >= MARGIN_FLOOR

    @property
    def status(self) -> str:
        if self.prev_year is None:
            return "없음"
        return "확정" if self.confident else "확인"


def match_years(this_year: list[LectureFile], prev_year: list[LectureFile]) -> list[Match]:
    """올해 강의마다 작년 짝을 하나씩 붙인다. 작년 강의는 한 번만 쓰인다.

    점수가 높은 짝부터 확정하는 탐욕 배정이다. 최적 배정(헝가리안)까지 갈 이유가
    없다 - 순번 문지기가 진짜 경쟁을 대부분 없애서, 남는 경쟁은 사람이 봐야 하는
    종류다.
    """
    pairs = [
        (score(this, prev), this, prev)
        for this in this_year
        for prev in prev_year
    ]
    pairs = [p for p in pairs if p[0] >= PLAUSIBLE_SCORE]
    pairs.sort(key=lambda p: (-p[0], p[1].uid, p[2].uid))

    # 각 올해 강의의 후보를 점수순으로 모아 둔다 (2등을 알아야 margin이 나온다).
    ranked: dict[str, list[tuple[float, LectureFile]]] = {}
    for value, this, prev in pairs:
        ranked.setdefault(this.uid, []).append((value, prev))

    taken: set[str] = set()
    matches: list[Match] = []
    assigned: dict[str, tuple[float, LectureFile]] = {}

    for value, this, prev in pairs:
        if this.uid in assigned or prev.uid in taken:
            continue
        assigned[this.uid] = (value, prev)
        taken.add(prev.uid)

    for this in this_year:
        candidates = ranked.get(this.uid, [])
        chosen = assigned.get(this.uid)
        if chosen is None:
            matches.append(Match(this, None, 0.0, 0.0, None))
            continue
        value, prev = chosen
        others = [c for c in candidates if c[1].uid != prev.uid]
        runner_up = others[0][1] if others else None
        margin = value - (others[0][0] if others else 0.0)
        matches.append(Match(this, prev, value, margin, runner_up))

    return matches


def match_with_confirmed(this_year: list[LectureFile], prev_year: list[LectureFile],
                         confirmed: dict[str, str]) -> list[Match]:
    """사람이 확인한 짝을 먼저 앉히고, 나머지를 `match_years` 로 붙인다.

    `confirmed` 는 `runs/_pairs/<과목>.json` 이다 — `{올해 run_id: 작년 run_id 또는
    파일 어간}`. `_` 로 시작하는 키는 주석이다.

    **2026-09-30 까지 이 짝은 올해 필기가 없는 칸에만 먹었다**(`ahead.plan`). 필기가
    올라오는 순간 자동 짝으로 바뀌어서, 사람이 본문까지 열어 확인한 짝이 조용히
    사라졌다 — 약리학 「약물의 이해 소개(조정현)」가 작년 「약리학 소개(예상규)」를
    잃고 사이트에 작년 필기가 안 붙었다. 적어 둔 짝은 필기가 있든 없든 짝이다.
    """
    by_key: dict[str, LectureFile | None] = {}
    for item in prev_year:
        # 한 교시에 작년 강의가 둘이면 키로는 못 가린다. 그때는 어간으로 적는다.
        by_key[item.key] = None if item.key in by_key else item
    by_stem = {item.path.stem: item for item in prev_year}

    fixed: list[Match] = []
    taken: set[str] = set()
    rest: list[LectureFile] = []
    for this in this_year:
        wanted = confirmed.get(this.key, "") if not this.key.startswith("_") else ""
        prev = (by_key.get(wanted) or by_stem.get(wanted)) if wanted else None
        if prev is None or prev.uid in taken:
            rest.append(this)
            continue
        fixed.append(Match(this, prev, 1.0, 1.0, None))
        taken.add(prev.uid)
    pool = [item for item in prev_year if item.uid not in taken]
    return fixed + match_years(rest, pool)

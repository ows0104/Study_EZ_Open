"""망각곡선 일정. **안키의 SM-2를 그대로 옮겼다.**

웹 풀이가 한 번 훑는 자리였던 것을 2026-09-18 관리자 지시로 뒤집었다 —
「웹 퀴즈를 안키처럼, 망각곡선에 기반해서」. 그 전까지 반복은 apkg 를 받아 간
사람의 안키가 들었고, 웹에는 카드마다 `correct` 불리언 하나가 남았다.

    전:  카드 한 장 = 맞았다/틀렸다 한 번
    후:  카드 한 장 = 상태 + 다음에 나올 때 + 쉬움도 + 반복/실패 횟수

**바퀴를 새로 깎지 않았다.** SM-2 는 40년 된 것이고 안키가 20년을 돌렸다.
간격을 우리 감으로 정하면 그 감을 확인할 방법이 없다 — 한 학기에 한 사람이
쓰는 제품에서는 A/B 로 잴 표본이 안 모인다. 그래서 상수까지 안키 기본값이고,
아래 주석은 **어디를 일부러 달리했는지**만 적는다.

## 여기에 DB 도 시계도 없다

`now` 를 받아서 새 `Card` 를 돌려주는 순수 함수뿐이다. 그래야 두 가지가 된다.

    ① 검사가 시각을 손으로 밀어 가며 사다리 전체를 잰다  (`tests/test_srs.py`)
    ② `reveal` 이 저장하지 않고 네 버튼의 결과를 미리 잰다  (`preview`)

②가 없으면 「이 버튼을 누르면 언제 다시 나오나」를 화면이 자기 계산으로 적게
되고, 그러면 일정 계산이 파이썬과 타입스크립트 두 곳에 산다.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, timedelta

# 복습의 하루가 바뀌는 시각. **안키 기본값이 새벽 4시이고 이유가 우리에게도 같다** —
# 자정을 넘겨 공부하는 사람의 「어제 몫」이 책상에 앉은 채로 사라지면 안 된다.
#
# **`prequiz_jobs.QUEUE_DAY_START_HOUR`(새벽 5시)와 일부러 안 묶었다.** 그것은
# 일감 큐가 "오늘 자동으로 몇 편을 세웠나"를 세는 자다. 한 상수로 묶으면 새벽에
# 복습하고 싶다는 요구가 러너의 하루 상한을 움직인다.
DAY_START_HOUR = 4
KST_OFFSET = timedelta(hours=9)

# 카드가 있을 수 있는 자리 넷. 안키와 같은 이름이다.
STATE_NEW = "new"  # 한 번도 안 찍었다
STATE_LEARNING = "learning"  # 익히는 중. 분 단위로 다시 나온다
STATE_REVIEW = "review"  # 익었다. 날 단위로 나온다
STATE_RELEARN = "relearn"  # 익었던 것을 잊었다. 다시 분 단위로

#: 누를 수 있는 넷. 순서가 화면의 버튼 순서다.
GRADES = ("again", "hard", "good", "easy")

# 익히는 단계. 안키 기본값(1분·10분)이다. 웹 한 세션이 20~40장이라 "1분 뒤"는
# 실제로 "몇 장 뒤"가 된다 — 그것이 Again 을 누른 카드가 그 자리에서 다시
# 돌아오게 하는 장치다.
LEARNING_STEPS = (60, 600)
RELEARN_STEPS = (600,)

GRADUATING_INTERVAL = 1  # 익히기를 마치면 하루 뒤
EASY_INTERVAL = 4  # 익히는 중에 Easy 를 누르면 나흘 뒤

STARTING_EASE = 2.5
MIN_EASE = 1.3
#: 누른 것이 쉬움도를 얼마나 움직이나. SM-2 의 값이다.
EASE_DELTA = {"again": -0.20, "hard": -0.15, "good": 0.0, "easy": 0.15}

HARD_FACTOR = 1.2  # Hard 는 쉬움도를 안 쓰고 이것으로만 늘린다
EASY_BONUS = 1.3  # Easy 는 쉬움도에 이만큼을 더 곱한다

# 잊은 카드의 간격을 얼마나 남기나. 안키 기본이 0% 라 하루로 떨어진다.
LAPSE_FACTOR = 0.0
MIN_REVIEW_INTERVAL = 1

# **안키 기본값(36500일)을 안 쓴다.** 한 학기짜리 제품에서 백 년 뒤 일정은
# 「다시 안 나온다」와 같은 말이고, 화면에 적으면 사람이 안 믿는다. 한 해를
# 넘기는 일정은 여기서 자른다.
MAX_INTERVAL = 365


@dataclass(frozen=True)
class Card:
    """일정 쪽에서 본 카드 한 장. `_Attempt` 의 칼럼과 이름까지 같다."""

    state: str = STATE_NEW
    #: 익히는 단계의 몇 번째인가. `state` 가 review 면 뜻이 없다.
    step: int = 0
    #: 익은 카드의 간격. 날 단위 정수다 — 안키가 그렇고, 실수로 두면 표에
    #: 3.0000000001 같은 값이 남는다.
    interval_days: int = 0
    ease: float = STARTING_EASE
    reps: int = 0
    lapses: int = 0
    due_at: datetime | None = None


def day_start(when: datetime) -> datetime:
    """`when` 이 속한 복습 하루의 시작. 한국 시각 새벽 `DAY_START_HOUR` 다."""
    kst = when + KST_OFFSET
    start = (kst - timedelta(hours=DAY_START_HOUR)).replace(
        hour=DAY_START_HOUR, minute=0, second=0, microsecond=0
    )
    return start - KST_OFFSET


def day_key(when: datetime) -> date:
    """`when` 이 속한 복습 하루를 **한국 시각의 날짜**로. 표의 열쇠로 쓴다.

    `day_start` 의 값을 그대로 `.date()` 하면 안 된다 — 그것은 UTC 시각이라
    새벽 4시(KST)는 전날 19시(UTC)이고, 날짜가 하루 어긋난다.
    """
    return (day_start(when) + KST_OFFSET).date()


def _due_in_days(now: datetime, days: int) -> datetime:
    """`days` 일 뒤의 하루가 열리는 시각.

    **날 단위로 재는 이유가 여기 있다.** 시각으로 재면 밤 11시에 찍은 카드가
    다음날 밤 11시에야 열린다 — 저녁 9시에 앉은 사람에게 화면은 「0장」을
    보여 주고, 그 0은 "다 했다"로 읽힌다. 안키가 날로 세는 것도 이 때문이다.
    """
    return day_start(now) + timedelta(days=days)


def _steps(state: str) -> tuple[int, ...]:
    return RELEARN_STEPS if state == STATE_RELEARN else LEARNING_STEPS


def _clamp_ease(ease: float, grade: str) -> float:
    return max(MIN_EASE, ease + EASE_DELTA[grade])


def _graduate(card: Card, now: datetime, interval_days: int) -> Card:
    interval = min(MAX_INTERVAL, max(MIN_REVIEW_INTERVAL, interval_days))
    return replace(
        card,
        state=STATE_REVIEW,
        step=0,
        interval_days=interval,
        due_at=_due_in_days(now, interval),
    )


def review(card: Card, grade: str, now: datetime) -> Card:
    """이 카드를 이렇게 찍었다. 다음 일정이 박힌 새 카드를 돌려준다.

    **`card` 를 고치지 않는다.** 되돌리기가 찍기 전의 값을 그대로 적어 두려면
    (`_ReviewLog`) 찍는 쪽이 원본을 들고 있어야 한다.
    """
    if grade not in EASE_DELTA:
        raise ValueError(f"모르는 채점: {grade}")

    card = replace(card, reps=card.reps + 1)

    # ── 익었던 카드를 잊었다. 여기만 `lapses` 가 오른다.
    if card.state == STATE_REVIEW and grade == "again":
        kept = int(round(card.interval_days * LAPSE_FACTOR))
        return replace(
            card,
            state=STATE_RELEARN,
            step=0,
            lapses=card.lapses + 1,
            ease=_clamp_ease(card.ease, grade),
            interval_days=max(MIN_REVIEW_INTERVAL, kept),
            due_at=now + timedelta(seconds=RELEARN_STEPS[0]),
        )

    # ── 익은 카드. 날 단위로 늘린다.
    if card.state == STATE_REVIEW:
        ease = _clamp_ease(card.ease, grade)
        if grade == "hard":
            grown = card.interval_days * HARD_FACTOR
        elif grade == "good":
            grown = card.interval_days * ease
        else:
            grown = card.interval_days * ease * EASY_BONUS
        # 간격은 언제나 는다. 안 그러면 Hard 를 누른 1일 카드가 1일에 머물러
        # 매일 같은 카드가 돌아오고, 사다리가 그 자리에서 멈춘다.
        interval = max(int(round(grown)), card.interval_days + 1)
        return replace(
            card,
            interval_days=min(MAX_INTERVAL, interval),
            ease=ease,
            due_at=_due_in_days(now, min(MAX_INTERVAL, interval)),
        )

    # ── 새 카드거나 익히는 중이거나 다시 익히는 중이다. 분 단위로 돈다.
    state = STATE_LEARNING if card.state == STATE_NEW else card.state
    steps = _steps(state)

    if grade == "easy":
        # 다시 익히는 중이었으면 잊기 전의 간격을 돌려받는다(이미 하루로
        # 깎여 있다). 처음 익히는 중이었으면 안키와 같이 나흘이다.
        return _graduate(card, now, card.interval_days if state == STATE_RELEARN else EASY_INTERVAL)

    if grade == "again":
        step = 0
    elif grade == "hard":
        # Hard 는 같은 단계를 한 번 더 돈다. **첫 단계에서만 두 단계의 가운데를
        # 쓴다** — 안키의 규칙이고, 안 그러면 새 카드에서 Again 과 Hard 가 둘 다
        # 「1분」으로 적힌다. 같은 값을 적은 버튼 둘은 고장으로 읽힌다.
        step = min(card.step, len(steps) - 1)
        if step == 0 and len(steps) >= 2:
            return replace(
                card,
                state=state,
                step=0,
                due_at=now + timedelta(seconds=(steps[0] + steps[1]) // 2),
            )
    else:  # good — 다음 단계로
        step = card.step + 1
        if step >= len(steps):
            return _graduate(
                card, now, card.interval_days if state == STATE_RELEARN else GRADUATING_INTERVAL
            )

    return replace(
        card,
        state=state,
        step=step,
        due_at=now + timedelta(seconds=steps[step]),
    )


def preview(card: Card, now: datetime) -> dict[str, dict[str, int]]:
    """네 버튼을 각각 누르면 언제 다시 나오나. **아무것도 저장하지 않는다.**

    `reveal` 이 이것을 실어 보내므로 화면은 일정을 계산하지 않는다 — 자기
    계산으로 적으면 사다리가 파이썬과 타입스크립트 두 곳에 살고, 두 곳에
    사는 것은 갈라진다.

    `days` 가 0 이 아니면 날 단위로 익은 것이다. 0 이면 `seconds` 를 읽는다.
    """
    out: dict[str, dict[str, int]] = {}
    for grade in GRADES:
        next_card = review(card, grade, now)
        if next_card.state == STATE_REVIEW:
            out[grade] = {"days": next_card.interval_days, "seconds": 0}
        else:
            delay = int((next_card.due_at - now).total_seconds()) if next_card.due_at else 0
            out[grade] = {"days": 0, "seconds": max(0, delay)}
    return out


def is_due(card: Card, now: datetime | None = None) -> bool:
    """지금 낼 카드인가. 시각을 안 가진 카드(새 카드)는 언제나 낸다."""
    if card.state == STATE_NEW or card.due_at is None:
        return True
    due = card.due_at if card.due_at.tzinfo else card.due_at.replace(tzinfo=UTC)
    return due <= (now or datetime.now(UTC))

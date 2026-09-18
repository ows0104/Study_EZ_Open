"""망각곡선 사다리가 맞게 오르고 맞게 떨어지는가.

`app/srs.py` 는 DB도 시계도 안 들고 `now` 를 받는 순수 함수라, **시각을 손으로
밀어 가며 사다리 전체를 한 프로세스에서 잴 수 있다.** 그것이 일정 계산을
라우트 밖으로 낸 이유 중 하나다.

여기서 재는 것은 넷이다.

    ① 새 카드가 익히기 단계를 거쳐 졸업한다
    ② 익은 카드의 간격이 쉬움도로 늘고, 늘기만 한다
    ③ Again 은 간격을 버리고 다시 익히기로 내린다
    ④ 하루는 날 단위로 바뀐다 — 밤에 찍은 카드가 다음날 저녁에 잠겨 있으면 안 된다

    server/.venv/Scripts/python.exe -m tests.test_srs
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta

os.environ.setdefault("ENVIRONMENT", "local-test")
os.environ.setdefault("DATABASE_URL", "sqlite://")

from app import srs  # noqa: E402

failures: list[str] = []


def check(label: str, condition: bool, detail: object = "") -> None:
    print(f"  {'PASS' if condition else 'FAIL'}  {label}" + (f"  <- {detail}" if not condition else ""))
    if not condition:
        failures.append(label)


#: 한국 시각 낮이다. 하루가 바뀌는 새벽 4시에서 멀리 떨어뜨려 두었다 —
#: 경계에 붙여 두면 경계 자체를 재는 검사와 섞인다.
NOON = datetime(2026, 9, 18, 3, 0, tzinfo=UTC)  # KST 정오


def main() -> None:
    print("\n[1] 새 카드가 익히기를 거쳐 졸업한다")
    card = srs.Card()
    check("새 카드는 지금 낸다", srs.is_due(card, NOON))

    first = srs.review(card, "good", NOON)
    check("한 번 누르면 익히는 중이다", first.state == srs.STATE_LEARNING, first.state)
    check("10분 뒤로 잡힌다", first.due_at == NOON + timedelta(seconds=600), first.due_at)
    check("아직 낼 때가 아니다", not srs.is_due(first, NOON), first.due_at)
    check("10분 뒤에는 낸다", srs.is_due(first, NOON + timedelta(seconds=600)))

    second = srs.review(first, "good", NOON + timedelta(seconds=600))
    check("단계를 다 지나면 졸업한다", second.state == srs.STATE_REVIEW, second.state)
    check("졸업 간격은 하루다", second.interval_days == 1, second.interval_days)
    check("찍은 횟수가 쌓인다", second.reps == 2, second.reps)

    print("\n[2] 처음부터 Again 은 첫 단계로 돌린다")
    again = srs.review(srs.Card(), "again", NOON)
    check("1분 뒤다", again.due_at == NOON + timedelta(seconds=60), again.due_at)
    check("아직 익히는 중이다", again.state == srs.STATE_LEARNING, again.state)
    stayed = srs.review(again, "again", NOON)
    check("또 눌러도 첫 단계다", stayed.step == 0, stayed.step)

    # **새 카드의 Hard 는 Again 과 달라야 한다.** 첫 단계에서 같은 단계를 그냥
    # 되돌면 둘 다 「1분」으로 적히고, 같은 값을 적은 버튼 둘은 고장으로 읽힌다.
    hard_first = srs.review(srs.Card(), "hard", NOON)
    check("첫 단계의 Hard 는 두 단계의 가운데다",
          hard_first.due_at == NOON + timedelta(seconds=330), hard_first.due_at)
    check("단계는 그대로 첫 칸이다", hard_first.step == 0, hard_first.step)

    print("\n[3] Easy 는 익히기를 건너뛴다")
    easy = srs.review(srs.Card(), "easy", NOON)
    check("바로 익은 것이 된다", easy.state == srs.STATE_REVIEW, easy.state)
    check("간격이 나흘이다", easy.interval_days == srs.EASY_INTERVAL, easy.interval_days)

    print("\n[4] 익은 카드의 간격이 쉬움도로 는다")
    card = srs.Card(state=srs.STATE_REVIEW, interval_days=10, ease=2.5, reps=3)
    good = srs.review(card, "good", NOON)
    check("Good 은 쉬움도만큼 — 10일이 25일", good.interval_days == 25, good.interval_days)
    check("Good 은 쉬움도를 안 건드린다", good.ease == 2.5, good.ease)

    hard = srs.review(card, "hard", NOON)
    check("Hard 는 1.2배 — 12일", hard.interval_days == 12, hard.interval_days)
    check("Hard 는 쉬움도를 깎는다", round(hard.ease, 2) == 2.35, hard.ease)

    easy = srs.review(card, "easy", NOON)
    check("Easy 는 쉬움도에 덤까지 — 34일", easy.interval_days == 34, easy.interval_days)
    check("Easy 는 쉬움도를 올린다", round(easy.ease, 2) == 2.65, easy.ease)

    print("\n[5] 간격은 늘기만 한다")
    # **여기가 안 막히면 사다리가 그 자리에서 멈춘다.** 하루짜리 카드에
    # Hard(1.2배)를 누르면 1.2일 → 반올림 1일이 되어, 매일 같은 카드가 돌아온다.
    one_day = srs.Card(state=srs.STATE_REVIEW, interval_days=1, ease=1.3)
    for grade in ("hard", "good", "easy"):
        grown = srs.review(one_day, grade, NOON)
        check(f"하루 카드에 {grade} 를 눌러도 하루에 안 머문다",
              grown.interval_days > 1, grown.interval_days)

    print("\n[6] 쉬움도에는 바닥이 있다")
    low = srs.Card(state=srs.STATE_REVIEW, interval_days=5, ease=1.3)
    check("1.3 아래로 안 내려간다", srs.review(low, "hard", NOON).ease == srs.MIN_EASE,
          srs.review(low, "hard", NOON).ease)

    print("\n[7] 간격에는 천장이 있다")
    huge = srs.Card(state=srs.STATE_REVIEW, interval_days=300, ease=2.5)
    check("한 해를 안 넘는다", srs.review(huge, "good", NOON).interval_days == srs.MAX_INTERVAL,
          srs.review(huge, "good", NOON).interval_days)

    print("\n[8] 잊은 카드는 간격을 버리고 다시 익힌다")
    known = srs.Card(state=srs.STATE_REVIEW, interval_days=40, ease=2.5, reps=6, lapses=1)
    lapsed = srs.review(known, "again", NOON)
    check("다시 익히기로 내려간다", lapsed.state == srs.STATE_RELEARN, lapsed.state)
    check("실패 횟수가 오른다", lapsed.lapses == 2, lapsed.lapses)
    check("간격이 하루로 깎인다", lapsed.interval_days == 1, lapsed.interval_days)
    check("10분 뒤에 다시 낸다", lapsed.due_at == NOON + timedelta(seconds=600), lapsed.due_at)
    check("쉬움도가 0.2 깎인다", round(lapsed.ease, 2) == 2.3, lapsed.ease)

    back = srs.review(lapsed, "good", NOON + timedelta(seconds=600))
    check("한 단계로 익은 것으로 돌아온다", back.state == srs.STATE_REVIEW, back.state)
    check("깎인 간격에서 다시 시작한다", back.interval_days == 1, back.interval_days)

    print("\n[9] 하루는 날 단위로 바뀐다")
    # 밤 11시(KST)에 찍은 하루짜리 카드가, 다음날 저녁 9시에 이미 열려 있어야
    # 한다. 시각으로 재면 그때까지 두 시간이 남고 화면은 「0장」을 보여 준다 —
    # 그 0은 「다 했다」로 읽힌다.
    late_night = datetime(2026, 9, 18, 14, 0, tzinfo=UTC)  # KST 23:00
    tomorrow_evening = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)  # KST 21:00
    # 마지막 익히기 단계에서 졸업하는 카드다 — 간격이 딱 하루다.
    scheduled = srs.review(
        srs.Card(state=srs.STATE_LEARNING, step=len(srs.LEARNING_STEPS) - 1), "good", late_night
    )
    check("졸업 간격이 하루다", scheduled.interval_days == 1, scheduled.interval_days)
    check("다음날 저녁에는 열려 있다", srs.is_due(scheduled, tomorrow_evening), scheduled.due_at)
    check("찍은 날 밤에는 안 열린다", not srs.is_due(scheduled, late_night + timedelta(hours=1)),
          scheduled.due_at)

    # 새벽 2시는 아직 어제다. 자정을 넘겨 공부하는 사람의 「어제 몫」이 책상에
    # 앉은 채로 사라지면 안 된다.
    check("새벽 2시는 전날에 속한다",
          srs.day_start(datetime(2026, 9, 18, 17, 0, tzinfo=UTC))  # KST 09-19 02:00
          == srs.day_start(datetime(2026, 9, 18, 12, 0, tzinfo=UTC)),  # KST 09-18 21:00
          srs.day_start(datetime(2026, 9, 18, 17, 0, tzinfo=UTC)))

    print("\n[10] 네 버튼의 결과를 미리 잰다 — 저장하지 않고")
    card = srs.Card(state=srs.STATE_REVIEW, interval_days=10, ease=2.5)
    seen = srs.preview(card, NOON)
    check("넷 다 온다", sorted(seen) == sorted(srs.GRADES), sorted(seen))
    check("Again 은 분 단위다", seen["again"] == {"days": 0, "seconds": 600}, seen["again"])
    check("Good 은 날 단위다", seen["good"]["days"] == 25, seen["good"])
    check("미리 재는 것이 카드를 안 건드린다", card.interval_days == 10, card)

    new_card = srs.preview(srs.Card(), NOON)
    check("새 카드의 Again 은 1분", new_card["again"]["seconds"] == 60, new_card["again"])
    check("새 카드의 Easy 는 나흘", new_card["easy"]["days"] == 4, new_card["easy"])

    print("\n[11] 모르는 채점은 조용히 넘기지 않는다")
    try:
        srs.review(srs.Card(), "pass", NOON)
        check("모르는 채점에서 멈춘다", False, "안 멈췄다")
    except ValueError:
        check("모르는 채점에서 멈춘다", True)

    print()
    if failures:
        print(f"{len(failures)}개 실패: {', '.join(failures)}")
        raise SystemExit(1)
    print("전부 통과.")


if __name__ == "__main__":
    main()

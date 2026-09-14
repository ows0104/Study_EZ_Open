"""한 강의의 시도를 전부 찾아 **원값으로** 나란히 놓는다.

    python scripts/attempts.py                  out/ 에 시도가 있는 편 전부
    python scripts/attempts.py 260812_01        한 편만
    python scripts/attempts.py --csv            표를 CSV 로

`docs/runs-layout.md` 의 2단계다. 그 문서가 이 도구에 **하지 말라고 적어 둔 것이
있다** — 등수를 매기지 않는다.

> 자동 선택 규칙을 지금 세우지 않는다. 세우려면 지표 하나를 임의로 골라야 하는데
> 그건 근거 없는 규칙이다. `CHOSEN.json` 의 `why` 를 사람이 적고, 코드는 **지표
> 표를 옆에 띄우는 데까지만** 한다.

그래서 여기서는 합계도 점수도 안 낸다. **정렬은 시각순뿐이다.**

## 재는 것은 `runner/attempts.py` 다

**이 파일은 화면에 찍는 일만 한다.** 재는 코드가 여기 있었는데 2026-09-15 에
`runner/attempts.py` 로 내렸다 — 사람이 고른 것을 적는 쪽(`runner/chosen.py`)이
같은 값을 봐야 하고, 두 곳에서 각각 재면 표와 기록이 갈릴 자리가 된다.

## 고르고 나면 적어라

이 표는 고르는 데 쓰고, **고른 것은 `CHOSEN.json` 에 적는다.**

    python -m runner chosen 260812_01 --keep --why "..."
    python -m runner chosen 260812_01 --pick out/redo_260812_01 --why "..."

적어 두지 않으면 다음에 같은 질문을 다시 하게 된다. 그 문서가 「왜 바꾸나」의 ④로
적어 둔 것이 그것이다 — **어느 시도가 왜 이겼는지 적는 자리가 없었다.**

## 재현 일치율은 ±4%p 흔들린다

같은 카드를 한 글자도 안 바꾸고 채점만 세 번 돌렸을 때 82.1% · 83.2% · 86.3% 가
나왔다(`quizgen/CLAUDE.md`). **그보다 작은 차이는 표에 그대로 싣되 고르는 근거로
쓰지 마라.** 이 도구가 그 폭을 표 아래에 같이 찍는 이유다.

## 왜 이 도구가 필요한가

`out/` 에 시도가 쌓여 있는데 `publish` 는 `runs/<run_id>/` 만 읽는다. 그래서
**어느 편의 가장 새 카드가 안 나가고 있는지**를 아무도 세지 않았다. 2026-08-29 에
23/29 편이 그랬고 2026-09-14 에 25/30 편이다 — 줄지 않았다.
"""

from __future__ import annotations

import csv
import datetime as dt
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from runner import attempts as att  # noqa: E402  (경로를 세운 뒤에 불러야 한다)
from runner import chosen  # noqa: E402

RUNS = ROOT / "runs"
OUT = ROOT / "out"


def rel(p: Path) -> str:
    try:
        return p.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return p.as_posix()


def fmt(a: att.Attempt, newest: bool) -> str:
    when = dt.datetime.fromtimestamp(a.when).strftime("%m-%d %H:%M") if a.when else "—"
    rate = f"{a.same_rate * 100:4.0f}%" if a.same_rate is not None else "   —"
    mark = "=" if not a.fresh else ("*" if newest else " ")
    tail = (f"  컷 {a.cut_id}" if a.cut_id
            else (f"  족보 안 붙음: {a.jokbo_why_not}" if a.jokbo_why_not else ""))
    return (f"  {mark} {rel(a.path):<34} {when}  "
            f"{a.cards:4}장  기출{a.exam_hit:3}  족보{a.jokbo_ref:3}  "
            f"같음{a.same:4}{rate}  부분{a.partial:3}  다름{a.different:3}  "
            f"{(str(a.minutes) + '분') if a.minutes else '—':>7}"
            f"{('$' + str(a.cost)) if a.cost else '—':>8}{tail}")


def as_csv(ids: list[str]) -> None:
    w = csv.writer(sys.stdout, lineterminator="\n")
    w.writerow(["run_id", "path", "when", "cards", "cards_sha256", "fresh",
                "exam_hit", "jokbo_ref", "same", "partial", "different", "graded",
                "minutes", "cost_usd", "cut_id", "jokbo_why_not"])
    for rid in ids:
        for a in att.attempts_of(RUNS, OUT, rid):
            w.writerow([rid, rel(a.path), a.when, a.cards, a.cards_sha256,
                        int(a.fresh), a.exam_hit, a.jokbo_ref, a.same, a.partial,
                        a.different, a.graded, a.minutes, a.cost,
                        a.cut_id, a.jokbo_why_not])


def main() -> None:
    args = [x for x in sys.argv[1:] if not x.startswith("--")]
    ids = args or att.run_ids_with_alternatives(RUNS, OUT)

    if "--csv" in sys.argv:
        as_csv(ids)
        return

    print("시도를 원값으로 나란히 놓는다. `*` 가 카드가 가장 새것인 시도다.")
    print("**등수는 매기지 않는다** — 무엇이 좋은 시도인지가 아직 안 정해졌다"
          " (docs/runs-layout.md 「아직 안 정한 것」).\n")
    stranded, real, unrecorded = [], 0, []
    for rid in ids:
        rows = att.attempts_of(RUNS, OUT, rid)
        if not rows:
            continue
        fresh = [a for a in rows if a.fresh]
        newest = max(fresh, key=lambda a: a.when)
        print(f"{rid}   시도 {len(fresh)}개")
        for a in rows:
            print(fmt(a, a is newest))
        # **고른 기록이 있으면 같이 보여 준다.** 표만 보고 또 고르지 않게 —
        # 그 문서의 ④ 가 「어느 시도가 왜 이겼는지 적는 자리가 없다」였다.
        run_dir = RUNS / rid
        if chosen.read(run_dir):
            print(f"    ▸ 골랐다: {chosen.summary(run_dir)}")
        else:
            unrecorded.append(rid)
        real += len(fresh)
        if newest.path.parent.resolve() == OUT.resolve():
            stranded.append(rid)
        print()

    print(f"편 {len(ids)}개 · 시도 {real}개 · 가장 새 카드가 out/ 에 있는 편 {len(stranded)}개")
    print("`=` 는 앞 줄과 **카드가 한 바이트도 안 다른** 것이다 — 채점만 다시 돌린 판이거나 사본이다.")
    if stranded:
        print("**`publish` 는 `runs/<run_id>/` 만 읽는다 — 그 편들은 안 나가고 있다.**")
    if unrecorded:
        print(f"\n고른 기록이 없는 편 {len(unrecorded)}개. **적어 두지 않으면 다음에 또 고른다.**")
        print(f'    python -m runner chosen {unrecorded[0]} --keep --why "..."')
    print(f"\n재현 같음비율은 채점만 다시 해도 ±{att.REPRODUCE_NOISE_PP}%p 흔들린다"
          " (한 편을 세 번 재서 얻은 값이다).")
    print("그보다 작은 차이는 표에 그대로 있되 **고르는 근거로 쓰지 마라.**")


if __name__ == "__main__":
    main()

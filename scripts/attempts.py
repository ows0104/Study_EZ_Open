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

import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / "runs"
OUT = ROOT / "out"
RUN_ID = re.compile(r"(\d{6}_\d{2})")

# 재현 일치율의 흔들림. 한 편(`260820_02`)을 세 번 재서 얻은 값이고 **다른 편에서
# 같은지는 모른다**(`quizgen/CLAUDE.md` 「아직 실측하지 않은 것」).
REPRODUCE_NOISE_PP = 4.2


def cards(d: Path) -> list[dict]:
    """그 시도가 낸 카드. 재현까지 간 것이 있으면 그것을, 없으면 검증 통과분을."""
    for name in ("items.reproduced.json", "items.checked.json", "items.raw.json"):
        p = d / name
        if not p.is_file():
            continue
        try:
            got = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        rows = got.get("cards", got) if isinstance(got, dict) else got
        # 모델이 카드 목록 끝에 `"__MORE__"` 같은 자리표시자를 붙여 낸 편이 있다.
        # 카드가 아닌 것이 섞일 수 있다는 것을 세는 쪽도 알아야 한다.
        return [c for c in rows if isinstance(c, dict) and "q" in c]
    return []


def measure(d: Path) -> dict | None:
    rows = cards(d)
    if not rows:
        return None
    verdicts = Counter(
        (c.get("reproduce") or {}).get("verdict") for c in rows if isinstance(c.get("reproduce"), dict)
    )
    got = {
        "path": d.relative_to(ROOT).as_posix(),
        "cards": len(rows),
        "exam_hit": sum(1 for c in rows if c.get("exam_hit")),
        "jokbo_ref": sum(1 for c in rows if c.get("jokbo_ref")),
        "same": verdicts.get("same", 0),
        "partial": verdicts.get("partial", 0),
        "different": verdicts.get("different", 0),
        "graded": sum(verdicts.values()),
        "minutes": None,
        "cost": None,
        "when": None,
        "cards_hash": None,
    }
    stamp = d / "items.raw.json"
    if stamp.is_file():
        got["when"] = stamp.stat().st_mtime
        # **시도인 척하는 것이 둘 있다.** 채점만 다시 돌린 판(`var1`·`var2`)과 그냥
        # 사본(`exp_prac` ↔ `runs/`). 모델이 쓴 카드가 한 바이트도 안 다르면 같은
        # 시도다 — 그것을 세면 시도 수가 부풀고, 그 표로 「나은 판」을 고르게 된다.
        got["cards_hash"] = hashlib.sha256(stamp.read_bytes()).hexdigest()[:8]
    report = d / "run.report.json"
    if report.is_file():
        try:
            cum = (json.loads(report.read_text(encoding="utf-8")) or {}).get("cumulative") or {}
            got["minutes"] = round(cum["seconds"] / 60, 1) if cum.get("seconds") else None
            got["cost"] = round(cum["cost_usd"], 2) if cum.get("cost_usd") else None
        except (OSError, json.JSONDecodeError, TypeError):
            pass
    return got


def attempts_of(run_id: str) -> list[dict]:
    """그 편의 시도 전부. `runs/<id>/` 와 `out/` 에서 이름에 그 id 가 든 것."""
    found = []
    for d in [RUNS / run_id, *sorted(p for p in OUT.glob(f"*{run_id}*") if p.is_dir())]:
        if d.is_dir() and (got := measure(d)):
            found.append(got)
    return sorted(found, key=lambda r: r["when"] or 0)


def run_ids() -> list[str]:
    """`out/` 에 시도가 있고 `runs/` 에도 있는 편. 없으면 비교할 것이 없다."""
    ids = set()
    for d in OUT.iterdir():
        m = RUN_ID.search(d.name)
        if d.is_dir() and m and (RUNS / m.group(1)).is_dir():
            ids.add(m.group(1))
    return sorted(ids)


def fmt(row: dict, newest: bool, dup: bool = False) -> str:
    import datetime as dt
    when = dt.datetime.fromtimestamp(row["when"]).strftime("%m-%d %H:%M") if row["when"] else "—"
    rate = f"{row['same'] / row['graded'] * 100:4.0f}%" if row["graded"] else "   —"
    mark = "=" if dup else ("*" if newest else " ")
    return (f"  {mark} {row['path']:<34} {when}  "
            f"{row['cards']:4}장  기출{row['exam_hit']:3}  족보{row['jokbo_ref']:3}  "
            f"같음{row['same']:4}{rate}  부분{row['partial']:3}  다름{row['different']:3}  "
            f"{(str(row['minutes']) + '분') if row['minutes'] else '—':>7}"
            f"{('$' + str(row['cost'])) if row['cost'] else '—':>8}")


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    as_csv = "--csv" in sys.argv
    ids = args or run_ids()

    if as_csv:
        import csv
        w = csv.writer(sys.stdout, lineterminator="\n")
        w.writerow(["run_id", "path", "when", "cards", "exam_hit", "jokbo_ref",
                    "same", "partial", "different", "graded", "minutes", "cost_usd"])
        for rid in ids:
            for r in attempts_of(rid):
                w.writerow([rid, r["path"], r["when"], r["cards"], r["exam_hit"], r["jokbo_ref"],
                            r["same"], r["partial"], r["different"], r["graded"],
                            r["minutes"], r["cost"]])
        return

    print("시도를 원값으로 나란히 놓는다. `*` 가 카드가 가장 새것인 시도다.")
    print("**등수는 매기지 않는다** — 무엇이 좋은 시도인지가 아직 안 정해졌다"
          " (docs/runs-layout.md 「아직 안 정한 것」).\n")
    stranded, real = [], 0
    for rid in ids:
        rows = attempts_of(rid)
        if not rows:
            continue
        seen: dict[str, dict] = {}
        for r in rows:
            r["dup_of"] = seen.setdefault(r["cards_hash"] or r["path"], r)
        fresh = [r for r in rows if r["dup_of"] is r]
        newest = max(fresh, key=lambda r: r["when"] or 0)
        print(f"{rid}" + (f"   시도 {len(fresh)}개" if len(fresh) != len(rows)
                          else f"   시도 {len(rows)}개"))
        for r in rows:
            print(fmt(r, r is newest, dup=r["dup_of"] is not r))
        real += len(fresh)
        if newest["path"].startswith("out/"):
            stranded.append((rid, newest["path"]))
        print()

    print(f"편 {len(ids)}개 · 시도 {real}개 · 가장 새 카드가 out/ 에 있는 편 {len(stranded)}개")
    print("`=` 는 앞 줄과 **카드가 한 바이트도 안 다른** 것이다 — 채점만 다시 돌린 판이거나 사본이다.")
    if stranded:
        print("**`publish` 는 `runs/<run_id>/` 만 읽는다 — 그 편들은 안 나가고 있다.**")
    print(f"\n재현 같음비율은 채점만 다시 해도 ±{REPRODUCE_NOISE_PP}%p 흔들린다"
          " (한 편을 세 번 재서 얻은 값이다).")
    print("그보다 작은 차이는 표에 그대로 있되 **고르는 근거로 쓰지 마라.**")


if __name__ == "__main__":
    main()

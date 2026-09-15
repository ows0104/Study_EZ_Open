"""㉰ 가 낸 카드에 **검사가 이미 뭐라고 했는지**를 센다.

    python scripts/quality_flags.py
    python scripts/quality_flags.py --card 260901_01:c037 --card 260901_02:c007

`docs/handoff-260915-cloze-quality.md` 가 관리자 불만 ③ 을 적으면서
*"길이에 잣대가 없다 … 프롬프트에도 검사에도 그 선이 없다"* 고 했다. **틀렸다.**
선은 넷이 이미 서 있고 계약에도 실려 있다(`quizgen/schema.py`).

    question_too_long        질문 120자 초과 (cloze 제외)      MAX_Q_CHARS
    cloze_sentence_too_long  빈칸 문장 120자 초과              MAX_Q_CHARS
    recall_load_high         외울 글자 80자 초과               MAX_RECALL_CHARS
    answer_frame_heavy       강조가 아닌 글자(프레임) 60자 초과   MAX_FRAME_CHARS
    too_many_items           회수 항목 6개 초과                MAX_RECALL_ITEMS

그래서 물어야 할 것이 바뀐다. 「선을 그을까」가 아니라 **「선이 울렸나, 울렸는데
아무도 안 봤나」** 다. 전부 soft flag 라 카드를 떨어뜨리지 않는다 — 깃발이 달린
카드도 그대로 덱에 실려 나갔다. 루트 `CLAUDE.md` 의 함정 ④ 가 이 모양이다.

**기준선의 눈금과 검사의 선은 다른 것을 잰다.** `prompt_baseline.py` 의 「답 80자」는
뒷면에 인쇄되는 글자 전부이고, 검사의 `recall_load_high` 는 `**` 로 표시된
**외울 글자**만 센다(`quizgen.validate.recall_load`). 둘이 얼마나 어긋나는지를
마지막 표가 보인다 — 어긋남이 크면 기준선 숫자로 검사를 논할 수 없다는 뜻이다.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from quizgen.schema import (  # noqa: E402
    MAX_FRAME_CHARS,
    MAX_Q_CHARS,
    MAX_RECALL_CHARS,
)
from quizgen.validate import recall_load  # noqa: E402

# `prompt_baseline.py` 와 같은 컷이다. ㉰ 가 선 시각(`b2b4326`).
SINCE = dt.datetime(2026, 9, 6, 15, 41)

# 기준선이 잡아 둔 눈금. **근거가 있어 그은 선이 아니다** — 검사의 선과 견주려고
# 여기서도 같은 값을 쓴다.
LONG_ANSWER = 80

# 길이에 닿는 깃발만 따로 본다. 나머지 깃발도 세지만 표에서는 이것들을 앞에 놓는다.
LENGTH_FLAGS = ("question_too_long", "cloze_sentence_too_long",
                "recall_load_high", "answer_frame_heavy", "too_many_items")


def cards_of(work: Path) -> list[dict]:
    """그 판의 카드. **`review_flags` 를 들고 있는 파일을 고른다.**

    `items.checked.json` 이 깃발을 다는 자리이고, `items.reproduced.json` 은 그것을
    이어받는다. 깃발이 없는 파일(`items.raw.json`)은 이 스크립트가 셀 것이 없다.
    """
    for name in ("items.checked.json", "items.reproduced.json"):
        p = work / name
        if not p.is_file():
            continue
        try:
            got = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []
        rows = got.get("cards", got) if isinstance(got, dict) else got
        return [c for c in rows if isinstance(c, dict) and "q" in c]
    return []


def decks(root: Path | None = None) -> list[tuple[str, str, list[dict]]]:
    """㉰ 이후에 카드를 쓴 판. `(편, 판, 카드들)`.

    **기본값을 여기서 푼다** — `root: Path = ROOT` 로 적으면 import 때 한 번 굳어서
    `ROOT` 를 딴 데로 돌려 놓고 부를 수가 없다.
    """
    root = root or ROOT
    cut = SINCE.timestamp()
    out = []
    for raw in sorted(root.glob("runs/*/main/*/items.raw.json")):
        if raw.stat().st_mtime < cut:
            continue
        cards = cards_of(raw.parent)
        if cards:
            out.append((raw.parts[-4], raw.parts[-2], cards))
    return out


def flagged(cards: list[dict]) -> Counter:
    return Counter(f for c in cards for f in (c.get("review_flags") or []))


def show_card(run: str, cid: str, root: Path | None = None) -> int:
    """짚은 카드 하나가 **깃발을 달고 있었는지** 본다."""
    root = root or ROOT
    hits = 0
    for edition, version, cards in decks(root):
        if edition != run:
            continue
        for c in cards:
            if c.get("id") != cid:
                continue
            hits += 1
            q, a = c.get("q") or "", c.get("a") or ""
            fmt = c.get("card_format", "?")
            recall, printed = recall_load(a, fmt)
            marks = c.get("review_flags") or []
            print(f"\n{edition}/{version}  {cid}  [{fmt}]")
            print(f"  질문 {len(q)}자 (선 {MAX_Q_CHARS})")
            print(f"  뒷면 {printed}자 · 외울 글자 {recall}자 (선 {MAX_RECALL_CHARS})")
            print(f"  프레임 {printed - recall}자 — 매번 다시 읽는 글자 "
                  f"(선 {MAX_FRAME_CHARS})")
            print(f"  깃발 {', '.join(marks) if marks else '없다'}")
    if not hits:
        print(f"{run}:{cid} — ㉰ 이후 판에서 못 찾았다")
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--card", action="append", default=[], metavar="편:id",
                    help="그 카드 하나가 깃발을 달고 있었는지 본다 (여러 번 쓸 수 있다)")
    args = ap.parse_args(argv)

    if args.card:
        bad = 0
        for spec in args.card:
            if ":" not in spec:
                print(f"--card 는 `편:id` 꼴이다: {spec}")
                return 2
            run, cid = spec.split(":", 1)
            bad |= show_card(run, cid)
        return bad

    got = decks()
    if not got:
        print(f"{SINCE:%Y-%m-%d %H:%M} 이후에 카드를 쓴 판이 없다")
        return 1

    rows = [c for _, _, cards in got for c in cards]
    counts = flagged(rows)
    n = len(rows)
    print(f"㉰({SINCE:%m-%d %H:%M} 이후)가 낸 편 {len(got)}개 · 카드 {n:,}장\n")

    print("길이에 닿는 깃발이 실제로 몇 번 울렸나")
    for f in LENGTH_FLAGS:
        print(f"  {f:24}{counts.get(f, 0):>6,}장 ({counts.get(f, 0) / n:>4.0%})")
    rest = [(f, k) for f, k in counts.most_common() if f not in LENGTH_FLAGS]
    if rest:
        print("\n나머지 깃발")
        for f, k in rest:
            print(f"  {f:24}{k:>6,}장 ({k / n:>4.0%})")

    print("\n**전부 soft flag 다.** 깃발이 달린 카드도 그대로 덱에 실려 나갔다.")

    # 기준선의 눈금과 검사의 선이 같은 카드를 가리키는가.
    basic = [c for c in rows if c.get("card_format") == "basic"]
    long_printed = {i for i, c in enumerate(basic) if len(c.get("a") or "") > LONG_ANSWER}
    high_recall = {i for i, c in enumerate(basic)
                   if "recall_load_high" in (c.get("review_flags") or [])}
    both = long_printed & high_recall
    print(f"\n기준선의 눈금과 검사의 선 (basic {len(basic):,}장)")
    print(f"  뒷면이 {LONG_ANSWER}자 넘는다 (눈금)        {len(long_printed):>6,}장")
    print(f"  recall_load_high (검사)          {len(high_recall):>6,}장")
    print(f"  둘 다                            {len(both):>6,}장")
    print("  → 어긋남이 크면 기준선 숫자로 검사를 논할 수 없다. 둘은 다른 것을 잰다 "
          "— 인쇄 길이와 외울 글자다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

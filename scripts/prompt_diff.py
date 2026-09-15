"""한 편의 판 둘을 맞댄다 — 프롬프트를 고친 것이 카드에 나타났는가.

    python scripts/prompt_diff.py 260914_03            제일 새 판 둘
    python scripts/prompt_diff.py 260914_03 A B        판을 지목해서

**같은 편 같은 자료를 두 번 구운 것**이므로 재료 차이가 없다. 그래도 이 저장소의
실측은 판마다 cloze 가 6~16장으로 흔들린다고 말한다(`quizgen/CLAUDE.md`) — **비율
지표의 작은 차이를 프롬프트 효과로 읽지 마라.**

믿을 만한 것은 **규칙이 겨냥한 모양을 직접 세는 칸**이다. 「힌트 줄」은 2026-09-15 전에는
프롬프트에 없던 모양이라 옛 판에서 0장이어야 하고, 그것이 0이 아니면 내가 세는 법을
잘못 짠 것이다.
"""

from __future__ import annotations

import json
import statistics as st
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LONG_LINE = 40
EXCLUDE = ("말고", "뺀다", "빼고", "제외하고", "은 뺀다")


def cards_of(work: Path) -> list[dict]:
    for name in ("items.reproduced.json", "items.checked.json", "items.raw.json"):
        p = work / name
        if not p.is_file():
            continue
        try:
            got = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []
        if isinstance(got, dict) and got.get("cards"):
            return got["cards"]
    return []


def lines_of(card: dict) -> list[str]:
    out = []
    for raw in (card.get("a") or "").splitlines():
        if raw.strip():
            out.append(raw.lstrip("- ").strip())
    return out


def measure(cards: list[dict]) -> dict:
    basic = [c for c in cards if c.get("card_format") == "basic"]
    cloze = [c for c in cards if c.get("card_format") == "cloze"]
    # **질문 길이는 머리줄로 잰다.** 힌트를 줄로 빼는 규칙(2026-09-15 `350b98a`)이 들면
    # 그 줄이 `q` 안으로 들어오므로, 문자열 전체로 재면 **규칙이 든 만큼 질문이 길어진
    # 것처럼 보인다.** 실제로 그렇게 읽혔다 — `260914_03` 이 60자 초과 4장에서 9장으로
    # 늘어난 줄 알았는데, 머리줄로 다시 재니 4장 그대로였다.
    ql = [len((c.get("q") or "").split(chr(10))[0]) for c in basic]
    al = [len(l) for c in basic for l in lines_of(c)]
    return {
        "카드": len(cards),
        "cloze": len(cloze),
        "질문 머리줄 중앙": st.median(ql) if ql else 0,
        "머리줄 60자 초과": sum(1 for x in ql if x > 60),
        "힌트 줄을 단 질문": sum(1 for c in basic if chr(10) in (c.get("q") or "")),
        "제외를 단 질문": sum(1 for c in basic
                         if any(w in (c.get("q") or "") for w in EXCLUDE)),
        "답 줄 중앙": st.median(al) if al else 0,
        "40자 넘는 줄": sum(1 for x in al if x > LONG_LINE),
        "해설이 붙은 카드": sum(1 for c in cards if (c.get("explanation") or "").strip()),
    }


def main() -> int:
    if len(sys.argv) < 2:
        print("쓰는 법: python scripts/prompt_diff.py 260914_03 [옛판 새판]")
        return 2
    run_id = sys.argv[1]
    root = ROOT / "runs" / run_id / "main"
    if not root.is_dir():
        print(f"{run_id}: main/ 이 없다")
        return 2
    have = [d.name for d in sorted(root.iterdir()) if d.is_dir() and cards_of(d)]
    picks = sys.argv[2:4] if len(sys.argv) >= 4 else have[-2:]
    if len(picks) < 2:
        print(f"{run_id}: 카드를 가진 판이 {len(have)}개다 — 맞댈 것이 없다")
        return 1

    got = [(p, measure(cards_of(root / p))) for p in picks]
    keys = list(got[0][1])
    wide = max(len(k) for k in keys) + 2
    print(f"{run_id} — 같은 편, 같은 자료. 판만 다르다" + chr(10))
    print(" " * wide + "".join(f"{p:>14}" for p, _ in got))
    for k in keys:
        row = "".join(f"{m[k]:>14.0f}" if isinstance(m[k], float) else f"{m[k]:>14}"
                      for _, m in got)
        mark = "   <- 이번에 넣은 규칙" if k in ("힌트 줄을 단 질문", "제외를 단 질문") else ""
        print(f"{k:<{wide}}{row}{mark}")
    print(chr(10) + "**비율의 작은 차이는 프롬프트 효과가 아니다.** 같은 편을 다시 구워도"
          + chr(10) + "판마다 흔들린다 — 믿을 것은 규칙이 겨냥한 모양을 직접 센 칸이다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

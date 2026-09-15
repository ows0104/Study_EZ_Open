"""㉰(2026-09-06 15:41 이후) 가 낸 카드의 기준선을 다시 뜬다.

    python scripts/prompt_baseline.py

`docs/handoff-260915-cloze-quality.md` 의 표를 만드는 한 줄이다. **고친 뒤 이 값과
견주려고 있다** — 관리자가 2026-09-15 에 넷을 반려했고(cloze 로 낼 것이 basic 으로 ·
질문의 한국어 · 답 길이 · 단순 번역) 그중 셋이 여기서 수치로 선다.

**④(단순 번역)는 세지 않는다.** 세는 법이 없고, 억지로 세면 없는 잣대를 만든 것이 된다.
"""

from __future__ import annotations

import datetime as dt
import json
import statistics as st
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# ㉰ 가 선 시각. `b2b4326` — v7 의 cloze 절을 되살린 커밋이다.
SINCE = dt.datetime(2026, 9, 6, 15, 41)

# 관리자 불만 ②③ 을 세는 선. **근거가 있어서 그은 선이 아니다** — 지금 분포를
# 보려고 잡은 눈금이다. 규칙으로 굳히려면 관리자에게 먼저 물어라
# (`quizgen/CLAUDE.md` 「규칙 문서를 쓰는 법」 ①).
LONG_ANSWER = 80
LONG_QUESTION = 60


def cards_of(work: Path) -> list[dict]:
    for name in ("items.reproduced.json", "items.checked.json", "items.raw.json"):
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


def parse_when(text: str) -> dt.datetime:
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return dt.datetime.strptime(text, fmt)
        except ValueError:
            continue
    raise SystemExit(f"시각을 못 읽었다: {text!r}  (예: 2026-09-15 10:45)")


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description="한 프롬프트가 낸 카드의 기준선을 뜬다")
    # **창을 자를 수 있어야 고친 뒤를 따로 잰다.** 안 그러면 새로 구운 판이 기준선에
    # 섞여 들어가 「고치기 전」이 조금씩 고쳐진 값이 된다.
    ap.add_argument("--since", metavar="시각",
                    help=f"이 시각 이후에 카드를 쓴 판만 (기본 {SINCE:%Y-%m-%d %H:%M})")
    ap.add_argument("--until", metavar="시각",
                    help="이 시각 전까지. 고치기 전 기준선을 그대로 다시 뜰 때 쓴다")
    args = ap.parse_args()
    since = parse_when(args.since) if args.since else SINCE
    until = parse_when(args.until) if args.until else None
    cut = since.timestamp()
    stop = until.timestamp() if until else None
    rows: list[dict] = []
    per: list[tuple] = []
    for raw in sorted(ROOT.glob("runs/*/main/*/items.raw.json")):
        if raw.stat().st_mtime < cut or (stop and raw.stat().st_mtime >= stop):
            continue
        cards = cards_of(raw.parent)
        if not cards:
            continue
        fm = Counter(c.get("card_format") for c in cards)
        alen = [len(c.get("a") or "") for c in cards if c.get("card_format") == "basic"]
        qlen = [len(c.get("q") or "") for c in cards]
        per.append((raw.parts[-4], raw.parts[-2], len(cards), fm.get("cloze", 0),
                    st.median(alen) if alen else 0, max(alen) if alen else 0,
                    st.median(qlen), max(qlen)))
        rows += cards

    if not rows:
        print(f"{since:%Y-%m-%d %H:%M} 이후에 카드를 쓴 판이 없다")
        return 1

    window = f"{since:%m-%d %H:%M} 이후" + (f" ~ {until:%m-%d %H:%M} 전" if until else "")
    print(f"{window}가 낸 편 {len(per)}개 · 카드 {len(rows):,}장\n")
    print(f"{'편':12}{'판':14}{'카드':>5}{'cloze':>6}{'답중앙':>7}{'답최대':>7}{'문중앙':>7}{'문최대':>7}")
    for r in per:
        print(f"  {r[0]:10}{r[1]:14}{r[2]:5}{r[3]:6}{r[4]:7.0f}{r[5]:7}{r[6]:7.0f}{r[7]:7}")

    fm = Counter(c.get("card_format") for c in rows)
    ab = [len(c.get("a") or "") for c in rows if c.get("card_format") == "basic"]
    qq = [len(c.get("q") or "") for c in rows]
    pct = lambda xs, p: sorted(xs)[int(len(xs) * p)]  # noqa: E731
    print(f"\n형식  {dict(fm.most_common())}")
    print(f"  cloze 비율                 {fm.get('cloze', 0) / len(rows):.1%}   ← ①")
    print(f"  basic 답 길이              중앙 {st.median(ab):.0f}자 · 상위10% {pct(ab, .9)}자 · 최대 {max(ab)}자")
    print(f"  질문 길이                  중앙 {st.median(qq):.0f}자 · 상위10% {pct(qq, .9)}자 · 최대 {max(qq)}자")
    print(f"  답이 {LONG_ANSWER}자 넘는 basic       {sum(x > LONG_ANSWER for x in ab):,}장 "
          f"({sum(x > LONG_ANSWER for x in ab) / len(ab):.0%})   ← ③")
    print(f"  질문이 {LONG_QUESTION}자 넘는 카드      {sum(x > LONG_QUESTION for x in qq):,}장 "
          f"({sum(x > LONG_QUESTION for x in qq) / len(qq):.0%})   ← ②")
    print("\n④(단순 번역)는 세지 않는다 — 세는 법이 없다. 사람이 짚는다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

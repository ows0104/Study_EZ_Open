"""가설 D 를 잰다 — cloze 의 「축을 남긴다」 규칙이 basic 질문으로 번지는가.

    python scripts/cloze_axis_probe.py [편]        기본값 260901_01

`docs/handoff-260915-cloze-quality.md` 가 D 를 **가장 중요한 단서**로 적으면서
*"이것은 아직 확인되지 않은 가설이다 — 프롬프트를 고치기 전에 그것부터 봐라"* 라고
남겼다. 그것을 재는 자리다.

## 무엇을 맞대는가

한 편을 판마다 다른 프롬프트로 돌려 둔 것이 있다(`260901_01` 은 11판). 판 폴더에
그때 쓴 `prompt.cards.*.md` 가 같이 있으므로 **프롬프트에 그 규칙이 있었는가**와
**산출물이 어땠는가**를 맞댈 수 있다.

## 프롬프트 파일을 그냥 믿으면 안 된다

**그 뒤 실행이 다시 조립하면서 덮는다.** `260901_01/main/260902-0122` 의 프롬프트는
09-08 16:21 것인데 카드는 09-06 16:19 에 썼다(핸드오프 「판 폴더의 `prompt.cards.*.md`
를 믿지 마라」). 아예 없는 판도 있다 — `260906-1619` 에는 프롬프트 파일이 0개다.

그래서 **파일 시각이 판 이름과 맞는 판만 센다.** 안 맞으면 `믿지 못함`으로 찍고
규칙 칸을 비운다. 세는 것에서 빼는 것이 아니라 **왜 뺐는지 보이게** 둔다.

## 재는 것

    ①② 질문      질문이 답의 구조를 번호로 늘어놓는가 — D 의 서명
    질문>60자     길이로 본 ②
    답>80자       ③
    cloze 비율    ①

`LONG_*` 눈금은 `prompt_baseline.py` 의 것과 같다 — **근거가 있어서 그은 선이 아니다.**
"""

from __future__ import annotations

import json
import re
import statistics as st
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

LONG_ANSWER = 80
LONG_QUESTION = 60

# D 의 서명. 질문이 답의 갈래를 번호로 세워 놓는 것 —
# 「4유형은 ① 몸 안으로 무엇이 들어오는가, ②~④ … 로 갈린다. 넷을 순서대로 들면?」
RE_ENUM = re.compile(r"[①②③④⑤]")

# 프롬프트에서 찾는 규칙. 왼쪽이 `core/quality.md` 의 문구다.
RULES = (("빈칸마다 그 축을 남긴다", "축"),
         ("범주나 기준을 밝혀", "닫기"),
         ("남는 문장이 답을 알려주면", "④"))

RE_VERSION = re.compile(r"^(\d{2})(\d{2})(\d{2})-(\d{2})(\d{2})")


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


def prompt_of(work: Path) -> tuple[str, str]:
    """그 판이 쓴 프롬프트와 믿을 수 있는지. 못 믿으면 본문을 빈 값으로 준다."""
    files = sorted(work.glob("prompt.cards.*.md"))
    if not files:
        return "", "파일 없음"
    stamp = max(f.stat().st_mtime for f in files)
    m = RE_VERSION.match(work.name)
    if not m:
        return "", "판 이름을 못 읽음"
    yy, mm, dd, hh, mi = (int(x) for x in m.groups())
    want = time.mktime((2000 + yy, mm, dd, hh, mi, 0, 0, 0, -1))
    # 조립이 끝나고 카드를 쓰기까지 걸리는 시간만큼은 벌어진다. 한 시간을 준다.
    if abs(stamp - want) > 3600:
        return "", time.strftime("덮임 %m-%d %H:%M", time.localtime(stamp))
    return "".join(f.read_text(encoding="utf-8") for f in files), ""


def main() -> int:
    run_id = sys.argv[1] if len(sys.argv) > 1 else "260901_01"
    root = ROOT / "runs" / run_id / "main"
    if not root.is_dir():
        print(f"{run_id}: main/ 이 없다")
        return 2

    print(f"{run_id} — 판마다 프롬프트와 산출물을 맞댄다\n")
    print(f"{'판':<14}{'장':>5}{'cloze':>7}{'q>60':>6}{'a>80':>6}{'①②':>5}"
          f"{'a중앙':>7}   규칙")
    rows = []
    for work in sorted(root.iterdir()):
        if not work.is_dir():
            continue
        cards = cards_of(work)
        if not cards:
            continue
        basic = [c for c in cards if c.get("card_format") == "basic"]
        cloze = sum(1 for c in cards if c.get("card_format") == "cloze")
        alen = [len(c.get("a") or "") for c in basic]
        enum = sum(1 for c in basic if RE_ENUM.search(c.get("q") or ""))
        text, why = prompt_of(work)
        marks = " ".join(lab for key, lab in RULES if key in text) if text else f"— {why}"
        row = dict(ver=work.name, n=len(cards), cloze=cloze,
                   cloze_pct=100 * cloze / len(cards),
                   q60=sum(1 for c in cards if len(c.get("q") or "") > LONG_QUESTION),
                   a80=sum(1 for x in alen if x > LONG_ANSWER),
                   enum=enum, amed=st.median(alen) if alen else 0,
                   axis="축" in marks, trusted=bool(text))
        rows.append(row)
        print(f"{row['ver']:<14}{row['n']:>5}{row['cloze']:>4}{row['cloze_pct']:>3.0f}%"
              f"{row['q60']:>6}{row['a80']:>6}{row['enum']:>5}{row['amed']:>7.0f}   {marks}")

    good = [r for r in rows if r["trusted"]]
    with_axis = [r for r in good if r["axis"]]
    without = [r for r in good if not r["axis"]]
    print(f"\n믿을 수 있는 판 {len(good)}/{len(rows)}")
    if not (with_axis and without):
        print("한쪽이 비어 맞댈 수 없다.")
        return 0

    def avg(rs, key):
        return sum(r[key] for r in rs) / len(rs)

    print(f"\n{'':<12}{'판':>4}{'cloze%':>8}{'a>80':>7}{'①②':>5}")
    for lab, rs in (("축 규칙 있음", with_axis), ("축 규칙 없음", without)):
        print(f"{lab:<12}{len(rs):>4}{avg(rs,'cloze_pct'):>7.1f}%"
              f"{avg(rs,'a80'):>7.1f}{avg(rs,'enum'):>5.1f}")

    print("\n**한 편을 판마다 한 번씩 돌린 값이다.** 같은 편 같은 자료인데 판마다"
          "\ncloze 6~16장으로 흔들린다(`quizgen/CLAUDE.md`). 여기 차이를 규칙의"
          "\n효과로 읽지 마라 — 맞댈 거리가 있는지 보는 자리다.")
    print("**이 편은 이미 프롬프트의 예시로 쓰였다**(`prompting.py` 의 `DOMAINS` 주석)."
          "\n그래서 「좋아졌다」를 이 편으로 재면 답을 쥐여 준 것이 된다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

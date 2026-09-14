"""한 강의의 시도를 찾아 **원값으로** 잰다. 고르지는 않는다.

`docs/runs-layout.md` 2단계의 계산부다. 화면에 찍는 것은 `scripts/attempts.py`,
사람이 고른 것을 적는 것은 `chosen.py` — **둘이 같은 값을 봐야 하므로 재는 자리를
하나로 둔다.**

## 등수를 매기지 않는다

그 문서가 코드에게 이렇게 적어 두었다.

> 자동 선택 규칙을 지금 세우지 않는다. 세우려면 지표 하나를 임의로 골라야 하는데
> 그건 근거 없는 규칙이다. `CHOSEN.json` 의 `why` 를 사람이 적고, 코드는 **지표
> 표를 옆에 띄우는 데까지만** 한다.

그래서 여기에는 점수도 합계도 없다. **정렬은 시각순뿐이다.**

## 시도인 척하는 것이 둘 있다

채점만 다시 돌린 판(`var1`·`var2`)과 그냥 사본(`exp_prac` ↔ `runs/`)이다. 모델이
쓴 카드가 한 바이트도 안 다르면 같은 시도다 — 그것을 세면 시도 수가 부풀고 **그
표로 「나은 판」을 고르게 된다.** `dedupe` 가 그것을 가른다.

## 시도의 신원은 `items.raw.json` 이다

모델이 쓴 카드가 그 시도가 한 일이고, 뒤의 검증·수선·재현은 그것에 붙는 처리다.
`chosen.py` 가 그 해시로 「사람이 고른 시도가 지금 그 자리에 있는가」를 본다 —
경로로 보면 카드를 옮겨 놓고도 안 맞는다고 하게 된다.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from . import runlayout

RUN_ID = re.compile(r"(\d{6}_\d{2})")
CARDS_FILE = "items.raw.json"

# 재현 같음비율의 흔들림. 한 편(`260820_02`)의 카드를 한 글자도 안 바꾸고 채점만
# 세 번 돌려 얻은 값이다(82.1 · 83.2 · 86.3). **다른 편에서 같은지는 모른다.**
# 이보다 작은 차이는 표에 그대로 싣되 **고르는 근거로 쓰지 마라.**
REPRODUCE_NOISE_PP = 4.2


@dataclass
class Attempt:
    path: Path
    cards: int = 0
    cards_sha256: str = ""
    exam_hit: int = 0
    jokbo_ref: int = 0
    same: int = 0
    partial: int = 0
    different: int = 0
    when: float = 0.0
    minutes: float | None = None
    cost: float | None = None
    cut_id: str | None = None
    jokbo_slice: str | None = None
    jokbo_why_not: str | None = None
    # 이 시도와 카드가 한 바이트도 안 다른 앞 시도. 자기 자신이면 새 시도다.
    same_cards_as: Attempt | None = field(default=None, repr=False)

    @property
    def graded(self) -> int:
        return self.same + self.partial + self.different

    @property
    def same_rate(self) -> float | None:
        """같음비율. **분모는 실제로 채점된 카드뿐이다.**

        이미지 카드는 재현 검사에서 빠진다(`reproduce.status = "skipped"` ·
        「앞면에 그림이 필요해 텍스트만으로 검사 불가」). 그것을 분모에 넣으면
        **사진이 많은 편이 저절로 낮게 나온다** — `260813_01` 은 154장 중 18장이
        그렇고, 넣으면 67%, 빼면 72% 다.

        2026-09-14 의 첫 표가 넣은 채로 찍고 있었다. 25편을 짝지어 본 결론은 그대로다
        (중앙 +3.5%p · 24/25 · 잡음 폭 안 15편) — 편마다의 백분율만 몇 점 움직였다.
        """
        return self.same / self.graded if self.graded else None

    @property
    def fresh(self) -> bool:
        """새 시도인가. 채점만 다시 돌린 판이나 사본이면 거짓."""
        return self.same_cards_as is None or self.same_cards_as is self


def _read(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def cards_of(attempt_dir: Path) -> list[dict]:
    """그 시도가 낸 카드. 재현까지 간 것이 있으면 그것을, 없으면 검증 통과분을."""
    for name in ("items.reproduced.json", "items.checked.json", CARDS_FILE):
        got = _read(attempt_dir / name)
        if got is None:
            continue
        rows = got.get("cards", got) if isinstance(got, dict) else got
        if not isinstance(rows, list):
            continue
        # 모델이 카드 목록 끝에 `"__MORE__"` 같은 자리표시자를 붙여 낸 편이 있다.
        # **카드가 아닌 것이 섞일 수 있다는 것을 세는 쪽도 알아야 한다** — 2026-09-02
        # 에 그것을 모르고 찍던 줄이 `AttributeError` 로 죽어 편 하나가 멈췄다.
        return [c for c in rows if isinstance(c, dict) and "q" in c]
    return []


def cards_sha256(attempt_dir: Path) -> str:
    """시도의 신원. `items.raw.json` 의 내용 해시 (모듈 머리)."""
    p = Path(attempt_dir) / CARDS_FILE
    if not p.is_file():
        return ""
    return hashlib.sha256(p.read_bytes()).hexdigest()


def measure(attempt_dir: Path) -> Attempt | None:
    """그 폴더가 시도라면 원값을 잰다. 카드가 없으면 시도가 아니다."""
    attempt_dir = Path(attempt_dir)
    rows = cards_of(attempt_dir)
    if not rows:
        return None
    verdicts = Counter((c.get("reproduce") or {}).get("verdict")
                       for c in rows if isinstance(c.get("reproduce"), dict))
    got = Attempt(
        path=attempt_dir,
        cards=len(rows),
        cards_sha256=cards_sha256(attempt_dir),
        exam_hit=sum(1 for c in rows if c.get("exam_hit")),
        jokbo_ref=sum(1 for c in rows if c.get("jokbo_ref")),
        same=verdicts.get("same", 0),
        partial=verdicts.get("partial", 0),
        different=verdicts.get("different", 0),
    )
    stamp = attempt_dir / CARDS_FILE
    if stamp.is_file():
        got.when = stamp.stat().st_mtime

    # 어느 족보 컷을 봤는가. **2026-09-14 이후에 만든 편에만 있다**
    # (`quizgen/cutmark.py` · `docs/runs-layout.md` 3단계).
    used = _read(attempt_dir / "jokbo.used.json")
    if isinstance(used, dict):
        got.cut_id = used.get("cut_id")
        got.jokbo_slice = used.get("slice")
        got.jokbo_why_not = None if used.get("attached") else used.get("why_not")

    report = _read(attempt_dir / "run.report.json")
    if isinstance(report, dict):
        cum = report.get("cumulative") or {}
        if cum.get("seconds"):
            got.minutes = round(cum["seconds"] / 60, 1)
        if cum.get("cost_usd"):
            got.cost = round(cum["cost_usd"], 2)
    return got


def dedupe(found: list[Attempt]) -> list[Attempt]:
    """카드가 같은 것끼리 묶어 `same_cards_as` 를 채운다. 같은 목록을 돌려준다.

    **해시가 없는 시도는 저마다 다른 것으로 둔다.** `items.raw.json` 이 없으면
    신원을 모르는 것이고, 모르는 둘을 같다고 하면 시도 하나가 사라진다.
    """
    seen: dict[str, Attempt] = {}
    for a in found:
        key = a.cards_sha256 or f"__no_hash__{a.path}"
        a.same_cards_as = seen.setdefault(key, a)
    return found


def attempts_of(runs_dir: Path, out_dir: Path, run_id: str) -> list[Attempt]:
    """그 편의 시도 전부, 시각순. 세 자리를 본다.

        runs/<id>/main/<판>/     새 모양 (`docs/runs-layout.md` 5단계)
        runs/<id>/               옛 모양 — 시도 것이 강의 폴더에 널려 있다
        out/*<id>*/              아직 접히지 않은 시도

    **옛 자리는 판이 있으면 안 본다.** 옮긴 편에서 강의 폴더를 또 재면 옮긴 시도가
    두 번 세어진다 — `dedupe` 가 카드 해시로 걸러 주지만, 그러면 경로가 옛 자리로
    찍혀 사람이 「안 옮겨졌다」고 읽는다.
    """
    run_dir = Path(runs_dir) / run_id
    places = [d for _, _, d in runlayout.attempt_dirs(run_dir)]
    if not places:
        places = [run_dir]
    if Path(out_dir).is_dir():
        places += sorted(p for p in Path(out_dir).glob(f"*{run_id}*") if p.is_dir())
    found = [got for d in places if d.is_dir() and (got := measure(d))]
    return dedupe(sorted(found, key=lambda a: a.when))


def run_ids_with_alternatives(runs_dir: Path, out_dir: Path) -> list[str]:
    """`out/` 에 시도가 있고 `runs/` 에도 있는 편. 없으면 비교할 것이 없다."""
    ids = set()
    if not Path(out_dir).is_dir():
        return []
    for d in Path(out_dir).iterdir():
        m = RUN_ID.search(d.name)
        if d.is_dir() and m and (Path(runs_dir) / m.group(1)).is_dir():
            ids.add(m.group(1))
    return sorted(ids)

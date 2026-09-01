"""「어디까지 왔고 얼마나 남았나」를 지난 편들의 실측으로 셈한다.

화면이 「만드는 중」만 말하면 5분째와 40분째가 같은 모양이다. 그래서 러너가
단계를 올릴 때 **몇 번째 단계인지와 남은 시간**을 같이 올린다.

세 가지를 읽는다. 셋 다 **이미 있던 것**이고, 이 모듈은 새로 재지 않는다.

    runs/*/run.report.json   `wall_seconds` — 한 편이 걸린 시간
                             `steps[]`      — 단계별 초. 이름이 로그의 `── ` 줄과
                                              겹치는 것만 쓴다
    runs/*/pipeline.log      복습의 단계 차례 (`── ` 줄이 나온 순서)
    runs/*/prequiz.log       예습의 단계 차례
    runs/_stage_stats.jsonl  러너가 자기 눈으로 잰 단계별 초 (`observe`)

**표본이 없으면 아무 말도 안 한다.** 0을 돌려주고 화면은 그 자리를 비운다 —
지어낸 숫자를 「예상 18분」이라고 적으면 그 뒤로 아무도 그 값을 안 믿는다.

이 저장소에서 처음 셈해 본 값(2026-09-01, 보고서 60개):

    복습 12편  중앙값 27.6분      예습 17편  중앙값 15.9분

**복습 표본이 저것뿐인 것은 갈래를 못 가른 자리가 많아서다.** 한 자리에 두 로그가
다 있는 편이 31편이고(`_run_kind`), 그중 마지막에 돈 것이 대개 예습이라 복습 쪽으로
안 세어졌다. 표본이 늘면 값이 움직인다 — **이 숫자를 목표나 기준으로 쓰지 마라.**

이어 돌린 회차(`--resume`)가 표본에 섞여 있어 `MIN_REAL_SECONDS`로 걸러 낸다 —
안 거르면 0.0분짜리가 중앙값을 끌어내린다.
"""

from __future__ import annotations

import json
import re
import statistics
import time
from dataclasses import dataclass
from pathlib import Path

MAIN = "main"
PRE = "pre"

# 이보다 짧게 끝난 편은 이어 돌린 회차다. 한 편이 걸리는 시간의 표본이 아니다.
MIN_REAL_SECONDS = 180

# 표본을 다시 읽는 간격. 러너가 20초마다 부르므로 매번 60개 파일을 열 수는 없다.
CACHE_SECONDS = 600

# `── 수선 1/2  (결함 4장)` 처럼 회차와 개수가 붙는 단계가 있다. 통계는 이름으로
# 모아야 해서 뒤를 떼어 낸다.
_TRAILING = re.compile(r"(?:\s{2,}\(.*\)|\s+\d+/\d+)+$")
_STAGE_LINE = re.compile(r"^── (.+)$")

_LOGS = {MAIN: "pipeline.log", PRE: "prequiz.log"}

_cache: dict[str, tuple[float, Samples]] = {}


def canon(stage: str) -> str:
    """통계에 쓰는 단계 이름. 회차·개수를 뗀다."""
    return _TRAILING.sub("", stage).strip()


@dataclass
class Samples:
    """한 갈래의 표본. 없으면 비어 있고, 그때는 아무 값도 안 낸다."""

    order: list[str]
    stage_seconds: dict[str, float]
    totals: list[float]

    @property
    def total(self) -> float:
        return statistics.median(self.totals) if self.totals else 0.0


@dataclass
class Estimate:
    index: int
    total: int
    eta_seconds: int


def observe(runs_dir: Path, kind: str, stage: str, seconds: float) -> None:
    """러너가 잰 단계 하나를 적어 둔다. **다음 편의 예상이 여기서 나온다.**

    `run.report.json`의 `steps`는 파이프라인이 아는 단계만 적는다(모델을 부르는
    자리들). 러너가 화면에 올리는 단계는 그보다 촘촘해서, 겹치지 않는 것들은
    이 파일이 아니면 잴 방법이 없다.
    """
    if seconds < 1:
        return
    row = {"kind": kind, "stage": canon(stage), "seconds": round(float(seconds), 1),
           "at": time.strftime("%Y-%m-%d %H:%M:%S")}
    try:
        runs_dir.mkdir(parents=True, exist_ok=True)
        with (runs_dir / "_stage_stats.jsonl").open("a", encoding="utf-8") as sink:
            sink.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError:
        # 통계를 못 적었다고 만들던 것을 버리지 않는다.
        pass


def _observed(runs_dir: Path) -> dict[str, list[float]]:
    rows: dict[str, list[float]] = {}
    path = runs_dir / "_stage_stats.jsonl"
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return rows
    for line in lines:
        try:
            row = json.loads(line)
        except ValueError:
            continue
        key = f"{row.get('kind')}/{row.get('stage')}"
        seconds = row.get("seconds")
        if isinstance(seconds, int | float) and seconds > 0:
            rows.setdefault(key, []).append(float(seconds))
    return rows


def _mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def _run_kind(run_dir: Path) -> str:
    """이 자리의 `run.report.json`이 어느 갈래의 것인가.

    **보고서는 갈래를 안 적는다.** 그런데 한 자리에 두 로그가 다 있는 편이 흔하다
    (작년 강의록으로 예습을 만들고, 같은 자리에서 복습도 만든 편들 — 60편 중
    31편이 그렇다). 그래서 **보고서와 시각이 가까운 로그** 쪽으로 센다. 마지막에
    돌린 것이 그 보고서를 쓴 것이다.

    둘 중 아무것도 없으면 표본이 아니다.
    """
    stamps = {kind: _mtime(run_dir / name) for kind, name in _LOGS.items()}
    live = {kind: stamp for kind, stamp in stamps.items() if stamp}
    if not live:
        return ""
    if len(live) == 1:
        return next(iter(live))
    report = _mtime(run_dir / "run.report.json")
    return min(live, key=lambda kind: abs(live[kind] - report))


def _stage_order(log: Path) -> list[str]:
    """로그에 `── ` 줄이 처음 나온 차례. 그것이 단계의 순서다."""
    seen: list[str] = []
    try:
        lines = log.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return seen
    for line in lines:
        found = _STAGE_LINE.match(line.strip())
        if not found:
            continue
        name = canon(found.group(1))
        if name and name not in seen:
            seen.append(name)
    return seen


def samples(runs_dir: Path, kind: str) -> Samples:
    """한 갈래의 표본. 10분 동안 캐시한다."""
    cached = _cache.get(kind)
    now = time.monotonic()
    if cached and now - cached[0] < CACHE_SECONDS:
        return cached[1]

    totals: list[float] = []
    per_stage: dict[str, list[float]] = {}
    order: list[str] = []
    newest = 0.0

    for report in runs_dir.glob("*/run.report.json"):
        run_dir = report.parent
        if _run_kind(run_dir) != kind:
            continue
        try:
            data = json.loads(report.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        wall = float(data.get("wall_seconds") or 0)
        if wall >= MIN_REAL_SECONDS:
            totals.append(wall)
        for step in data.get("steps") or []:
            name, seconds = canon(str(step.get("step", ""))), float(step.get("seconds") or 0)
            if name and seconds > 0:
                per_stage.setdefault(name, []).append(seconds)

        # 차례는 **가장 최근에 끝난 편**의 것을 쓴다. 단계가 늘거나 줄면 옛 편들과
        # 다수결을 해 봐야 지금 도는 편과 안 맞는다.
        try:
            stamp = report.stat().st_mtime
        except OSError:
            continue
        if stamp > newest:
            found = _stage_order(run_dir / _LOGS[kind])
            if found:
                newest, order = stamp, found

    for key, values in _observed(runs_dir).items():
        seen_kind, _, name = key.partition("/")
        if seen_kind == kind and name:
            per_stage.setdefault(name, []).extend(values)

    result = Samples(
        order=order,
        stage_seconds={name: statistics.median(values) for name, values in per_stage.items()},
        totals=totals,
    )
    _cache[kind] = (now, result)
    return result


def estimate(runs_dir: Path, kind: str, stage: str, elapsed: float,
             stage_elapsed: float = 0.0) -> Estimate:
    """지금 몇 번째 단계이고 얼마나 남았는가. 모르면 0을 돌려준다.

    남은 시간을 두 길로 센다.

    ① **남은 단계들의 합.** 단계별 중앙값이 남은 단계 대부분을 덮을 때만 쓴다.
       이쪽이 정확하다 — 「② 카드」 하나가 편의 절반이라 단계 번호를 시간에
       그대로 견주면 어긋난다.
    ② **편 전체의 중앙값에서 지난 시간을 뺀다.** ①이 안 될 때의 물러설 자리다.

    둘 다 못 세면 0이다. 화면은 그 자리를 비우고 「몇 분째」만 말한다.
    """
    data = samples(runs_dir, kind)
    name = canon(stage)
    order = data.order
    index = order.index(name) + 1 if name in order else 0
    total = len(order)

    remaining = order[index:] if index else []
    known = [step for step in remaining if step in data.stage_seconds]
    here = max(0.0, data.stage_seconds.get(name, 0.0) - stage_elapsed)
    eta = 0.0
    if index and not remaining:
        # **마지막 단계다.** 여기서 편 전체의 중앙값으로 물러서면 다 끝나 가는 편이
        # 「20분 남았다」고 말한다.
        eta = here
    elif index and len(known) >= max(1, int(len(remaining) * 0.6)):
        eta = sum(data.stage_seconds[step] for step in known) + here
    elif data.total:
        eta = max(0.0, data.total - elapsed)

    return Estimate(index=index, total=total, eta_seconds=int(eta))

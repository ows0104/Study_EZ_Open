"""「어디까지 왔고 얼마나 남았나」를 지난 편들의 실측으로 셈한다.

화면이 「만드는 중」만 말하면 5분째와 40분째가 같은 모양이다. 그래서 러너가
단계를 올릴 때 **몇 번째 단계인지와 남은 시간**을 같이 올린다.

세 가지를 읽는다. 셋 다 **이미 있던 것**이고, 이 모듈은 새로 재지 않는다.

    <판>/run.report.json     `wall_seconds` — 한 편이 걸린 시간
                             `steps[]`      — 단계별 초. 이름이 로그의 `── ` 줄과
                                              겹치는 것만 쓴다
    <판>/pipeline.log        복습의 단계 차례 (`── ` 줄이 나온 순서)
    <판>/prequiz.log         예습의 단계 차례
    runs/_stage_stats.jsonl  러너가 자기 눈으로 잰 단계별 초 (`observe`)

`<판>` 이 두 모양이라 찾는 자리도 둘이다 — `_reports` 를 봐라.

**표본이 없으면 아무 말도 안 한다.** 0을 돌려주고 화면은 그 자리를 비운다 —
지어낸 숫자를 「예상 18분」이라고 적으면 그 뒤로 아무도 그 값을 안 믿는다.

실측값(2026-09-18, 이 모듈이 읽은 표본 — 트리에 있는 보고서는 226개다):

    복습 141편  중앙값 27.4분      예습 63편  중앙값 16.2분

    4분위        23.0~33.7분                  14.1~19.9분

**갈래는 이제 경로에서 온다**(`runs/<편>/prequiz/<판>/`). 한 자리에 두 로그가 다
있어 갈래를 못 가르던 편이 31편이었고 그 때문에 복습 표본이 12편뿐이었는데, 새 모양은
판 폴더가 갈래를 적어 두므로 그 문제가 없다. **그래도 이 숫자를 목표나 기준으로
쓰지 마라** — 병렬로 두 편을 돌리면 편당 벽시계가 늘어난다(예습 단독 14편은 중앙값
15.4분, 겹쳐 돈 49편은 16.8분이고 최대 51.0분이다).

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

from . import runlayout

MAIN = "main"
PRE = "pre"

# 이보다 짧게 끝난 편은 이어 돌린 회차다. 한 편이 걸리는 시간의 표본이 아니다.
MIN_REAL_SECONDS = 180

# 단계 차례를 볼 때 몇 편까지 거슬러 보나. **한 편에 걸지 않는다** — 아래 참조.
ORDER_SAMPLE = 5

# 표본을 다시 읽는 간격. 러너가 20초마다 부르므로 매번 다 열 수는 없다 — 판 폴더까지
# 읽게 된 뒤로는 보고서가 226개다(2026-09-18).
CACHE_SECONDS = 600

# `── 수선 1/2  (결함 4장)` 처럼 회차와 개수가 붙는 단계가 있다. 통계는 이름으로
# 모아야 해서 뒤를 떼어 낸다.
_TRAILING = re.compile(r"(?:\s{2,}\(.*\)|\s+\d+/\d+)+$")
_STAGE_LINE = re.compile(r"^── (.+)$")

_LOGS = {MAIN: "pipeline.log", PRE: "prequiz.log"}

# **갈래 이름이 둘이다.** 이 모듈과 러너는 `pre`, 판 폴더는 `prequiz` 다
# (`runlayout.PREQUIZ`). 여기서만 맞춰 주고 밖으로는 안 내보낸다.
_KIND_DIRS = {MAIN: runlayout.MAIN, PRE: runlayout.PREQUIZ}

# 두 파이프라인의 마지막 단계. **끝까지 갔는지를 이걸로 안다** — 보고서에 성패를
# 적는 칸이 없다. 도중에 죽은 편의 보고서에는 이 단계가 없다.
FINAL_STAGE = "덱 빌드"

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
    """이 자리의 `run.report.json`이 어느 갈래의 것인가. **옛 모양에만 쓴다.**

    새 모양은 판 폴더 이름이 갈래를 적어 두므로 짐작할 것이 없다(`_reports`).

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


def _reports(runs_dir: Path, kind: str) -> list[tuple[Path, Path]]:
    """그 갈래의 보고서 전부. `(보고서, 그 편의 폴더)`.

    **두 모양을 같이 읽는다** — `runlayout` 이 그러는 이유가 여기서도 같다.

        새  runs/<편>/prequiz/<판>/run.report.json   갈래가 경로에 적혀 있다
        옛  runs/<편>/run.report.json                갈래를 로그 시각으로 짐작한다

    2026-09-18에 **새 모양을 아예 안 읽고 있던 것**을 고쳤다. `*/run.report.json`
    하나로 훑고 있었고 그것이 보고서 226개 중 **1개**를 잡았다 — 2026-09-15에 시도가
    판 폴더로 내려가면서(`runlayout.WRITES_ATTEMPT_DIRS`) 보고서가 한 칸 깊어졌는데
    글롭이 안 따라갔다.

    **화면에서 남은 시간이 통째로 빠져 있었다.** 처음 적을 때 「단계별 초는
    `_stage_stats.jsonl` 에서 따로 오니 남은 시간은 그동안도 떴을 것」이라고
    짐작해 적었는데, 재 보니 아니었다 — 보고서를 못 읽으면 `order` 가 비고, 그러면
    `estimate` 의 `index` 가 0 이라 ①도 못 가고 `totals` 가 비어 ②도 못 간다.
    2026-09-15(`cbef761`, 시도 160개를 접은 판)부터 사흘 동안 이렇게 돌았다.

        고치기 전   ② 카드 · 7분째 · 이 단계 6분째
        고친 뒤     ② 카드 (8/19단계) · 7분째 · 이 단계 6분째 · 남은 약 9분

    옛 판을 그대로 돌려 잰 값이다(`estimate('② 카드', 420초)` → 고치기 전 `0/0 ·
    0초`, 고친 뒤 `8/19 · 538초`). **짐작으로 적지 말고 재라** — 「무해하다」고 적어
    두면 그 줄이 확인을 막는다.

    **`revisions/` 는 안 센다.** 수선 회차가 낸 보고서는 한 편이 걸린 시간이 아니다.
    판 폴더 **바로 밑**만 보므로 저절로 빠진다.
    """
    # **표본 자리가 없는 갈래는 「모른다」다** — 예외가 아니다. Quiz Bank(`bank`)는 판 폴더도
    # `run.report.json` 도 없어서, 여기서 `KeyError` 가 나자 러너의 일꾼이 통째로 넘어졌다
    # (2026-10-05). 단계 시간은 `observe` 가 갈래 이름으로 따로 적으므로 그쪽 표본은 쌓인다.
    if kind not in _KIND_DIRS:
        return []
    folder = _KIND_DIRS[kind]
    found = [(report, report.parent.parent.parent)
             for report in runs_dir.glob(f"*/{folder}/*/run.report.json")
             if runlayout.RE_VERSION.match(report.parent.name)]
    found += [(report, report.parent)
              for report in runs_dir.glob("*/run.report.json")
              if _run_kind(report.parent) == kind]
    return found


def _log_of(report: Path, run_dir: Path, kind: str) -> Path:
    """그 보고서를 쓴 실행의 로그. **판 폴더 → 강의 폴더** 순.

    `runlayout.find` 가 시도 것을 찾는 순서와 같다. 새 모양으로 옮긴 편에도 로그가
    강의 폴더에만 있는 것이 있다 — 2026-09-18에 예습 보고서 64개 중 판 폴더에 로그가
    같이 있는 것은 38개였다.
    """
    here = report.parent / _LOGS[kind]
    return here if here.is_file() else run_dir / _LOGS[kind]


def samples(runs_dir: Path, kind: str) -> Samples:
    """한 갈래의 표본. 10분 동안 캐시한다."""
    cached = _cache.get(kind)
    now = time.monotonic()
    if cached and now - cached[0] < CACHE_SECONDS:
        return cached[1]

    totals: list[float] = []
    per_stage: dict[str, list[float]] = {}
    orders: list[tuple[float, list[str]]] = []

    for report, run_dir in _reports(runs_dir, kind):
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

        # 차례는 **끝까지 간 편**에서만 모은다. 도중에 죽은 편의 로그는 앞부분만
        # 있어서 분모를 끌어내린다 — 2026-09-02에 한도로 죽은 복습 셋이 최근
        # 표본을 채우자 `main`의 총 단계가 5로 떨어졌고, `② 카드`가 차례에서
        # 아예 빠졌다(그 편들은 거기까지 못 갔다).
        if FINAL_STAGE not in [canon(str(step.get("step", ""))) for step in data.get("steps") or []]:
            continue
        try:
            stamp = report.stat().st_mtime
        except OSError:
            continue
        found = _stage_order(_log_of(report, run_dir, kind))
        if found:
            orders.append((stamp, found))

    for key, values in _observed(runs_dir).items():
        seen_kind, _, name = key.partition("/")
        if seen_kind == kind and name:
            per_stage.setdefault(name, []).extend(values)

    result = Samples(
        order=_typical_order(orders),
        stage_seconds={name: statistics.median(values) for name, values in per_stage.items()},
        totals=totals,
    )
    _cache[kind] = (now, result)
    return result


def _typical_order(orders: list[tuple[float, list[str]]]) -> list[str]:
    """여러 편의 단계 차례에서 하나를 고른다. **한 편에 걸지 않는다.**

    분모가 표본 하나에서 오면 그 한 편의 변덕이 그대로 화면에 뜬다. 2026-09-02에
    같은 배치의 예습 두 편이 `7/7`과 `7/18`로 끝났다 — 예습 로그의 단계 이름 수를
    세어 보면 18이 보통인데 9·7짜리가 섞여 있고, 하필 그 짧은 편이 「가장 최근」이면
    뒤따르는 편들이 전부 그 분모를 쓴다.

    최근 몇 편의 **길이 최빈값**에 맞는 차례를 쓰고, 그중에서는 새 것을 고른다.
    이름의 다수결이 아니라 길이의 최빈값인 까닭은 **차례가 실제로 있던 한 편의
    것이어야** 하기 때문이다 — 여러 편에서 이름을 기워 붙이면 어느 편에도 없던
    차례가 만들어진다.
    """
    recent = [order for _, order in
              sorted(orders, key=lambda row: row[0], reverse=True)[:ORDER_SAMPLE]]
    if not recent:
        return []
    common = statistics.mode([len(order) for order in recent])
    return next(order for order in recent if len(order) == common)


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

"""v2 편당 토큰. **재기만 하고 판정하지 않는다.**

    python -m quiz2.tokens runs/260819_03
    python -m quiz2.tokens runs/260819_03 --save

세는 값과 구간 짝짓기는 `quiz/tokens.py`와 같다. **파일이 아니라 읽는 법이 다르다.**

## 한 API 호출이 2~3줄로 찍힌다

트랜스크립트는 assistant 메시지 하나를 블록별로 여러 줄에 나눠 적고, **그 줄마다
같은 `usage`를 통째로 붙인다.** `quiz/tokens.py`는 줄마다 더하므로 같은 호출을
두세 번 센다.

`260819_03`의 조각 `c01`에서 실측(2026-08-21):

    usage 레코드 21줄 → 고유 message.id 9개      (2~3배)
    편 전체       435줄 →           220개
    캐시읽기     30.0M →           14.6M

`message.id`로 묶어 한 번만 센다. 묶을 때 **출력은 최댓값**을 쓴다 — 스트리밍
첫 줄이 `output_tokens: 1` 같은 중간값으로 찍혀 있고, 나머지 넷(입력·캐시 둘)은
줄마다 같은 값이다.

    write 14554 read 28440 out   1   ← 첫 줄
    write 14554 read 28440 out 106   ← 같은 message.id

## 단계 창은 편 비용의 3분의 1만 덮는다 (2026-08-21)

`260819_03`을 단계 창으로 세면 15.9M인데, **같은 편의 창 전체를 세면 42.4M**이다.
빠진 26.5M은 오케스트레이터가 단계와 단계 **사이에서** 쓴 것이다 — 파이프라인 명령,
결과 들여다보기, 다음 스폰을 조립하는 자리. 창은 `start`~`end` 사이만 덮는데
오케스트레이터는 그 밖에서도 매 호출마다 제 문맥을 통째로 다시 읽는다.

    오케스트레이터(메인 세션)   135회   27.7M   호출당 207,253
    일꾼(서브에이전트) 27개     220회   14.6M   호출당  74,167

**그래서 「창 전체」 표를 따로 낸다.** 단계별 표는 그대로 두고 그 아래에 붙인다.
줄일 자리를 고르는 데 쓰는 것은 **호출당 문맥**이다 — 호출 수는 줄일 수 있고
문맥 크기는 세션을 새로 여는 것으로만 줄어든다.

## 창 전체는 이 편만의 값이 아니다

창은 시각으로만 잘린 구간이라 **그 사이 세션이 한 다른 일이 다 들어 있다.** 실제로
`260819_03` 창의 오케스트레이터 135회 중 44회가 그날 깨진 코드를 고치는 데 쓰였다.
`overlap`에 다른 편이 뜨면 그쪽 몫도 섞여 있다.

**그러니 창 합을 「이 편의 값」이라고 적지 마라.** 이 표가 답하는 것은 하나다 —
*단계 창이 못 보고 있던 것이 얼마나 되나.*

## 왜 `messages`가 아니라 `calls`인가

세던 것이 메시지 줄 수여서 이름이 `messages`였다. 그 수가 실제로 무엇을 뜻하는지
아무도 확인한 적이 없었고, 확인해 보니 API 호출 수도 메시지 수도 아니었다.
여기서는 **고유 `message.id` 수**를 세고 `calls`라고 부른다.

`quiz/`는 비교 기준선이라 고치지 않는다(`quiz2/README.md`). 그래서 읽는 쪽을
여기 따로 뒀다 — `quiz2/timings.py`가 벽시계를 다시 읽는 것과 같은 이유다.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

from quiz import timings  # noqa: E402
from quiz.tokens import FIELDS, PROJECTS, _fmt, _warn  # noqa: E402

# 구간 합집합은 v2 쪽에만 있다 (`quiz/`는 얼어붙은 기준선이라 안 고친다).
from . import timings as timings2

FILENAME = "tokens.json"

_INDEX: dict[str, list] | None = None


def _blank() -> dict:
    row = {f: 0 for f in FIELDS}
    row["calls"] = 0
    return row


def _add(into: dict, usage: dict) -> None:
    for f in FIELDS:
        into[f] += usage.get(f) or 0
    into["calls"] += 1


def _read(path: Path) -> list[tuple]:
    """(시각, usage, message_id)만 흘린다. 한 파일이 수십 MB라 통째로 안 파싱한다."""
    out: list[tuple] = []
    try:
        fh = path.open(encoding="utf-8", errors="replace")
    except OSError:
        return out
    with fh:
        for line in fh:
            if '"assistant"' not in line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("type") != "assistant":
                continue
            message = row.get("message") or {}
            usage = message.get("usage")
            stamp = row.get("timestamp")
            if not usage or not stamp:
                continue
            try:
                at = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
            except ValueError:
                continue
            # timings는 로컬 naive로 적는다. 같은 자로 맞춘다.
            out.append((at.astimezone().replace(tzinfo=None), usage,
                        message.get("id") or row.get("uuid")))
    return out


def _dedupe(rows: list[tuple]) -> list[tuple]:
    """같은 `message.id`를 한 줄로 접는다. 출력은 최댓값, 시각은 처음."""
    best: dict[str, tuple] = {}
    order: list[str] = []
    for at, usage, mid in rows:
        key = str(mid)
        seen = best.get(key)
        if seen is None:
            best[key] = (at, usage, mid)
            order.append(key)
        elif (usage.get("output_tokens") or 0) > (seen[1].get("output_tokens") or 0):
            best[key] = (seen[0], usage, mid)
    return [best[k] for k in order]


def index() -> dict[str, list]:
    """세션 → [(시각, usage, id, 종류)]. 한 번만 읽고, 파일 단위로 접는다.

    `종류`는 `main`(오케스트레이터 본 세션 파일)이나 `sub`(서브에이전트 파일)다.
    **둘을 안 가르면 「창 전체」 표를 못 낸다** — 편 비용의 어느 쪽이 큰지가
    거기서 갈린다.

    접는 단위가 **파일**이다. 같은 `message.id`가 두 파일에 나오는 일은 없고,
    세션 전체로 접으면 서브에이전트 파일이 서로를 지울 위험만 는다.
    """
    global _INDEX
    if _INDEX is not None:
        return _INDEX
    _INDEX = {}
    for main in PROJECTS.glob("*/*.jsonl"):
        session = main.stem
        rows = [(at, u, mid, "main") for at, u, mid in _dedupe(_read(main))]
        for agent in sorted((main.parent / session / "subagents").glob("*.jsonl")):
            rows.extend((at, u, mid, "sub")
                        for at, u, mid in _dedupe(_read(agent)))
        if rows:
            _INDEX[session] = rows
    return _INDEX


def collect(run_dir) -> dict:
    """한 편. 단계별 토큰과, 못 가른 것."""
    run_dir = Path(run_dir)
    spans = timings._spans(timings.load(run_dir))
    if not spans:
        return {"run": run_dir.name, "stages": {}, "total": _blank(),
                "spans": 0, "session_unknown": False, "overlap": [],
                "note": "timings.jsonl에 짝지어진 구간이 없다"}

    known = {s["session"] for s in spans if s.get("session")}
    unknown = any(not s.get("session") for s in spans)
    everything = index()
    sessions = sorted(everything) if unknown else sorted(known)

    mine = (min(s["start"] for s in spans), max(s["end"] for s in spans))

    stages: dict[str, dict] = {}
    total = _blank()
    # 창 전체. 단계 사이에서 나간 것이 여기서만 보인다 (위 문서).
    window = {"main": _blank(), "sub": _blank()}
    for session in sessions:
        for at, usage, _mid, kind in everything.get(session, ()):
            if mine[0] <= at <= mine[1]:
                _add(window[kind], usage)
            for span in spans:
                if not (span["start"] <= at <= span["end"]):
                    continue
                if span.get("session") and span["session"] != session:
                    continue
                _add(stages.setdefault(span["stage"], _blank()), usage)
                _add(total, usage)
                break

    overlap = []
    for other in sorted(run_dir.parent.iterdir()):
        if not other.is_dir() or other.name == run_dir.name:
            continue
        rows = timings._spans(timings.load(other))
        if any(a["start"] <= b["end"] and b["start"] <= a["end"]
               for a in spans for b in rows):
            overlap.append(other.name)

    return {
        "run": run_dir.name,
        "stages": stages,
        "total": total,
        "spans": len(spans),
        "sessions": sorted(known),
        "session_unknown": unknown,
        "overlap": overlap,
        "window": [mine[0].isoformat(timespec="seconds"),
                   mine[1].isoformat(timespec="seconds")],
        # 창 길이와, 그중 어느 단계에도 안 걸린 시간. 재실행 탐지용 (`_window_table`).
        "window_seconds": (mine[1] - mine[0]).total_seconds(),
        "window_idle_seconds": max(
            0.0, (mine[1] - mine[0]).total_seconds()
            - timings2._union_seconds([(sp["start"], sp["end"]) for sp in spans])),
        "window_main": window["main"],
        "window_sub": window["sub"],
        # 단계 창이 못 본 몫. **이 값이 크면 표의 위쪽 절반을 믿지 마라.**
        "unattributed": {
            f: window["main"][f] + window["sub"][f] - total[f] for f in FIELDS
        } | {"calls": window["main"]["calls"] + window["sub"]["calls"]
                      - total["calls"]},
    }


def _ctx(row: dict) -> str:
    """호출당 문맥. **줄일 자리를 고르는 데 쓰는 것은 이 값이다.**

    호출 수는 명령을 붙여서 줄일 수 있고, 문맥 크기는 세션을 새로 여는 것으로만
    줄어든다. 둘 중 무엇이 문제인지가 이 열에서 갈린다.
    """
    if not row["calls"]:
        return "-"
    per = (row["cache_read_input_tokens"]
           + row["cache_creation_input_tokens"]) // row["calls"]
    return f"{per:,}"


def _window_table(result: dict) -> None:
    """창 전체. **단계 창이 못 본 것이 여기서만 보인다** (모듈 문서).

    이 편만의 값이 아니다 — 창은 시각으로만 잘려서 그 사이 세션이 한 다른 일이
    다 들어 있다. 그래서 「이 편」이라고 안 적고 「창 전체」라고 적는다.
    """
    main = result.get("window_main")
    agent = result.get("window_sub")
    if not main and not agent:
        return
    lo, hi = result["window"]
    both = {f: main[f] + agent[f] for f in FIELDS}
    both["calls"] = main["calls"] + agent["calls"]
    missed = result["unattributed"]

    print(f"\n창 전체  {lo} ~ {hi}")
    print(f"{'':<20}{'':>8}{'캐시쓰기':>10}{'캐시읽기':>10}"
          f"{'출력':>9}{'호출':>7}{'호출당 문맥':>13}")
    for name, row in (("오케스트레이터", main), ("일꾼(서브에이전트)", agent),
                      ("창 합", both), ("단계 창이 못 본 몫", missed)):
        print(f"{name:<20}{'':>8}"
              f"{_fmt(row['cache_creation_input_tokens']):>10}"
              f"{_fmt(row['cache_read_input_tokens']):>10}"
              f"{_fmt(row['output_tokens']):>9}{row['calls']:>7}"
              f"{_ctx(row):>13}")

    read = both["cache_read_input_tokens"]
    if read:
        share = 100 * main["cache_read_input_tokens"] // read
        tail = ("파이프라인이 아니라 **세션이** 비용이다"
                if share >= 50 else "일꾼 쪽이 더 크다")
        print(f"  캐시읽기의 {share}%가 오케스트레이터다 — {tail}. "
              "줄이는 법은 `quiz2/README.md`의 「먼저」·「덩어리」다.")
    print("  ※ 창은 시각으로만 잘린다. 그 사이 세션이 한 다른 일도 들어 있다 — "
          "**이 편의 값이 아니다.**")

    # 재실행이 창을 부풀린다. `timings.py` ②가 벽시계에서 겪은 것과 같은 일인데,
    # 여기서는 훨씬 나쁘다 — 그 사이의 남의 토큰이 통째로 딸려 온다.
    # `260819_01`은 어제 편의 검증기를 오늘 한 번 더 돌렸을 뿐인데 창이 하루가
    # 되고 캐시읽기가 137M으로 찍혔다. 그래서 창과 실제 작업 시간을 견준다.
    idle = result.get("window_idle_seconds") or 0.0
    if idle > 1800:
        print(f"  ⚠ 창 {result['window_seconds'] / 3600:.1f}시간 중 "
              f"**{idle / 3600:.1f}시간이 단계 밖이다.** 재실행이 섞였으면 그 사이의"
              f" 남의 토큰이 통째로 들어와 있다 — 위 창 합을 믿지 마라")


def report(run_dir, save: bool = False) -> int:
    result = collect(run_dir)
    if not result["stages"]:
        print(f"[tokens2] {run_dir} — {result.get('note', '창에 걸린 메시지가 없다')}")
        return 0

    print(f"[tokens2] {Path(run_dir).name}  (message.id로 접어서 센다)\n")
    print(f"{'단계':<20}{'입력':>8}{'캐시쓰기':>10}{'캐시읽기':>10}"
          f"{'출력':>9}{'호출':>7}")
    order = sorted(result["stages"].items(), key=lambda kv: -kv[1]["output_tokens"])
    for name, s in order + [("합계(단계 창)", result["total"])]:
        print(f"{name:<20}{_fmt(s['input_tokens']):>8}"
              f"{_fmt(s['cache_creation_input_tokens']):>10}"
              f"{_fmt(s['cache_read_input_tokens']):>10}"
              f"{_fmt(s['output_tokens']):>9}{s['calls']:>7}")

    _window_table(result)
    _warn(result)

    if save:
        path = Path(run_dir) / FILENAME
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2),
                        encoding="utf-8")
        print(f"  → {path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="편당·단계당 토큰 (중복 제거)")
    parser.add_argument("run_dir")
    parser.add_argument("--save", action="store_true", help="tokens.json으로 남긴다")
    args = parser.parse_args()
    return report(args.run_dir, save=args.save)


if __name__ == "__main__":
    raise SystemExit(main())

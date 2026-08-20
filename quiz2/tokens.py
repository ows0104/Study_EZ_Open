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
    """세션 → [(시각, usage, id)]. 한 번만 읽고, 파일 단위로 접는다.

    접는 단위가 **파일**이다. 같은 `message.id`가 두 파일에 나오는 일은 없고,
    세션 전체로 접으면 서브에이전트 파일이 서로를 지울 위험만 는다.
    """
    global _INDEX
    if _INDEX is not None:
        return _INDEX
    _INDEX = {}
    for main in PROJECTS.glob("*/*.jsonl"):
        session = main.stem
        rows = _dedupe(_read(main))
        for sub in sorted((main.parent / session / "subagents").glob("*.jsonl")):
            rows.extend(_dedupe(_read(sub)))
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

    stages: dict[str, dict] = {}
    total = _blank()
    for session in sessions:
        for at, usage, _mid in everything.get(session, ()):
            for span in spans:
                if not (span["start"] <= at <= span["end"]):
                    continue
                if span.get("session") and span["session"] != session:
                    continue
                _add(stages.setdefault(span["stage"], _blank()), usage)
                _add(total, usage)
                break

    mine = (min(s["start"] for s in spans), max(s["end"] for s in spans))
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
    }


def report(run_dir, save: bool = False) -> int:
    result = collect(run_dir)
    if not result["stages"]:
        print(f"[tokens2] {run_dir} — {result.get('note', '창에 걸린 메시지가 없다')}")
        return 0

    print(f"[tokens2] {Path(run_dir).name}  (message.id로 접어서 센다)\n")
    print(f"{'단계':<20}{'입력':>8}{'캐시쓰기':>10}{'캐시읽기':>10}"
          f"{'출력':>9}{'호출':>7}")
    order = sorted(result["stages"].items(), key=lambda kv: -kv[1]["output_tokens"])
    for name, s in order + [("합계", result["total"])]:
        print(f"{name:<20}{_fmt(s['input_tokens']):>8}"
              f"{_fmt(s['cache_creation_input_tokens']):>10}"
              f"{_fmt(s['cache_read_input_tokens']):>10}"
              f"{_fmt(s['output_tokens']):>9}{s['calls']:>7}")
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

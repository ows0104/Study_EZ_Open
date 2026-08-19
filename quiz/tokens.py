"""편당 토큰. **재기만 하고 판정하지 않는다.**

`timings.jsonl`이 이미 "언제 무엇이 돌았나"를 들고 있다. 여기서는 그 구간에
세션 트랜스크립트의 `usage`를 겹쳐 **단계별 토큰**을 낸다.

    편   ← runs/<id>/timings.jsonl              구간(start~end) + 그걸 돈 세션
    토큰 ← ~/.claude/projects/**/<세션>.jsonl    assistant 메시지마다 usage

## 왜 창(시각)과 세션을 곱하나

세션 하나가 여러 편을 돌고, 한 편이 여러 세션에 걸친다. 실측(2026-08-19):
한 세션이 `260812_02`와 `260813_05`를 **동시에** 들고 있었다. 그래서 세션만으로는
못 가른다. 창만으로도 못 가른다 — 같은 시각에 두 편이 돌면 시각이 답을 안 준다.

**둘을 곱해야 갈린다.** `timings.record`가 줄마다 `session`을 찍는 이유다
(`CLAUDE_CODE_SESSION_ID`). 세션이 찍힌 구간은 그 세션의 트랜스크립트만 본다.

run_id를 트랜스크립트에서 문자열로 찾는 길도 있었는데 버렸다. `INDEX.md`나
`queue.json`을 한 번 읽으면 그 세션이 모든 편을 언급한 것이 된다 — 실측에서
아무 일도 안 한 세션이 `260812_02`를 67회 언급했다.

## 서브에이전트가 대부분이다

`/quiz`의 토큰은 조각 작성·감사 서브에이전트에서 나간다. 그 기록은 본 세션
파일이 아니라 `<세션>/subagents/agent-*.jsonl`에 따로 쌓이고, 본 세션 파일의
`isSidechain`은 전부 false다. **둘 다 세지 않으면 크게 적게 나온다.**

## 못 가르는 것은 못 가른다고 적는다

- `session`이 안 찍힌 구간(이 계측 이전에 돈 편)은 창에 걸치는 세션을 전부
  합산하고 `session_unknown`을 세운다. 다른 편의 토큰이 섞여 있다.
- 창이 다른 편과 겹치면 `overlap`에 그 편을 적는다. 같은 메시지를 양쪽이
  가져가므로 **두 편의 합은 실제보다 크다.**

지울지 믿을지는 사람이 정한다.

## 쓰는 법

    python quiz/tokens.py runs/260813_05            # 한 편, 단계별
    python quiz/tokens.py runs/260813_05 --save     # + tokens.json
    python quiz/tokens.py --all                     # runs 전체 한 줄씩
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from quiz import timings  # noqa: E402

PROJECTS = Path.home() / ".claude" / "projects"
FILENAME = "tokens.json"

# usage에서 세는 것. 넷을 따로 낸다 — 캐시 읽기는 싸고 캐시 쓰기는 비싸서
# 합쳐 놓으면 어디서 나갔는지가 사라진다. 단가는 여기 박지 않는다.
FIELDS = ("input_tokens", "cache_creation_input_tokens",
          "cache_read_input_tokens", "output_tokens")

_INDEX: dict[str, list] | None = None


def _blank() -> dict:
    row = {f: 0 for f in FIELDS}
    row["messages"] = 0
    return row


def _add(into: dict, usage: dict) -> None:
    for f in FIELDS:
        into[f] += usage.get(f) or 0
    into["messages"] += 1


def _files(session: str) -> list[Path]:
    """세션 하나가 남기는 파일 전부. 본 세션 + 서브에이전트.

    프로젝트 폴더 이름은 cwd를 슬러그로 바꾼 것이라 규칙을 짐작해야 하는데,
    세션 ID로 바로 찾으면 짐작할 것이 없다.
    """
    found: list[Path] = []
    for main in PROJECTS.glob(f"*/{session}.jsonl"):
        found.append(main)
        found.extend(sorted((main.parent / session / "subagents").glob("*.jsonl")))
    return found


def _read(path: Path) -> list[tuple]:
    """(시각, usage)만 흘린다. 한 파일이 수십 MB라 통째로 파싱하지 않는다."""
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
            usage = (row.get("message") or {}).get("usage")
            stamp = row.get("timestamp")
            if not usage or not stamp:
                continue
            try:
                at = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
            except ValueError:
                continue
            # timings는 로컬 naive로 적는다. 같은 자로 맞춘다.
            out.append((at.astimezone().replace(tzinfo=None), usage))
    return out


def index() -> dict[str, list]:
    """세션 → [(시각, usage)]. 한 번만 읽는다.

    `--all`이 편마다 다시 읽으면 100MB를 스물몇 번 훑는다.
    """
    global _INDEX
    if _INDEX is not None:
        return _INDEX
    _INDEX = {}
    for main in PROJECTS.glob("*/*.jsonl"):
        session = main.stem
        rows = _read(main)
        for sub in sorted((main.parent / session / "subagents").glob("*.jsonl")):
            rows.extend(_read(sub))
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
    # 세션이 찍힌 구간만 있으면 그 세션만 본다. 하나라도 안 찍혀 있으면
    # 그 구간은 누가 돌렸는지 모르므로 전부 본다 — 섞이는 것을 감수하고,
    # 섞였다고 적는다.
    sessions = sorted(everything) if unknown else sorted(known)

    stages: dict[str, dict] = {}
    total = _blank()
    for session in sessions:
        for at, usage in everything.get(session, ()):
            for span in spans:
                if not (span["start"] <= at <= span["end"]):
                    continue
                # 세션이 찍힌 구간은 남의 세션 것을 안 받는다.
                if span.get("session") and span["session"] != session:
                    continue
                _add(stages.setdefault(span["stage"], _blank()), usage)
                _add(total, usage)
                break

    mine = (min(s["start"] for s in spans), max(s["end"] for s in spans))
    # 겹침은 **구간끼리** 본다. 처음~끝의 껍데기로 보면 0단계 prep이 편들을
    # 한꺼번에 돌기 때문에 모든 편이 모든 편과 겹친다고 나온다 — 실측에서
    # `260813_05` 하나가 18편과 겹친다고 나왔고, 그건 신호가 아니라 잡음이다.
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


def _fmt(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.0f}k"
    return str(n)


def _warn(result: dict) -> None:
    if result["session_unknown"]:
        print("  ⚠ 세션이 안 찍힌 구간이 있다 — 그 창에 걸친 다른 편의 토큰이 섞였다")
    if result["overlap"]:
        print(f"  ⚠ 창이 겹치는 편: {', '.join(result['overlap'])} — 같은 메시지를 "
              f"양쪽이 센다. 두 편의 합은 실제보다 크다")


def report(run_dir, save: bool = False) -> int:
    result = collect(run_dir)
    if not result["stages"]:
        print(f"[tokens] {run_dir} — {result.get('note', '창에 걸린 메시지가 없다')}")
        return 0

    print(f"{'단계':<20}{'입력':>8}{'캐시쓰기':>10}{'캐시읽기':>10}"
          f"{'출력':>9}{'메시지':>8}")
    order = sorted(result["stages"].items(), key=lambda kv: -kv[1]["output_tokens"])
    for name, s in order + [("합계", result["total"])]:
        print(f"{name:<20}{_fmt(s['input_tokens']):>8}"
              f"{_fmt(s['cache_creation_input_tokens']):>10}"
              f"{_fmt(s['cache_read_input_tokens']):>10}"
              f"{_fmt(s['output_tokens']):>9}{s['messages']:>8}")
    _warn(result)

    if save:
        path = Path(run_dir) / FILENAME
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2),
                        encoding="utf-8")
        print(f"  → {path}")
    return 0


def report_all(runs_dir: Path) -> int:
    print(f"{'편':<12}{'입력':>8}{'캐시쓰기':>10}{'캐시읽기':>10}{'출력':>9}   비고")
    shown = 0
    for run_dir in sorted(runs_dir.iterdir()):
        if not run_dir.is_dir() or run_dir.name.startswith("_"):
            continue
        result = collect(run_dir)
        t = result["total"]
        if not t["messages"]:
            continue
        shown += 1
        note = []
        if result["session_unknown"]:
            note.append("세션 미상")
        if result["overlap"]:
            note.append(f"겹침 {len(result['overlap'])}편")
        print(f"{run_dir.name:<12}{_fmt(t['input_tokens']):>8}"
              f"{_fmt(t['cache_creation_input_tokens']):>10}"
              f"{_fmt(t['cache_read_input_tokens']):>10}"
              f"{_fmt(t['output_tokens']):>9}   {' · '.join(note)}")
    if not shown:
        print("  기록이 없다.")
    else:
        print("\n  '세션 미상'은 이 계측 이전에 돈 편이다. 창에 걸친 다른 편의")
        print("  토큰이 섞여 있으니 편끼리 비교하지 마라. 합은 총계가 아니다.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="편당·단계당 토큰")
    parser.add_argument("run_dir", nargs="?", help="runs/<lecture_id>")
    parser.add_argument("--all", action="store_true", help="runs 전체를 한 줄씩")
    parser.add_argument("--save", action="store_true", help="tokens.json으로 남긴다")
    parser.add_argument("--runs", default="runs", help="runs 디렉터리")
    args = parser.parse_args()

    if args.all:
        return report_all(Path(args.runs))
    if not args.run_dir:
        parser.error("run_dir을 주거나 --all을 써라")
    return report(Path(args.run_dir), save=args.save)


if __name__ == "__main__":
    raise SystemExit(main())

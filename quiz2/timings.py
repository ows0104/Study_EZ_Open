"""v2 단계 계측. **재기만 하고 판정하지 않는다.**

    python -m quiz2.timings runs/260819_01 report
    python -m quiz2.timings runs/260819_01 start 2-write --label c01
    python -m quiz2.timings runs/260819_01 end   2-write --label c01

줄은 `quiz/timings.py`와 같은 `timings.jsonl`에 쌓는다. **파일이 아니라 읽는 법이
다르다.** 아래 둘 때문이다.

## ① 모델 단계가 하나도 안 찍혔다

`260819_01`의 `timings.jsonl`에 있는 것은 `0-prep`·`0.5-check`·`3-validate`·
`5-build` 넷뿐이다. 전부 코드 단계이고 다 합쳐 **0.1분**이다.

편 하나의 시간은 거의 전부 모델 단계에서 나온다. `RUNS.md`가 적은 *"약 21분"*은
계측이 아니라 손으로 적은 값이고, *"jokbo 조각이 20.6분, 나머지 아홉은 5~6분"*도
마찬가지다. **관리자가 준 목표가 30분 이하인데 그걸 판정할 숫자가 파일에 없다.**

코드 단계는 자기가 찍는다. 모델 단계는 **오케스트레이터가 찍어야 한다** — 아래
`STAGES`가 그 목록이고 `report`가 빠진 것을 이름으로 댄다.

## ② 재실행이 벽시계를 부풀린다

`quiz/timings.py`의 `summarize`는 한 단계의 벽시계를 `max(end) - min(start)`로
잰다. 조각이 **동시에** 도는 자리를 재려고 그렇게 짰는데, 같은 단계를 **나중에 다시**
돌리면 그 사이의 빈 시간이 통째로 들어온다.

`260819_01`에서 실제로 이렇게 나왔다 — 어제 돌린 편의 검증기를 오늘 한 번 더 돌렸을 뿐인데

    0.5-check   2회   1130.5분      ← 두 실행 사이의 하루가 통째로 들어갔다
    3-validate  6회    577.5분
    합계(벽시계)      1132.5분      ← 21분짜리 편이다

여기서는 **구간의 합집합**으로 잰다. 겹치는 구간은 하나로 합치고 떨어진 구간은
각각 더한다. 동시 실행은 그대로 벽시계가 되고(겹치므로), 재실행은 각 실행의 길이만
더해진다. 같은 파일로 0.1분이 나온다.

`quiz/`는 비교 기준선이라 고치지 않는다. 그래서 읽는 쪽을 여기 따로 뒀다.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

from quiz.timings import FILENAME, _spans, load, record  # noqa: E402


# 겹침으로 안 치는 틈. 조각 스폰이 몇 초 어긋나 떨어져 찍히는 것까지 재실행으로
# 세면 동시 실행이 쪼개진다.
JOIN_GAP_SECONDS = 90.0

# v2 한 편의 단계. **이름이 오케스트레이터와의 계약이다.**
# `code`는 그 단계의 명령이 스스로 찍는다. `model`은 서브에이전트를 띄우는 자리라
# 오케스트레이터가 `start`/`end`를 직접 찍어야 한다 — 안 찍으면 그 시간이 사라진다.
STAGES: list[tuple[str, str, str]] = [
    ("0-prep",           "code",  "quiz/prep.py"),
    ("0.5-plan",         "code",  "quiz2.structure — 스폰 문구 조립"),
    ("0.5-write",        "model", "structure.json을 쓴다"),
    ("0.5-check",        "code",  "quiz/structure.py — 검증"),
    ("1-assemble",       "code",  "quiz2.assemble — 조각 PDF와 스폰 문구"),
    ("2-write",          "model", "조각마다 하나. --label c01 …"),
    ("2-merge",          "code",  "quiz2.merge"),
    ("3-validate",       "code",  "quiz2.validate"),
    ("3.5-occl-plan",    "code",  "quiz2.occlusion plan"),
    ("3.5-occlusion",    "model", "배치마다 하나. --label b01 …"),
    ("4.5-repro-split",  "code",  "quiz2.reproduce split"),
    ("4.5-repro-grade",  "code",  "quiz2.reproduce grade"),
    ("4.5-reproduce",    "model", "푸는 쪽·채점 쪽 두 바퀴. --label answer-b01 / grade-b01"),
    ("4.5-repro-score",  "code",  "quiz2.reproduce score"),
    ("5-build",          "code",  "quiz2.build"),
]

MODEL_STAGES = [name for name, kind, _ in STAGES if kind == "model"]


def _union_seconds(intervals: list[tuple[datetime, datetime]]) -> float:
    """겹치는 구간은 하나로, 떨어진 구간은 각각. **이 파일의 요점이다.**"""
    if not intervals:
        return 0.0
    merged: list[list[datetime]] = []
    for start, end in sorted(intervals):
        if merged and (start - merged[-1][1]).total_seconds() <= JOIN_GAP_SECONDS:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return sum((b - a).total_seconds() for a, b in merged)


def _runs(intervals: list[tuple[datetime, datetime]]) -> int:
    """떨어져 있는 덩어리 수. 2 이상이면 **재실행이 섞였다는 뜻**이다."""
    if not intervals:
        return 0
    count = 1
    last = sorted(intervals)[0][1]
    for start, end in sorted(intervals)[1:]:
        if (start - last).total_seconds() > JOIN_GAP_SECONDS:
            count += 1
        last = max(last, end)
    return count


def summarize(run_dir) -> dict:
    spans = _spans(load(run_dir))
    stages: dict[str, dict] = {}
    for span in spans:
        s = stages.setdefault(span["stage"], {
            "count": 0, "sum_seconds": 0.0, "intervals": [], "failed": 0,
            "labels": [], "last": span["end"],
        })
        s["count"] += 1
        s["sum_seconds"] += span["seconds"]
        s["intervals"].append((span["start"], span["end"]))
        s["last"] = max(s["last"], span["end"])
        if not span["ok"]:
            s["failed"] += 1
        if span["label"]:
            s["labels"].append(span["label"])
    for s in stages.values():
        s["wall_seconds"] = _union_seconds(s["intervals"])
        s["runs"] = _runs(s["intervals"])

    every = [iv for s in stages.values() for iv in s["intervals"]]
    known = {name for name, _, _ in STAGES}
    return {
        "stages": stages,
        "total_wall_seconds": _union_seconds(every),
        "spans": len(spans),
        "dangling": spans[0]["dangling"] if spans else 0,
        "missing_model": [n for n in MODEL_STAGES if n not in stages],
        "unknown": sorted(set(stages) - known),
    }


def _fmt(seconds: float | None) -> str:
    return "-" if seconds is None else f"{seconds / 60:.1f}분"


def report(run_dir) -> int:
    run_dir = Path(run_dir)
    result = summarize(run_dir)
    if not result["spans"]:
        print(f"[timings] {run_dir / FILENAME}에 짝지어진 구간이 없다")
        return 1

    order = {name: i for i, (name, _, _) in enumerate(STAGES)}
    rows = sorted(result["stages"].items(),
                  key=lambda kv: (order.get(kv[0], 99), kv[0]))

    print(f"[timings] {run_dir.name}")
    print(f"\n{'단계':<18}{'횟수':>4}{'벽시계':>9}{'작업합':>9}  비고")
    for name, s in rows:
        note = ""
        if s["runs"] > 1:
            note = f"재실행 {s['runs']}회 — 사이의 빈 시간은 안 센다"
        elif s["count"] > 1:
            # 겹쳤거나 90초 안에 연달아 돌았다. 둘을 여기서 갈라 말하지 않는다 —
            # 갈라 말하려면 구간을 다시 봐야 하는데 그럴 값이 없다.
            labels = ", ".join(s["labels"][:4])
            note = f"{s['count']}회 (겹치거나 연달아)" + (f" — {labels}" if labels else "")
        if s["failed"]:
            note = (note + "  ") if note else ""
            note += f"✗ 실패 {s['failed']}"
        print(f"{name:<18}{s['count']:>4}{_fmt(s['wall_seconds']):>9}"
              f"{_fmt(s['sum_seconds']):>9}  {note}")
    print(f"\n{'합계(벽시계)':<18}{'':>4}{_fmt(result['total_wall_seconds']):>9}"
          f"{'':>9}  겹치는 구간은 한 번만 센다")

    if result["dangling"]:
        print(f"\n  끝을 못 찍은 구간 {result['dangling']}개 — 죽었거나 "
              f"`end`를 빠뜨렸다")
    if result["unknown"]:
        print(f"  STAGES에 없는 이름: {', '.join(result['unknown'])}")

    if result["missing_model"]:
        print(f"\n  ⚠ 모델 단계 {len(result['missing_model'])}개가 한 줄도 안 찍혔다."
              f" **편 시간의 거의 전부가 거기서 나온다.**")
        for name in result["missing_model"]:
            detail = next(d for n, _, d in STAGES if n == name)
            print(f"      {name:<18} {detail}")
        print("\n  서브에이전트를 띄우기 직전과 받은 직후에 찍는다:")
        print(f"      python -m quiz2.timings {run_dir} start 2-write --label c01")
        print(f"      python -m quiz2.timings {run_dir} end   2-write --label c01")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="v2 단계 계측")
    parser.add_argument("run_dir")
    parser.add_argument("action", choices=["report", "start", "end"])
    parser.add_argument("stage", nargs="?", default=None)
    parser.add_argument("--label", default=None)
    args = parser.parse_args()

    if args.action == "report":
        return report(args.run_dir)

    if not args.stage:
        print("단계 이름을 줘라. 쓸 수 있는 이름:")
        for name, kind, detail in STAGES:
            print(f"  {name:<18} [{kind}] {detail}")
        return 2
    known = {name for name, _, _ in STAGES}
    if args.stage not in known:
        # 막지는 않는다. 새 단계가 생길 수 있고, 계측 때문에 파이프라인이 멈추면
        # 안 된다. 다만 `report`가 나중에 이름을 대서 알린다.
        print(f"  (STAGES에 없는 이름이다: {args.stage})")
    row = record(args.run_dir, args.stage, args.action, args.label)
    if not row:
        print(f"  안 찍혔다 — {args.run_dir}가 디렉터리가 아니다")
        return 1
    print(f"[timings] {args.stage} {args.action}"
          + (f" ({args.label})" if args.label else "") + f"  {row['at']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

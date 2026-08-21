"""v2 단계 계측. **재기만 하고 판정하지 않는다.**

    python -m quiz2.timings runs/260819_01 report
    python -m quiz2.timings runs/260819_01 start 2-write --label c01 c02 c03
    #   end는 일꾼이 제 것만 찍는다 (아래 ③)

## ③ 찍는 자리를 오케스트레이터에서 일꾼으로 옮겼다 (2026-08-21)

한 줄 찍는 값이 **누가 찍느냐로 갈린다.** `260819_03`을 다시 세어 보니 —

    오케스트레이터가 찍은 timings   16회   2.6M   호출당 164,493
    같은 편의 조각 일꾼             ...          호출당  40,587~62,963

오케스트레이터는 편이 길어질수록 문맥이 불어난다(그 편 마지막 호출이 376k였다).
`timings start` 한 줄에 16만 토큰이 드는 것은 명령이 길어서가 아니라 **부르는 쪽이
무겁기 때문**이다. 그래서 둘로 갈랐다.

    start   오케스트레이터가 찍되 **스폰과 같은 메시지에 넣는다.** 같은 메시지의
            도구 호출들은 문맥을 한 번만 읽으므로 추가 비용이 0이다.
            그래서 `--label`이 여러 개를 받는다 — 한 줄로 조각 전부를 연다
    end     **일꾼이 제 것만 찍는다.** 스폰 문서가 마지막 절에 명령을 준다
            (`stamp_note`). 일꾼 문맥은 4만대라 같은 한 줄이 4분의 1 값이다

**잃는 것을 적어 둔다.** 일꾼이 죽거나 명령을 빠뜨리면 `end`가 안 찍힌다. 예전에는
오케스트레이터가 받은 직후에 찍어서 그럴 일이 없었다. `report`의 「끝을 못 찍은
구간」이 그걸 센다 — **그 줄이 0이 아니면 벽시계를 믿지 마라.**

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
# **`start`는 오케스트레이터가 스폰과 같은 메시지에, `end`는 일꾼이** 찍는다
# (위 ③). 둘 중 하나라도 빠지면 그 시간이 사라진다.
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

# 일꾼이 뜰 때 쓰는 서브에이전트 이름. `.claude/agents/quiz-worker.md`가 실물이다.
# 도구를 넷(Read·Write·Edit·Bash)만 지고 뜬다 — 부팅 문맥 11.9k 대 43.0k.
WORKER = "quiz-worker"


def _cmd(run_dir, stage: str, action: str, labels=None) -> str:
    """Bash에 그대로 붙일 한 줄. 경로는 슬래시로 낸다."""
    tail = ""
    if labels:
        tail = " --label " + " ".join(str(x) for x in labels)
    return (f"python -m quiz2.timings {Path(run_dir).as_posix()} "
            f"{action} {stage}{tail}")


def stamp_note(run_dir, stage: str, label: str) -> str:
    """스폰 문서 맨 끝에 붙일 절. **일꾼이 제 끝을 찍는다.**

    이걸 안 붙이면 그 단계의 `end`가 아무 데서도 안 찍힌다. 붙이는 자리는
    `assemble`·`occlusion`·`reproduce`·`structure`의 스폰 문구 넷이다.

    산출물 하나만 쓰라는 규칙(`assemble.DO_NOT`, `quiz-worker.md` 3번)의 예외라
    **여기서 명시적으로 뚫어 준다.** 안 적으면 일꾼이 규칙끼리 어긋난다고 보고
    멈춘다 — 어긋나 보이면 따르지 말고 보고하라는 것이 그 문서의 지시다.
    """
    return f"""## 마지막에 계측을 찍는다

산출물을 쓴 **뒤에** 이 한 줄을 돌리고 끝낸다.

    {_cmd(run_dir, stage, 'end', [label] if label else None)}

`timings.jsonl`은 산출물이 아니라 곁다리라 「하지 말 것」의 예외다.
**이 줄만 예외이고 다른 파일은 여전히 건드리지 마라.**

찍는 쪽을 네게 옮긴 이유는 값이다 — 같은 한 줄이 오케스트레이터 문맥에서는
16만 토큰, 네 문맥에서는 4만대다 (`260819_03` 실측)."""


def spawn_note(run_dir, stage: str, labels, *, what: str = "서브에이전트") -> str:
    """코드 단계가 오케스트레이터에게 인쇄해 줄 안내. **한 메시지에 넣으라고 적는다.**

    같은 assistant 메시지 안의 도구 호출들은 문맥을 한 번만 읽는다. `start` 한 줄을
    스폰들과 같은 메시지에 넣으면 계측 값이 0이 된다. 따로 보내면 16만 토큰이다.
    """
    # 라벨이 비면 일꾼 하나짜리 단계다 (0.5). 그때도 `start`는 스폰과 같은
    # 메시지에 넣어야 값이 0이 된다 — 개수만 다르고 규칙은 같다.
    many = bool(labels)
    head = (f"{what} {len(labels)}개를 **한 메시지에 함께** 띄운다."
            if many else f"{what} 하나를 띄운다.")
    lines = [
        "",
        head,
        f"  subagent_type: `{WORKER}`  — 도구 넷만 지고 떠서 부팅 문맥이 4분의 1이다",
        ("  각자에게는 " if many else "  ") + "「그 파일을 읽고 그대로 따르라」만 시킨다.",
        "",
        ("  **아래 한 줄을 그 스폰" + ("들" if many else "") +
         "과 같은 메시지에 넣어라.** 따로 보내면 그 한 줄이"),
        "  오케스트레이터 문맥값을 통째로 문다:",
        f"      {_cmd(run_dir, stage, 'start', labels)}",
        "",
        "  `end`는 안 찍어도 된다 — 일꾼이 제 것을 찍는다. 못 찍었으면",
        f"  `python -m quiz2.timings {Path(run_dir).as_posix()} report`의",
        "  「끝을 못 찍은 구간」에 뜬다.",
    ]
    return "\n".join(lines)



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
        print("\n  `start`는 스폰들과 **같은 메시지**에 한 줄로 넣는다:")
        print(f"      {_cmd(run_dir, '2-write', 'start', ['c01', 'c02', 'c03'])}")
        print("  `end`는 일꾼이 제 것을 찍는다 — 스폰 문서 마지막 절이 시킨다.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="v2 단계 계측")
    parser.add_argument("run_dir")
    parser.add_argument("action", choices=["report", "start", "end"])
    parser.add_argument("stage", nargs="?", default=None)
    # 여러 개를 받는다. 조각 스폰과 **같은 메시지**에서 한 줄로 전부 여는 자리다.
    parser.add_argument("--label", nargs="*", default=None)
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
    labels = args.label or [None]
    rows = [record(args.run_dir, args.stage, args.action, label)
            for label in labels]
    if not rows[0]:
        print(f"  안 찍혔다 — {args.run_dir}가 디렉터리가 아니다")
        return 1
    tags = ", ".join(l for l in labels if l)
    print(f"[timings] {args.stage} {args.action}"
          + (f" ({tags})" if tags else "") + f"  {rows[0]['at']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

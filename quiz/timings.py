"""단계별 소요 기록. **재기만 하고 판정하지 않는다.**

`runs/<lecture_id>/timings.jsonl`에 한 줄씩 append한다.

왜 필요한가 - 어디서 줄일지 정하려면 단계별 소요가 있어야 하는데, 예전엔 남는 시각이
`prep.json`의 `prepared_at`과 `run.meta.json`의 `built_at` **둘뿐**이라 그 사이가
통짜였다. 이걸 넣고 나서 완전 분해가 둘 나왔다.

    260814_05  0.5단계 7.0 · 1단계 14.8 · 2단계 21.4(조각 8)  · 4단계 17.9 = 72.2분
    260812_03  0.5단계 3.9 · 1단계 13.9 · 2단계 17.9(조각 12) · 4단계 14.6 = 52.9분

그 값이 실제로 코드를 바꿨다. `quiz/plan_chunks.py`의 회귀 계수(5.9분 + 0.64분/카드,
오클루전 있으면 +4분)가 전부 여기 `--label` 구간에서 나왔다. **그래서 라벨을 빠뜨리면
안 된다** - 라벨이 없으면 벽시계와 작업시간 합이 안 갈리고, 그 둘의 차가 조각화의
값이다(`260812_03`에서 147.4분 / 17.9분 = 8.2배).

두 편이므로 아직 분포가 아니다. 쌓일 때까지 계속 찍어라.

한 번 더 - 재기만 한다. 느리다/빠르다는 판정은 사람이 한다.

## 코드 단계

각 단계의 `main()`이 스스로 찍는다. 아무것도 안 해도 된다.

## 모델 단계

코드가 아니므로 **오케스트레이터가 찍는다.** 서브에이전트를 띄우기 직전과 받은 직후:

    python quiz/timings.py runs/<id> start 1-blueprint
    python quiz/timings.py runs/<id> end   1-blueprint

2단계처럼 동시에 여러 개가 도는 자리는 `--label`로 가른다. 그래야 **벽시계와
작업시간 합**이 갈린다 - 조각화가 줄이는 것은 합이 아니라 벽시계다.

    python quiz/timings.py runs/<id> start 2-write --label c1
    python quiz/timings.py runs/<id> end   2-write --label c1

## 보기

    python quiz/timings.py runs/<id> report
"""

from __future__ import annotations

import argparse
import json
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

FILENAME = "timings.jsonl"


def now() -> str:
    # prep.json의 prepared_at·run.meta.json의 built_at과 같은 꼴로 맞춘다.
    return datetime.now().isoformat(timespec="seconds")


def record(run_dir, stage: str, event: str, label: str | None = None,
           at: str | None = None, **extra) -> dict:
    """한 줄 append. run_dir이 없으면 만들지 않고 조용히 건너뛴다.

    계측 때문에 파이프라인이 죽으면 안 된다 - 이건 곁다리다.

    `at`을 주면 그 시각으로 적는다. 0단계처럼 **run_dir이 생기기 전에 시작하는**
    단계가 자기 시작 시각을 나중에 적을 때 쓴다.
    """
    run_dir = Path(run_dir)
    if not run_dir.is_dir():
        return {}
    row = {"stage": stage, "event": event, "at": at or now()}
    if label:
        row["label"] = label
    row.update(extra)
    try:
        with (run_dir / FILENAME).open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError:
        return {}
    return row


@contextmanager
def stage(run_dir, name: str, label: str | None = None):
    """코드 단계용. 예외가 나도 끝을 남기고 `ok: false`를 붙인다."""
    record(run_dir, name, "start", label)
    ok = True
    try:
        yield
    except BaseException:
        ok = False
        raise
    finally:
        record(run_dir, name, "end", label, ok=ok)


def load(run_dir) -> list[dict]:
    path = Path(run_dir) / FILENAME
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def _spans(rows: list[dict]) -> list[dict]:
    """(stage, label)별로 start와 end를 순서대로 짝지어 구간을 만든다.

    짝이 안 맞는 start는 버린다 - 죽은 단계다. 그것도 정보이므로 세어서 돌려준다.
    """
    open_: dict[tuple, list] = {}
    spans: list[dict] = []
    dangling = 0
    for row in rows:
        key = (row.get("stage"), row.get("label"))
        if row.get("event") == "start":
            open_.setdefault(key, []).append(row)
        elif row.get("event") == "end":
            queue = open_.get(key) or []
            if not queue:
                continue
            start = queue.pop(0)
            try:
                t0 = datetime.fromisoformat(start["at"])
                t1 = datetime.fromisoformat(row["at"])
            except (KeyError, ValueError):
                continue
            spans.append({
                "stage": key[0], "label": key[1],
                "start": t0, "end": t1,
                "seconds": (t1 - t0).total_seconds(),
                "ok": row.get("ok", True),
            })
    dangling = sum(len(v) for v in open_.values())
    for span in spans:
        span["dangling"] = dangling
    return spans


def summarize(run_dir) -> dict:
    """단계별 벽시계와 작업시간 합. **둘을 따로 낸다.**

    2단계는 조각이 동시에 돌아서 둘이 크게 갈린다 - 실측에서 벽시계 8분에
    합 35분이었다. 하나만 보면 조각화의 값을 잘못 읽는다.
    """
    spans = _spans(load(run_dir))
    stages: dict[str, dict] = {}
    for span in spans:
        s = stages.setdefault(span["stage"], {
            "count": 0, "sum_seconds": 0.0, "start": span["start"],
            "end": span["end"], "failed": 0, "labels": [],
        })
        s["count"] += 1
        s["sum_seconds"] += span["seconds"]
        s["start"] = min(s["start"], span["start"])
        s["end"] = max(s["end"], span["end"])
        if not span["ok"]:
            s["failed"] += 1
        if span["label"]:
            s["labels"].append(span["label"])
    for s in stages.values():
        s["wall_seconds"] = (s["end"] - s["start"]).total_seconds()
    total = None
    if spans:
        total = (max(s["end"] for s in spans)
                 - min(s["start"] for s in spans)).total_seconds()
    return {
        "stages": stages,
        "total_wall_seconds": total,
        "spans": len(spans),
        "dangling": spans[0]["dangling"] if spans else 0,
    }


def _fmt(seconds: float | None) -> str:
    if seconds is None:
        return "-"
    return f"{seconds / 60:.1f}분"


def report(run_dir) -> int:
    result = summarize(run_dir)
    if not result["stages"]:
        print(f"[timings] {run_dir}에 기록이 없다. "
              f"코드 단계는 스스로 찍고, 모델 단계는 오케스트레이터가 찍는다.")
        return 0
    order = sorted(result["stages"].items(), key=lambda kv: kv[1]["start"])
    print(f"{'단계':<20}{'횟수':>4}{'벽시계':>10}{'작업합':>10}   비고")
    for name, s in order:
        note = ""
        if s["count"] > 1:
            note = f"{s['count']}개 동시 ({', '.join(s['labels'][:6])})"
        if s["failed"]:
            note = (note + " " if note else "") + f"실패 {s['failed']}"
        print(f"{name:<20}{s['count']:>4}{_fmt(s['wall_seconds']):>10}"
              f"{_fmt(s['sum_seconds']):>10}   {note}")
    print(f"{'합계(벽시계)':<20}{'':>4}{_fmt(result['total_wall_seconds']):>10}")
    if result["dangling"]:
        print(f"  ⚠ 끝이 안 남은 구간 {result['dangling']}개 — 죽었거나 end를 안 찍었다")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="단계별 소요 기록/보기")
    parser.add_argument("run_dir", help="runs/<lecture_id>")
    parser.add_argument("action", choices=["start", "end", "report"])
    parser.add_argument("stage", nargs="?", help="단계 이름 (start/end에 필요)")
    parser.add_argument("--label", default=None, help="동시 실행을 가르는 이름 (예: c1)")
    args = parser.parse_args()

    if args.action == "report":
        return report(Path(args.run_dir))
    if not args.stage:
        parser.error("start/end에는 단계 이름이 필요하다")
    row = record(Path(args.run_dir), args.stage, args.action, args.label)
    if not row:
        print(f"[timings] {args.run_dir}가 없어 건너뛴다")
        return 0
    print(f"[timings] {row['stage']}"
          f"{'/' + row['label'] if row.get('label') else ''} {row['event']} {row['at']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

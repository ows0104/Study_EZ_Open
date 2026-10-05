"""단계마다 시간·비용·토큰을 한 줄씩 적는다.

빈 세션은 저마다 다른 프로세스에서 돈다. run.py 가 직접 띄우는 것(①②·수선)도 있고
reproduce.py 가 하위 프로세스에서 띄우는 것(풀이·채점)도 있다. 그래서 합계를 메모리에
들고 있을 수 없다 — 각자 작업 폴더의 `usage.jsonl` 에 적고, 끝에 모아 읽는다.

**세는 값은 전부 모델 실행 어댑터의 사용량가 이미 주는 것이다.**
따로 재느라 세션을 더 띄우거나 토큰을 더 쓰지 않는다.

한 번의 run.py 실행은 `run` 표로 묶인다. 하위 프로세스는 환경변수 `PDF2ANKI_RUN`
으로 그 표를 물려받으므로, 끊겼다 이어서 돌려도 '이번 실행'과 '이 강의 누적'을
따로 볼 수 있다.
"""

from __future__ import annotations

import json
import os
import time
import unicodedata
from pathlib import Path

LOG = "usage.jsonl"
ENV_RUN = "PDF2ANKI_RUN"

# 봉투의 usage 에서 가져오는 것. 캐시 읽기·쓰기를 입력과 나눠 둔다 —
# 셋을 합쳐 버리면 ②가 ①을 이어받아 아낀 양이 보이지 않는다.
TOKEN_KEYS = ("input_tokens", "output_tokens",
              "cache_creation_input_tokens", "cache_read_input_tokens")
SHORT = {"input_tokens": "입력", "output_tokens": "출력",
         "cache_creation_input_tokens": "캐시쓰기", "cache_read_input_tokens": "캐시읽기"}


def usage_of(env: dict | None) -> dict:
    """이전 Claude 봉투에서 토큰만 뽑는다. 없으면 0으로 채운다."""
    u = (env or {}).get("usage") or {}
    return {k: int(u.get(k) or 0) for k in TOKEN_KEYS}


def models_of(env: dict | None) -> dict[str, int]:
    """어느 모델이 얼마나 냈는지. 봉투의 `modelUsage` 가 이미 들고 있다.

    **이 줄이 없어서 오늘 하루가 갔다.** 2026-08-26에 `260821_03` 을 8-23과 같은
    커밋·같은 자료로 다시 돌렸더니 카드가 78장에서 23장이 됐다. 코드도 입력도
    같다는 것까지는 실험으로 좁혔는데, 남은 변수인 **모델을 어디에도 안 적어 둬서**
    거기서 멈췄다. 값이 흔들렸을 때 무엇이 흔들렸는지 물을 수 있어야 한다.
    """
    mu = (env or {}).get("modelUsage") or {}
    if not isinstance(mu, dict):
        return {}
    out = {}
    for name, v in mu.items():
        if isinstance(v, dict):
            out[str(name)] = int(v.get("outputTokens") or 0)
    return out


def add(dst: dict, src: dict | None) -> dict:
    for k in TOKEN_KEYS:
        dst[k] = int(dst.get(k, 0)) + int((src or {}).get(k) or 0)
    return dst


def add_models(dst: dict, src: dict | None) -> dict:
    for name, n in (src or {}).items():
        dst[name] = int(dst.get(name, 0)) + int(n or 0)
    return dst


def total(u: dict) -> int:
    return sum(int(u.get(k) or 0) for k in TOKEN_KEYS)


def run_id() -> str:
    """이번 실행의 표. 하위 프로세스는 환경변수로 같은 표를 쓴다."""
    return os.environ.get(ENV_RUN) or f"r{int(time.time())}"


def append(out: Path, step: str, *, seconds: float, cost: float | None,
           usage: dict | None = None, sessions: int = 1, note: str = "",
           models: dict[str, int] | None = None) -> None:
    row = {"run": run_id(), "t": round(time.time()), "step": step,
           "seconds": round(float(seconds), 1), "cost_usd": round(float(cost or 0.0), 4),
           "sessions": int(sessions),
           **{k: int((usage or {}).get(k) or 0) for k in TOKEN_KEYS}}
    if models:
        row["models"] = models
    if note:
        row["note"] = note
    with (Path(out) / LOG).open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def read(out: Path) -> list[dict]:
    p = Path(out) / LOG
    if not p.exists():
        return []
    rows = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            pass                       # 반쯤 쓰다 끊긴 줄이 있어도 나머지는 읽는다
    return rows


def fold(rows: list[dict]) -> list[dict]:
    """같은 단계를 하나로 합친다. 처음 나온 순서를 지킨다(파이프라인 순서다)."""
    order, byname = [], {}
    for r in rows:
        name = r.get("step", "?")
        if name not in byname:
            order.append(name)
            byname[name] = {"step": name, "seconds": 0.0, "cost_usd": 0.0, "sessions": 0,
                            **dict.fromkeys(TOKEN_KEYS, 0)}
        acc = byname[name]
        acc["seconds"] += float(r.get("seconds") or 0)
        acc["cost_usd"] += float(r.get("cost_usd") or 0)
        acc["sessions"] += int(r.get("sessions") or 0)
        add(acc, r)
    return [byname[n] for n in order]


def _n(v: int) -> str:
    return f"{v:,}" if v else "·"


def _w(s: str) -> int:
    """터미널에서 차지하는 칸 수. 한글은 두 칸이라 len() 으로 맞추면 표가 어긋난다."""
    return sum(2 if unicodedata.east_asian_width(ch) in "WF" else 1 for ch in s)


def _lj(s: str, w: int) -> str:
    return s + " " * max(0, w - _w(s))


def _rj(s: str, w: int) -> str:
    return " " * max(0, w - _w(s)) + s


COLS = (("단계", 15, _lj), ("세션", 5, _rj), ("시간", 9, _rj), ("비용", 9, _rj),
        ("입력", 10, _rj), ("출력", 10, _rj), ("캐시쓰기", 12, _rj), ("캐시읽기", 12, _rj))
RULE = "─" * sum(c[1] for c in COLS)


def _row(cells: list[str]) -> str:
    return "".join(fn(c, w) for c, (_, w, fn) in zip(cells, COLS, strict=False))


def _dur(s: float) -> str:
    """1분 반이 안 되면 초로 낸다. 0.0분 이 줄줄이 서면 아무것도 못 읽는다."""
    return f"{s:.0f}초" if s < 90 else f"{s / 60:.1f}분"


def _cells(r: dict, name: str) -> list[str]:
    return [name, str(r["sessions"] or "·"), _dur(r["seconds"]),
            ("$%.2f" % r["cost_usd"]) if r["cost_usd"] else "·",
            _n(r["input_tokens"]), _n(r["output_tokens"]),
            _n(r["cache_creation_input_tokens"]), _n(r["cache_read_input_tokens"])]


def table(rows: list[dict], title: str = "") -> str:
    """단계별 한 줄. 사람이 읽는 것이지 파싱하라고 내는 것이 아니다."""
    folded = fold(rows)
    if not folded:
        return ""
    out = ([title] if title else []) + [_row([c[0] for c in COLS]), RULE]
    tot = {"seconds": 0.0, "cost_usd": 0.0, "sessions": 0, **dict.fromkeys(TOKEN_KEYS, 0)}
    for r in folded:
        out.append(_row(_cells(r, r["step"])))
        for k in ("seconds", "cost_usd", "sessions"):
            tot[k] += r[k]
        add(tot, r)
    out += [RULE, _row(_cells(tot, "합계"))]
    used = models_used(rows)
    if used:
        out.append("모델  " + " · ".join(f"{k} ({_n(v)})" for k, v in used.items()))
    return "\n".join(out)


def summarize(out: Path, run: str | None = None) -> dict:
    """`run.report.json` 에 실을 값. 이번 실행과 이 폴더 누적을 함께 낸다."""
    rows = read(out)
    mine = [r for r in rows if run is None or r.get("run") == run]

    def agg(rs: list[dict]) -> dict:
        t = {"seconds": 0.0, "cost_usd": 0.0, "sessions": 0, **dict.fromkeys(TOKEN_KEYS, 0)}
        for r in rs:
            t["seconds"] += float(r.get("seconds") or 0)
            t["cost_usd"] += float(r.get("cost_usd") or 0)
            t["sessions"] += int(r.get("sessions") or 0)
            add(t, r)
        t["seconds"] = round(t["seconds"], 1)
        t["cost_usd"] = round(t["cost_usd"], 4)
        t["tokens_total"] = total(t)
        return t

    return {"run": run, "this_run": agg(mine), "cumulative": agg(rows),
            "models": models_used(mine), "models_cumulative": models_used(rows),
            "steps": fold(mine), "rows": mine}


def models_used(rows: list[dict]) -> dict[str, int]:
    """이 실행에 실제로 답을 낸 모델들. 출력 토큰이 많은 쪽이 주 모델이다."""
    out: dict[str, int] = {}
    for r in rows:
        for name, n in (r.get("models") or {}).items():
            out[name] = out.get(name, 0) + int(n or 0)
    return dict(sorted(out.items(), key=lambda kv: -kv[1]))

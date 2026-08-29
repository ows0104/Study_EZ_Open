"""복습·예습 러너가 같이 쓰는 배관. **판단은 한 줄도 들어오지 않는다.**

두 파이프라인은 목적 함수가 다르다(`CLAUDE.md` 첫 절). 그래서 무엇을 낼지·
무엇을 결함으로 볼지·어디까지 수선할지는 **각자 갖는다.** 여기 있는 것은 그런
결정이 하나도 없는 것들뿐이다 — 산출물이 있으면 건너뛰고, 원장에 시간과 비용을
적고, 하위 프로세스를 띄우고, 세션을 이어 붙이는 일.

가른 기준은 「고치면 양쪽이 같이 틀리는가」다. `step` 의 원장 기록에 버그가 있으면
두 파이프라인이 똑같이 틀린다 — 그런 것만 여기 있다. 반대로 `repair` 는 예습이
계약 위반까지 고치고 복습은 안 고치므로 여기 없고, `reproduce` 는 예습만
`--skip-reproduce` 를 받으므로 여기 없고, `prep` 은 실패 메시지가 다르므로 없다.

**여기에 `if 예습이면` 을 쓰고 싶어지면 그건 여기 올 것이 아니다.**
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

from . import ledger
from .build import DEFECT_REASONS
from .prompting import DEFAULT_DOMAIN
from .session import run_agent

PY = sys.executable


class Failed(RuntimeError):
    pass


class BaseRunner:
    """한 편을 만드는 러너의 공통 부분. 그대로는 쓰지 않는다 — 상속해서 쓴다."""

    def __init__(self, out: Path, args):
        self.out, self.args = out, args
        self.args.domain = getattr(args, "domain", None) or DEFAULT_DOMAIN
        self.cost = 0.0
        self.t0 = time.time()
        self.sid: str | None = None      # ① 세션. ②·수선이 이어받아 자료를 다시 안 읽는다
        # 이번 실행의 표를 한 번만 정하고 환경에 박는다. 이 프로세스가 적는 줄도,
        # 하위 프로세스(reproduce)가 적는 줄도 같은 표를 달아야 '이번 실행'이 묶인다.
        self.run = ledger.run_id()
        os.environ[ledger.ENV_RUN] = self.run
        self.pend_cost, self.pend_usage, self.pend_sessions = 0.0, {}, 0
        self.pend_models = {}

    # ------------------------------------------------------------ 산출물

    def made(self, produces: str | None) -> bool:
        """산출물이 있는가. `*` 를 쓸 수 있다 — 프롬프트는 커지면 파트로 갈린다."""
        if not produces:
            return False
        if "*" in produces:
            return any(self.out.glob(produces))
        return (self.out / produces).exists()

    def defects(self) -> list[dict]:
        """재현 검사가 **카드 결함**으로 가른 것만. lecture_specific·genuinely_wrong 은 아니다."""
        f = self.out / "items.reproduced.json"
        if not f.exists():
            return []
        cards = json.loads(f.read_text(encoding="utf-8"))["cards"]
        return [c for c in cards
                if (c.get("reproduce") or {}).get("reason") in DEFECT_REASONS]

    # ------------------------------------------------------------ 실행

    def sh(self, *argv: str, ok: tuple = (0,)) -> int:
        """`ok` 에 없는 종료코드면 멈춘다.

        예습의 `validate` 는 계약 위반에 2 를 낸다. 그것까지 죽으면 **한 줄 실행이
        깨진다** — 사람이 `--allow-size` 를 붙여 다시 불러야 하기 때문이다. 2 는
        받아 두고 수선 루프가 처리한다. 복습은 `ok` 를 안 주므로 예전대로 0 만 받는다.
        """
        r = subprocess.run([PY, "-m", *argv], cwd=Path.cwd(),
                           env={**os.environ, "PYTHONIOENCODING": "utf-8",
                                ledger.ENV_RUN: self.run})
        if r.returncode not in ok:
            raise Failed(f"명령 실패: {' '.join(argv)}")
        return r.returncode

    def step(self, name: str, produces: str | None, fn):
        """산출물이 있으면 건너뛴다. 재개가 공짜가 되는 지점이다."""
        if produces and self.made(produces) and not self.args.force:
            print(f"[건너뜀] {name}  ({produces} 이미 있음)", flush=True)
            return
        print(f"\n── {name}", flush=True)
        n0 = len(ledger.read(self.out))
        t = time.time()
        self.pend_cost, self.pend_usage, self.pend_sessions = 0.0, {}, 0
        self.pend_models = {}
        fn()
        # 하위 프로세스가 스스로 적었으면(재현 검사) 여기서 또 적지 않는다. 시간이 겹친다.
        if len(ledger.read(self.out)) == n0:
            ledger.append(self.out, name, seconds=time.time() - t, cost=self.pend_cost,
                          usage=self.pend_usage, sessions=self.pend_sessions,
                          models=self.pend_models)
        if produces and not self.made(produces):
            raise Failed(f"{name}: {produces} 가 생기지 않았다")

    # ------------------------------------------------------------ 모델

    def prompt_extra(self) -> str:
        """이 강의에만 얹는 지시. **여기가 두 파이프라인이 갈리는 자리다.**

        복습은 채널 위계 변경(`--annotation-evidence`)과 `--note` 를 얹고, 예습은
        `--hint` 를 얹는다. 얹을 것이 없으면 빈 문자열이다.
        """
        return ""

    def agent(self, prompt: str, label: str, resume: bool = False):
        """빈 세션에 프롬프트를 던지고 비용·토큰을 이번 단계 몫으로 쌓는다."""
        prompt += self.prompt_extra()
        res = run_agent(prompt, cwd=Path.cwd(), model=self.args.model,
                        timeout=self.args.timeout, label=label,
                        resume=self.sid if resume else None)
        self.cost += res.get("cost_usd") or 0.0
        self.pend_cost += res.get("cost_usd") or 0.0
        self.pend_sessions += 1
        ledger.add(self.pend_usage, res.get("usage"))
        ledger.add_models(self.pend_models, res.get("models"))
        if res.get("session_id"):
            self.sid = res["session_id"]
        for line in (res.get("text") or "").strip().splitlines()[-6:]:
            print(f"   {line[:110]}", flush=True)
        return res

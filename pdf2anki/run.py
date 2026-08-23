"""강의 하나를 명령 한 줄로 덱까지 굽는다.

각 단계는 이미 따로 돌릴 수 있다. 이 모듈은 순서를 알고 있고, 사람이 앉아 있어야만
넘어갈 수 있었던 두 칸 — ① 학습목표와 ② 카드 — 을 빈 세션에 맡겨 이어 붙인다.

    prep → 전략 판정 → assemble → ①목표 → 승인 → ②카드 → validate
         → 누출수선 → 재현검사(+수선) → 누출재확인 → build

**이름은 파일이 정한다.** 덱은 `<과목>::<PDF 파일제목>`, 강의 ID 는 파일명 앞머리의
`[260820_03]` 에서 딴다. 사람이 강의 번호와 제목을 손으로 옮겨 적을 일이 없다 —
29강을 돌리는 동안 그 손이 틀리는 것이 실제 위험이다.

**전략은 코드가 정한다.** 족보 조각의 교수 교체 여부와 연도간 반복률을 보고
필기 중심 / 족보 중심 / 기본 중 하나를 고른다. 교수가 바뀌었으면 `--annotation-evidence`
도 자동으로 켠다 — 사람이 매번 index.json 을 열어 확인하던 일이다. `--strategy` 로 덮는다.

**재개할 수 있다.** 각 단계는 자기 산출물이 이미 있으면 건너뛴다. 중간에 끊겨도
`--resume <폴더>` 한 줄이면 남은 데서 이어진다(덱 이름도 그 폴더가 기억한다).
처음부터 다시 하려면 --force.

**수선 고리가 둘이다.** 재현 검사에서 결함으로 갈린 카드가 있으면 그 카드만 다시 쓰게 하고
검사를 다시 돌린다. 사람이 손으로 반복하던 일이고, 붙여 보니 대개 두 바퀴 안에 0이 된다.
**앞면이 답을 흘리는 카드(누출)에도 같은 고리를 건다.** 누출 검사는 풀이 전에 도는
결정론적 검사라 그 앞에 놓을 수 있고, 깨끗하면 공짜다. 24강 일괄 실행에서 멈춘 7건 중
4건이 누출이었고 전부 사람이 카드 한 장 고치고 재개하면 끝나는 일이었다.
수선이 카드를 다시 쓰면 누출이 새로 생길 수 있어 빌드 직전에 한 번 더 본다.

**장부.** 단계마다 시간·비용·토큰을 `usage.jsonl` 에 적고 끝에 표로 낸다.
값은 `claude -p` 봉투가 이미 주는 것이라 재느라 토큰을 더 쓰지 않는다.

사람이 꼭 봐야 하는 것은 둘뿐이다.
  - 학습목표 목록 (빠진 게 있는지) — 기본은 출력만 하고 지나간다. --stop-at-review 로 세운다.
  - 이미지 카드 접촉 시트 (앞면 크롭에 정답이 인쇄됐는지) — 코드가 못 잡는 유일한 결함이다.
    끝나면 `out/_image_check/` 에 모아 둔다. 눈으로 볼 것이 한 폴더에 쌓인다.

사용:
    python -m pdf2anki.run "필기.pdf"
    python -m pdf2anki.run --resume out/p260820_03
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
import unicodedata
from pathlib import Path

from . import ledger
from .assemble import STRATEGIES, STRATEGY_ALIAS, decide_strategy, slice_for
from .pack import lecture_of
from .build import DEFECT_REASONS
from .session import SessionError, run_agent

PROMPTS = Path(__file__).parent / "prompts"
PY = sys.executable
CONFIG = "run.config.json"       # 덱 이름·전략을 폴더가 기억한다 (--resume 이 한 줄이 되게)


class Failed(RuntimeError):
    pass


# ── 이름 짓기 ──────────────────────────────────────────────────────
def lecture_id_of(pdf: Path) -> str:
    """파일명 앞머리의 `[260820_03]` 을 강의 ID 로 쓴다.

    날짜+교시라 과목 안에서 유일하고, 다시 돌려도 같은 값이 나온다.
    guid 의 씨앗이므로 **바뀌면 Anki 가 전부 새 노트로 본다.** 파일명에서 따는 이유다.
    """
    stem = unicodedata.normalize("NFC", pdf.stem)   # 아카이브에 NFD 파일명이 섞여 있다
    m = re.match(r"\s*\[(\d{6})_(\d{2})\]", stem)
    if m:
        return f"p{m.group(1)}_{m.group(2)}"
    slug = re.sub(r"[^0-9A-Za-z가-힣]+", "-", stem).strip("-")
    return slug[:40] or "lecture"


def deck_of(lecture: str, subject: str) -> str:
    """`<과목>::<강의명>`. `build` 가 여기에 `::강의록`·`::기출` 을 단다.

    강의명은 `--lecture` 로 주고, 안 주면 `pack.lecture_of` — 파일제목 원문이다.
    과목은 `--subject`, 안 주면 그냥 `과목`. 빈 문자열이면 앞머리를 안 붙인다.

    하위 덱을 `::예습` `::강의록` `::기출` 로 나눠 둔 것은 **작년 필기본으로 만든 예습 덱과
    올해 필기본으로 만든 복습 덱을 한 노드에 세우기** 위해서다. 다만 파일명이 해마다 다르므로
    그 노드는 저절로 모이지 않는다 — 양쪽에 `--lecture` 로 같은 값을 줘야 모인다.
    어느 필기본에서 나왔는지는 덱 이름이 아니라 `강의::<lecture_id>` 태그와
    `run.config.json` 이 기억한다.

    `--lecture` 로 두 강의를 한 노드에 몰아도 guid 는 `lecture_id` 를 씨앗으로 쓰므로
    노트끼리는 섞이지 않는다. 그래도 조용히 합치지는 않는다 — `deck_siblings` 가 알린다.
    """
    name = lecture.replace("::", "-")           # Anki 의 하위덱 구분자와 부딪히지 않게만 손본다
    return f"{subject}::{name}" if subject else name


def deck_siblings(out: Path, deck: str, lecture_id: str) -> list[str]:
    """같은 덱 노드를 이미 쓰고 있는 다른 강의를 찾는다.

    한 강의가 두 교시에 걸쳤으면 합쳐지는 것이 맞지만, 제목만 우연히 같은 별개 강의일
    수도 있다. 어느 쪽인지는 코드가 모른다. 사람이 보게 알리기만 한다.
    """
    found = []
    for cfg in sorted(out.parent.glob(f"*/{CONFIG}")):
        try:
            c = json.loads(cfg.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if c.get("deck") == deck and c.get("id") and c["id"] != lecture_id:
            found.append(f"{c['id']}  {c.get('pdf_name', '')}".strip())
    return found


class Runner:
    def __init__(self, out: Path, args):
        self.out, self.args = out, args
        self.cost = 0.0
        self.t0 = time.time()
        self.sid: str | None = None      # ① 세션. ②·수선이 이어받아 자료를 다시 안 읽는다
        # 이번 실행의 표를 한 번만 정하고 환경에 박는다. 이 프로세스가 적는 줄도,
        # 하위 프로세스(reproduce)가 적는 줄도 같은 표를 달아야 '이번 실행'이 묶인다.
        self.run = ledger.run_id()
        os.environ[ledger.ENV_RUN] = self.run
        self.pend_cost, self.pend_usage, self.pend_sessions = 0.0, {}, 0
        self.strategy: str = "base"
        self.strategy_why: str = ""
        # 전략 판정 전까지의 잠정값. 사람이 깃발로 켰으면 그대로 산다.
        self.annotation: bool = bool(getattr(args, "annotation_evidence", False))

    # ── 하위 명령 ──────────────────────────────────────────────
    def made(self, produces: str | None) -> bool:
        """산출물이 있는가. `*` 를 쓸 수 있다 — 프롬프트는 커지면 파트로 갈린다."""
        if not produces:
            return False
        if "*" in produces:
            return any(self.out.glob(produces))
        return (self.out / produces).exists()

    def prompt_path(self, stage: str) -> Path:
        """모델에게 읽힐 프롬프트의 첫 파일.

        `assemble` 은 Read 의 25k 토큰 상한 때문에 프롬프트를 파트로 나눈다. 그러면
        `prompt.cards.md` 는 아예 생기지 않고 `prompt.cards.1of2.md` 가 대신 선다
        (파트 1이 나머지를 읽으라는 목록을 달고 있다). 그 이름을 고정으로 쓰면
        갈린 강의에서만 조용히 멈춘다 — 실제로 순환장애 두 강의가 여기서 멈췄다.
        """
        one = self.out / f"prompt.{stage}.md"
        if one.exists():
            return one
        parts = sorted(self.out.glob(f"prompt.{stage}.1of*.md"))
        if parts:
            return parts[0]
        raise Failed(f"prompt.{stage}.md 도 prompt.{stage}.1ofN.md 도 없다")

    def step(self, name: str, produces: str | None, fn):
        """산출물이 있으면 건너뛴다. 재개가 공짜가 되는 지점이다."""
        if produces and self.made(produces) and not self.args.force:
            print(f"[건너뜀] {name}  ({produces} 이미 있음)", flush=True)
            return
        print(f"\n── {name}", flush=True)
        n0 = len(ledger.read(self.out))
        t = time.time()
        self.pend_cost, self.pend_usage, self.pend_sessions = 0.0, {}, 0
        fn()
        # 하위 프로세스가 스스로 적었으면(재현 검사) 여기서 또 적지 않는다. 시간이 겹친다.
        if len(ledger.read(self.out)) == n0:
            ledger.append(self.out, name, seconds=time.time() - t, cost=self.pend_cost,
                          usage=self.pend_usage, sessions=self.pend_sessions)
        if produces and not self.made(produces):
            raise Failed(f"{name}: {produces} 가 생기지 않았다")

    def sh(self, *argv: str):
        r = subprocess.run([PY, "-m", *argv], cwd=Path.cwd(),
                           env={**os.environ, "PYTHONIOENCODING": "utf-8",
                                ledger.ENV_RUN: self.run})
        if r.returncode:
            raise Failed(f"명령 실패: {' '.join(argv)}")

    ANNOTATION_POLICY = """

## 채널 위계 변경 — 올해 필기는 근거다

이 강의는 **담당 교수가 올해 바뀌었다.** 강의록은 작년 것이 그대로 쓰이지만
올해 교수가 실제로 말한 것은 필기에만 남아 있다. 그래서 이 강의에 한해:

- **올해(2026) 필기의 의학적 내용은 질문·정답의 근거로 쓸 수 있다.**
  `evidence_type=annotation` 을 쓰고, 기출 근거가 없어도 된다.
- **필기는 강의록과 같은 급이다. 그 위가 아니다.** 어느 한쪽이 다른 쪽을 이기지 않는다.
  둘이 어긋나면 **어느 쪽도 임의로 택하지 마라** — 카드는 강의록을 따라 내고,
  필기가 무엇이라 했는지를 `review_note` 에 적어 사람이 보게 한다.
- 다만 **의학적 정보일 때만이다.** 교수 잡담·필기자 사담·진로 이야기·시험 요령·
  인사말은 여전히 근거가 아니고 카드도 아니다. 그 구분은 네가 한다.
- 작년 이전 필기는 이전 교수의 강의다. 올해 필기와 어긋나면 올해 것을 쓴다.
"""

    def agent(self, prompt: str, label: str, resume: bool = False):
        if self.annotation:
            prompt += self.ANNOTATION_POLICY
        if self.args.note:
            # 사람이 이 강의에만 걸어 두는 지시. 프롬프트 파일을 고치지 않고 얹는다.
            prompt += ("\n\n## 이 강의에 대한 사용자 지시 (프롬프트보다 우선한다)\n\n"
                       + self.args.note + "\n")
        res = run_agent(prompt, cwd=Path.cwd(), model=self.args.model,
                        timeout=self.args.timeout, label=label,
                        resume=self.sid if resume else None)
        self.cost += res.get("cost_usd") or 0.0
        self.pend_cost += res.get("cost_usd") or 0.0
        self.pend_sessions += 1
        ledger.add(self.pend_usage, res.get("usage"))
        if res.get("session_id"):
            self.sid = res["session_id"]
        tail = (res.get("text") or "").strip().splitlines()
        for line in tail[-6:]:
            print(f"   {line[:110]}", flush=True)
        return res

    # ── 단계 ──────────────────────────────────────────────────
    def prep(self):
        if not self.args.pdf:
            raise Failed("prep.json 이 없는데 PDF 경로도 모른다. PDF 를 인자로 줘라")
        self.sh("pdf2anki.prep", str(self.args.pdf), "-o", str(self.out))

    def plan_strategy(self):
        """족보 조각의 통계에서 이번 강의의 전략을 정한다.

        축은 하나다 — 이번 시험의 출제자가 누구의 강조점을 물을 것인가.
        교수 교체를 반복률보다 **먼저** 본다. 16-18강(반복률 72%·교수 교체)에서
        순서를 뒤집으면 이전 교수의 기출을 쫓는, 정확히 틀린 덱이 나온다.
        """
        prep = json.loads((self.out / "prep.json").read_text(encoding="utf-8"))
        path, stats, mixed = slice_for(prep, Path(self.args.jokbo_dir), self.args.jokbo)
        auto, why = decide_strategy(stats, mixed)
        chosen = STRATEGY_ALIAS[self.args.strategy]
        if chosen == "auto":
            self.strategy, self.strategy_why = auto, why
        else:
            self.strategy = chosen
            self.strategy_why = f"사람이 --strategy 로 지정했다 (자동 판정은 {STRATEGIES[auto]})"

        # 필기 중심이면 올해 필기를 근거로 인정한다. 그것이 이 전략의 실체다.
        self.annotation = self.strategy == "annotation"
        if self.args.annotation_evidence:
            self.annotation = True
        if self.args.no_annotation_evidence:
            self.annotation = False

        print(f"   족보 조각 : {path.name if path else '없음'}"
              f"{'  (주인은 다른 강의)' if mixed else ''}")
        if stats:
            print(f"   반복률 {stats.get('repeat_rate', 0):.0%} · 가중치 "
                  f"{stats.get('jokbo_weight_hint', '?')}"
                  f"{' · 교수 교체' if stats.get('professor_changed_2026') else ' · 교수 유임'}")
        print(f"   전략   : {STRATEGIES[self.strategy]} — {self.strategy_why}")
        print("   필기 근거 인정: " + ("예 (--annotation-evidence 상당)"
                                 if self.annotation else "아니오"))
        self.save_config()

    def assemble(self):
        argv = ["pdf2anki.assemble", str(self.out), "--jokbo-dir", self.args.jokbo_dir,
                "--strategy", self.strategy]
        if self.args.jokbo:
            argv += ["--jokbo", self.args.jokbo]
        self.sh(*argv)

    def plan(self):
        self.agent(f"{self.prompt_path('plan').resolve().as_posix()} 를 읽고 "
                   "그 안의 지시를 그대로 수행해라. 끝나면 무엇을 몇 개 세웠는지 한 줄로만 보고해라.",
                   "①학습목표")

    def approve(self):
        self.sh("pdf2anki.review", str(self.out))
        print((self.out / "plan.review.md").read_text(encoding="utf-8"))
        if self.args.stop_at_review:
            print("\n검토하고 이어서 돌려라 (승인은 자동으로 된다):", flush=True)
            print(f"   python -m pdf2anki.run --resume {self.out.as_posix()}")
            raise SystemExit(0)
        self.sh("pdf2anki.review", str(self.out), "--approve")

    def cards(self):
        # ① 세션을 이어받으면 46쪽 PDF와 사이드카를 다시 읽지 않고, 자기가 세운 목표를 안다.
        cont = ("이어서 ② 를 한다. " if self.sid else "")
        self.agent(f"{cont}{self.prompt_path('cards').resolve().as_posix()} 를 읽고 "
                   "그 안의 지시를 그대로 수행해라. "
                   + ("앞서 읽은 자료는 다시 읽지 않아도 된다. " if self.sid else "")
                   + "끝나면 카드를 몇 장 냈는지 한 줄로만 보고해라.",
                   "②카드", resume=bool(self.sid))

    def validate(self):
        argv = ["pdf2anki.validate", str(self.out / "items.raw.json"),
                "--prep", str(self.out / "prep.json")]
        if self.annotation:
            argv += ["--annotation-evidence"]
        jk = self.jokbo_slice()
        if jk:
            argv += ["--jokbo", str(jk)]
        self.sh(*argv)

    def jokbo_slice(self) -> Path | None:
        prep = json.loads((self.out / "prep.json").read_text(encoding="utf-8"))
        path, _, _ = slice_for(prep, Path(self.args.jokbo_dir), self.args.jokbo)
        return path

    # ── 재현 검사와 수선 ───────────────────────────────────────
    def defects(self) -> list[dict]:
        f = self.out / "items.reproduced.json"
        if not f.exists():
            return []
        cards = json.loads(f.read_text(encoding="utf-8"))["cards"]
        return [c for c in cards
                if (c.get("reproduce") or {}).get("reason") in DEFECT_REASONS]

    def reproduce(self, only: list[str] | None = None):
        """only 를 주면 그 카드만 다시 풀고 채점한다. 나머지 결과는 그대로 살아 있다."""
        if not only:
            for f in ("reproduce.answers.json", "reproduce.grades.json",
                      "items.reproduced.json"):
                (self.out / f).unlink(missing_ok=True)
        argv = ["pdf2anki.reproduce", "check", str(self.out), "--jobs", str(self.args.jobs)]
        if only:
            argv += ["--only", ",".join(only)]
        if self.args.model:
            argv += ["--model", self.args.model]
        self.sh(*argv)

    def leak_repair(self):
        """앞면이 답을 흘리는 카드를 수선 고리로 흘려보낸다.

        누출 검사는 풀이 **전**에 도는데, 원래는 여기서 그냥 멈췄다 — 수선 고리는
        *채점 뒤* `DEFECT_REASONS` 로 갈린 카드만 다시 쓰기 때문에 손이 닿지 않았다.
        24강을 일괄로 돌려 보니 **멈춘 7건 중 4건이 이것**이었고, 넷 다 사람이 카드
        한 장을 고치고 `--resume` 하면 끝나는 일이었다. 같은 고리를 앞에도 놓는다.

        검사 자체는 결정론적이고 세션도 돈도 안 든다. 누출이 없으면 이 단계는 공짜다.
        """
        from .reproduce import LEAK_FIX, LEAK_SAYS, hard_leaks
        for rnd in range(1, self.args.repair_rounds + 1):
            bad = hard_leaks(self.out)
            if not bad:
                return
            print(f"\n── 누출 수선 {rnd}/{self.args.repair_rounds}  "
                  f"(앞면이 답을 흘리는 카드 {len(bad)}장)", flush=True)
            for x in bad:
                print(f"   [{x['kind']}] {x['id']}: {x['card']['q'][:60]}", flush=True)
            t = time.time()
            self.pend_cost, self.pend_usage, self.pend_sessions = 0.0, {}, 0
            body = [f"### [{x['kind']}] {x['card']['q']}\n"
                    f"- 새어 나간 것: {x['detail']!r} — {LEAK_SAYS[x['kind']]}\n"
                    f"- 원래 답: {x['card']['a']}\n"
                    f"- 고치는 방향: {LEAK_FIX[x['kind']]}" for x in bad]
            raw = (self.out / "items.raw.json").resolve().as_posix()
            task = (PROMPTS / "repair_leak.md").read_text(encoding="utf-8").replace("{raw}", raw)
            self.agent(task + "\n\n" + "\n\n".join(body), f"누출수선{rnd}",
                       resume=bool(self.sid))
            ledger.append(self.out, "누출 수선", seconds=time.time() - t, cost=self.pend_cost,
                          usage=self.pend_usage, sessions=self.pend_sessions)

            # **고치는 대상은 items.raw.json 이다.** checked 만 고치면 다음 `validate()` 가
            # raw 에서 다시 만들면서 조용히 되돌린다 — 24강 실행에서 손으로 고친 세 장이
            # 정확히 그렇게 덱까지 흘러 들어갔다.
            self.validate()              # items.raw.json → items.checked.json 다시
            ids = sorted({x["id"] for x in bad})
            if (self.out / "items.reproduced.json").exists():
                # 수선 뒤 재확인이다. 다시 검사해 두지 않으면 빌드가 읽는 파일에
                # 낡은 질문이 남는다 (빌드 입력은 items.reproduced.json 이다).
                self.reproduce(only=ids)
            left = hard_leaks(self.out)
            if len(left) >= len(bad):
                print("   누출이 줄지 않았다. 수선을 멈춘다 — "
                      "재현 검사가 여기서 다시 막을 것이다.", flush=True)
                return

    def repair(self):
        """결함 카드를 다시 쓰게 하고 검사를 다시 돈다. 줄지 않으면 그만둔다."""
        for rnd in range(1, self.args.repair_rounds + 1):
            bad = self.defects()
            if not bad:
                return
            print(f"\n── 수선 {rnd}/{self.args.repair_rounds}  (결함 {len(bad)}장)", flush=True)
            t = time.time()
            self.pend_cost, self.pend_usage, self.pend_sessions = 0.0, {}, 0
            raw = (self.out / "items.raw.json").resolve().as_posix()
            body = []
            for c in bad:
                r = c["reproduce"]
                body.append(f"### [{r['reason']}] {c['q']}\n"
                            f"- 원래 답: {c['a']}\n"
                            f"- 질문만 보고 다시 푼 답: {r.get('reproduced_answer') or '(풀 수 없다고 답함)'}\n"
                            f"- 채점 메모: {r.get('note') or ''}")
            task = (PROMPTS / "repair.md").read_text(encoding="utf-8").replace("{raw}", raw)
            self.agent(task + "\n\n" + "\n\n".join(body), f"수선{rnd}",
                       resume=bool(self.sid))
            ledger.append(self.out, "수선", seconds=time.time() - t, cost=self.pend_cost,
                          usage=self.pend_usage, sessions=self.pend_sessions)

            ids = [c["id"] for c in bad if c.get("id")]
            self.validate()
            self.reproduce(only=ids)     # 고친 카드만 다시 검사한다
            if len(self.defects()) >= len(bad):
                print("   결함이 줄지 않았다. 수선을 멈춘다.", flush=True)
                return

    def build(self):
        # `--jokbo-dir` 을 넘기지 않으면 build 가 자기 기본값(`out/jokbo`)을 본다.
        # 조각을 다른 곳에 두고 돌리면 **기출 카드의 원문과 지면이 통째로 빠진 채**
        # 덱이 나온다 — 카드는 멀쩡해 보이고 뒷면만 비어서 티가 안 난다.
        # 예습 쪽(`prequiz/run.py`)은 처음부터 넘기고 있었다.
        argv = ["pdf2anki.build", str(self.out), "--deck", self.args.deck,
                "--id", self.args.id, "--jokbo-dir", self.args.jokbo_dir]
        if self.args.apkg_name:
            argv += ["--apkg-name", self.args.apkg_name]
        if self.args.jokbo:
            argv += ["--jokbo", self.args.jokbo]
        if self.defects():
            # 여기서 멈추지 않는 이유는 사람이 덱을 열어 봐야 무엇이 문제인지 알기
            # 때문이다. 대신 결함 id 가 run.meta.json 의 `reproduce_defects` 에 남고,
            # studyez.gate 가 그걸 읽어 **배포를 막는다.** 나가는 것을 막는 자리는
            # 빌드가 아니라 거기다 — 문서가 한동안 반대로 적고 있었다.
            print(f"⚠ 재현 불가 {len(self.defects())}장이 남았다. 그대로 덱에 넣는다.\n"
                  "   이 덱은 배포가 막힌다 (studyez.gate 의 reproduce_defects 검사). "
                  "고쳐 다시 굽거나, 사람이 보고 괜찮으면 publish 를 --no-gate 로 민다.",
                  flush=True)
            argv += ["--allow-defects"]
        self.sh(*argv)

    # ── 검수 자료와 장부 ───────────────────────────────────────
    def collect_check(self) -> Path | None:
        """이미지 카드 접촉 시트를 한 폴더에 모은다.

        앞면 크롭 안에 정답이 인쇄돼 있는지는 **코드가 못 잡는다.** 강의마다 폴더를
        찾아 들어가지 않고 한자리에서 훑을 수 있어야 실제로 보게 된다.
        """
        src = self.out / f"{self.args.id}_image_check.pdf"
        if not src.exists() or self.args.no_image_check:
            return None
        dst_dir = Path(self.args.check_dir)
        dst_dir.mkdir(parents=True, exist_ok=True)
        dst = dst_dir / f"{Path(self.args.pdf_name).stem}_image_check.pdf"
        shutil.copy2(src, dst)
        return dst

    def save_config(self):
        """덱 이름·전략을 폴더가 기억한다. --resume 이 한 줄이 되는 이유다."""
        (self.out / CONFIG).write_text(json.dumps(
            {"deck": self.args.deck, "id": self.args.id, "pdf": str(self.args.pdf or ""),
             "pdf_name": self.args.pdf_name, "subject": self.args.subject,
             "lecture": self.args.lecture, "strategy": self.strategy,
             "strategy_why": self.strategy_why, "annotation_evidence": self.annotation},
            ensure_ascii=False, indent=2), encoding="utf-8")

    def report(self, check: Path | None):
        rep = ledger.summarize(self.out, self.run)
        rep.update({"deck": self.args.deck, "id": self.args.id,
                    "pdf": self.args.pdf_name, "strategy": self.strategy,
                    "strategy_why": self.strategy_why,
                    "annotation_evidence": self.annotation,
                    "wall_seconds": round(time.time() - self.t0, 1),
                    "image_check": str(check) if check else None})
        (self.out / "run.report.json").write_text(
            json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")

        print("\n" + ledger.table(rep["rows"], "── 이번 실행"))
        cum = rep["cumulative"]
        if abs(cum["cost_usd"] - rep["this_run"]["cost_usd"]) > 1e-6:
            print(f"\n이 강의 누적: {cum['seconds'] / 60:.0f}분 · ${cum['cost_usd']:.2f} "
                  f"· 토큰 {cum['tokens_total']:,} (앞선 실행 포함)")
        print(f"\n벽시계 {rep['wall_seconds'] / 60:.0f}분  (단계 합계와 다르다 — "
              "재현 검사는 세션을 동시에 돌린다)")

    # ── 전체 ──────────────────────────────────────────────────
    def all(self):
        self.step("자료 준비 (prep)", "prep.json", self.prep)
        self.step("전략 판정", None, self.plan_strategy)
        self.step("프롬프트 조립", "prompt.cards*.md", self.assemble)
        self.step("① 학습목표", "plan.json", self.plan)
        self.step("계획 검토·승인", "plan.approved.json", self.approve)
        self.step("② 카드", "items.raw.json", self.cards)
        self.step("기계 검증", "items.checked.json", self.validate)
        # 누출은 풀이 전에 걸린다. 여기서 고쳐 두지 않으면 재현 검사가 통째로 멈춘다.
        self.step("누출 수선", None, self.leak_repair)
        self.step("재현 검사", "items.reproduced.json", self.reproduce)
        self.repair()
        # 수선이 카드를 다시 썼다면 누출이 새로 생겼을 수 있다. 덱에 들어가기 전 마지막 관문.
        self.step("누출 재확인", None, self.leak_repair)
        self.step("덱 빌드", None, self.build)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="강의 하나를 명령 한 줄로 덱까지 굽는다")
    ap.add_argument("pdf", nargs="?", help="필기 PDF. --resume 이면 생략할 수 있다")
    ap.add_argument("--deck", help='덱 전체 이름. 주면 --subject·--lecture 를 덮는다')
    ap.add_argument("--subject", default="과목",
                    help="덱의 첫 마디. 기본 '과목'. 빈 문자열이면 앞머리를 안 붙인다")
    ap.add_argument("--lecture", help="덱의 가운데 마디. 기본은 파일제목 원문")
    ap.add_argument("--id", help="강의 ID (태그·파일명·guid). 기본은 파일명의 [260820_03]")
    ap.add_argument("-o", "--out", help="작업 폴더. 기본 out/<id>")
    ap.add_argument("--resume", help="이 폴더에서 이어서 돌린다 (pdf·덱 이름 생략 가능)")
    ap.add_argument("--jokbo-dir", default="out/jokbo")
    ap.add_argument("--jokbo", help="족보 조각 json. 생략하면 목차 제목으로 자동 대조")
    ap.add_argument("--apkg-name", help="덱 파일 이름 (확장자 없이). 기본은 강의 ID")
    ap.add_argument("--strategy", default="auto", choices=sorted(STRATEGY_ALIAS),
                    help="필기/족보/기본 중 무엇을 축으로 삼을지. "
                         "auto(기본)면 교수 교체·반복률에서 판정한다")
    ap.add_argument("--model", help="빈 세션에 쓸 모델. 생략하면 CLI 기본값")
    ap.add_argument("--timeout", type=int, default=3600, help="세션 하나의 제한 시간(초)")
    ap.add_argument("--jobs", type=int, default=4,
                    help="재현 검사에서 동시에 띄울 빈 세션 수")
    ap.add_argument("--repair-rounds", type=int, default=2,
                    help="재현 불가 카드를 다시 쓰게 할 최대 횟수 (0이면 안 고친다)")
    ap.add_argument("--stop-at-review", action="store_true",
                    help="학습목표를 보여준 뒤 멈춘다. 사람이 훑고 다시 돌린다")
    ap.add_argument("--note", help="이 강의에만 거는 지시. ①②·수선 프롬프트 끝에 붙는다")
    ap.add_argument("--annotation-evidence", action="store_true",
                    help="자동 판정과 무관하게 올해 필기를 근거로 인정한다")
    ap.add_argument("--no-annotation-evidence", action="store_true",
                    help="교수가 바뀌었어도 필기를 근거로 인정하지 않는다")
    ap.add_argument("--check-dir", default="out/_image_check",
                    help="이미지 카드 접촉 시트를 모아 둘 폴더")
    ap.add_argument("--no-image-check", action="store_true",
                    help="접촉 시트를 모으지 않는다 (눈검사가 더 필요 없어지면)")
    ap.add_argument("--force", action="store_true", help="이미 있는 산출물도 다시 만든다")
    args = ap.parse_args(argv)

    # ── 이어 돌리기: 폴더가 기억한 이름을 되찾는다 ──
    saved, given = {}, args.pdf          # 명령줄에서 준 PDF 가 기억보다 우선한다
    if args.resume:
        cfg = Path(args.resume) / CONFIG
        if cfg.exists():
            saved = json.loads(cfg.read_text(encoding="utf-8"))
        args.pdf = args.pdf or saved.get("pdf") or None

    if not args.resume and not args.pdf:
        print("필기 PDF 경로가 필요하다 (또는 --resume <폴더>).", flush=True)
        return 1

    pdf = Path(args.pdf) if args.pdf else None
    if pdf and not pdf.exists():
        print(f"PDF 를 찾지 못했다: {pdf}", flush=True)
        return 1

    args.pdf_name = ((pdf.name if given and pdf else None)
                     or saved.get("pdf_name") or (pdf.name if pdf else "lecture.pdf"))
    args.lecture = args.lecture or saved.get("lecture") or lecture_of(Path(args.pdf_name))
    args.deck = args.deck or saved.get("deck") or deck_of(args.lecture, args.subject)
    args.id = args.id or saved.get("id") or lecture_id_of(Path(args.pdf_name))

    out = Path(args.resume or args.out or f"out/{args.id}")
    out.mkdir(parents=True, exist_ok=True)

    print(f"덱   : {args.deck}")
    print(f"ID   : {args.id}")
    print(f"폴더 : {out.as_posix()}")

    kin = deck_siblings(out, args.deck, args.id)
    if kin:
        print()
        print("⚠ 이 덱 노드를 다른 강의가 이미 쓰고 있다 - 임포트하면 한 덱으로 합쳐진다.")
        for k in kin:
            print(f"   {k}")
        print("   한 강의가 두 교시에 걸친 것이면 맞다. 아니면 --deck 으로 갈라라.")

    r = Runner(out, args)
    try:
        r.all()
    except (Failed, SessionError) as e:
        print(f"\n멈췄다 — {e}", flush=True)
        print(f"   고친 뒤 이 한 줄이면 이어서 간다: "
              f"python -m pdf2anki.run --resume {out.as_posix()}", flush=True)
        r.report(None)
        return 1

    chk = r.collect_check()
    print(f"\n끝났다.  덱: {out.as_posix()}/{args.apkg_name or args.id}.apkg", flush=True)
    if chk:
        print(f"\n⚠ 눈으로 볼 것 — 이미지 카드 접촉 시트", flush=True)
        print(f"   {chk}", flush=True)
        print("   앞면 크롭 안에 정답(진단명·캡션)이 인쇄돼 있는지만 본다.", flush=True)
    elif not args.no_image_check:
        print("\n이미지 카드가 없어 접촉 시트는 만들지 않았다.", flush=True)
    r.report(chk)
    return 0


if __name__ == "__main__":
    sys.exit(main())

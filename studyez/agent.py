"""서버에 적힌 일감을 집어 와 한 편씩 만들고 올린다. **야간 스케줄러를 대신한다.**

    python -m studyez agent              계속 돈다 (Ctrl+C로 멈춘다)
    python -m studyez agent --once       한 바퀴만 — 붙는지 볼 때
    python -m studyez agent 병리학        쓸기를 이 과목으로 좁힌다

## 왜 크론을 걷어냈나

`04:00 예습 빌드` + `06:00 쓸기`로 돌던 것을 여기로 옮겼다. 크론이 못 한 것은
빌드가 아니라 **실패를 알리는 일**이었다.

    2026-08-18 09:15  쓸기 — 강의 0편 · 올릴 것이 없다   종료 코드 0
    2026-08-19 06:48  같음                              종료 코드 0
    2026-08-22 07:15  같음                              종료 코드 0
    2026-08-23 06:56  같음                              종료 코드 0

닷새 동안 아무것도 안 올렸는데 스케줄러에는 성공으로 적혔다. 같은 날 예습 빌드는
`0xC000013A`(강제 종료)로 죽었고, 로그에는 머리글만 남았다 — 그 스크립트가 자식이
끝난 뒤에야 로그를 쓰기 때문이다.

**사람이 누른 일감은 다르다.** `/admin`에 줄이 남아 있고, 끝나지 않으면 끝나지 않은
채로 보인다. 그래서 여기서 하는 일의 절반은 만드는 것이고 나머지 절반은 **어디까지
왔는지 서버에 적는 것**이다.

## 도는 모양

    일꾼 w1 ─┐
    일꾼 w2 ─┤ POST …/prequiz-jobs/claim?worker=<이름>   일감 하나 (없으면 null)
             │   → 예습: studyez prequeue <과목> --run-id <올해> --build --max 1
             │     복습: studyez watch    <과목> --run-id <올해> --build
             │   → studyez publish  <과목> --run-id <올해>
             │   → PUT …/prequiz-jobs/<id>   queued → running → done|failed
    쓸기 ────┘ 10분마다 studyez publish — **빌드와 겹쳐 돈다**

## 왜 실을 나눴나 (2026-09-01)

그 전에는 한 실이 `claim` → `handle` → 쓸기를 차례로 했다. 그래서 **한 편이 막히면
전부 막혔다.** 2026-08-31에 기생충학/260831_01이 「필기 중심으로 만들까요?」에서
45분을 잠들어 있었는데, 그동안 큐에 선 편도 올릴 것도 아무것도 안 움직였다.

지금은 일꾼이 둘이고(`WORKERS`), 쓸기가 따로 돈다. 겹쳐 도는 것을 서버도 같은
값으로 막는다(`routes/prequiz_jobs.MAX_RUNNING`).

**같은 편을 둘이 만들지 않는다**는 것을 세 겹으로 지킨다.

    서버   `running`인 편은 그 일꾼에게만 돌려준다
    러너   `Agent.building`에 든 run_id는 두 번째 일꾼이 안 잡는다
    파일   `runs/<run_id>/BUILDING` — 쓸기(하위 프로세스)가 이것을 보고 비껴간다

**겹치던 자리 하나를 같이 옮겼다**(2026-09-01). 예습 둘이 같이 돌면 두 `prequeue`
프로세스가 `runs/prequeue.json`을 각자 통째로 다시 쓴다(`prequeue.save`). 산출물은
편마다 자리가 달라 안 상하지만, 그 파일을 읽던 `already_made`가 판정을 못 찾아
**덱은 멀쩡한데 「덱을 못 만들었다」를 적을 수 있었다.** 판정을 편마다 자기 자리에도
적게 했고(`prequeue.save_state`), 큐 파일은 사람이 읽는 자리로 남겼다.

**갈래는 일감에 실려 온다**(`kind`). 재료가 다르므로 명령이 다르다 — 예습은 관리자가
만든 예습 대화와 작년 필기로, 복습은 올해 필기로 만든다. 그 뒤(올리기·보고)는 같다.

**「다시 만들기」는 일감에 실려 온다**(`force`). 그러면 `prequeue`에 `--force`가
붙는다. 이 값이 서버에서 오는 이유는 노트북이 판정할 수 없기 때문이다 — 여기에
산출물이 남아 있는 것과 사람이 다시 만들라고 한 것은 다른 사실이다.

일감이 없으면 `SWEEP_SECONDS`마다 `publish`를 한 번 돌린다. 06:00 쓸기가 받던 것들이
그대로 여기로 온다 — 강의록, 복습 덱, 끊긴 업로드, `release`로 풀린 편.

**한 번에 한 편이다.** 한 편이 이미 빈 세션 넷을 띄운다(`studyez.watch.build`와
같은 이유). 서버도 `running`이 있으면 새 일감을 안 준다.

## 한도는 실패가 아니다 (2026-09-02)

모델 한도(`session limit`)로 멈춘 편은 **실패로 적지 않고 줄 앞으로 되돌린다.**
이 편의 잘못이 아니고 시각이 되면 풀리기 때문이다. 실패로 적으면 사람이 다시
눌러야 하는데, 걸리는 시각이 대개 사람이 자는 때다 — 그날 01:32과 10:17 두 번이
그랬고 둘 다 아침까지 아무것도 안 만들어졌다.

    state=queued · resumeAt=<풀리는 시각> · stage=「세션 한도 — 13:40에 다시 시작」

**기다림은 큐가 든다**(`prequiz_job.resume_at`). 러너 메모리에 두면 재시작에
날아가고, 그러면 풀리지도 않은 한도에 다시 부딪힌다. 서버가 그 시각 전에는 그
줄을 아무에게도 안 준다.

만들어 둔 단계는 그대로 남으므로, 다시 집으면 **거기서 이어 간다**.

## 박동은 두 자리에서 찍는다

`claim`만으로는 모자란다. **한 편을 잡으면 15분 동안 `claim`을 안 부른다** —
`tick`이 `handle` 안에 머물기 때문이다. 그동안 박동이 멎으면 화면은 2분 뒤부터
멀쩡히 만드는 중인 러너를 「안 붙어 있습니다」라고 말한다.

그래서 도는 동안에는 진행을 적는 `PUT`이 박동을 겸한다(`_run`). 단계가 바뀌면
그 단계를, 안 바뀌면 빈 몸으로 두드린다 — 서버는 빈 몸을 받으면 아무것도 안
바꾸고 살아 있다는 것만 적는다.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from datetime import date as Date
from datetime import datetime, timedelta
from pathlib import Path

from . import ahead, deck, eta, gate, prequeue, publish, watch

POLL_SECONDS = 15         # 일감을 물어보는 간격
STAGE_SECONDS = 20        # 하위 로그를 훑어 단계를 올리는 간격
SWEEP_SECONDS = 600       # 남은 것을 쓸어 올리는 간격
BUILD_TIMEOUT = 3 * 3600  # 이 시간을 넘기면 그 편을 버린다

# 한 번에 몇 편을 겹쳐 만드나(관리자 지시, 2026-09-01). 서버도 같은 값을 든다
# (`routes/prequiz_jobs.MAX_RUNNING`) — 둘 중 작은 쪽이 실제 상한이 된다.
#
# **편당 비용은 안 변한다.** 한 편이 쓰는 세션 수도 시간도 그대로이고, 벽시계만
# 줄어든다. 대신 최대 여덟 개 세션이 겹친다(한 편이 재현 검사에서 넷을 띄운다).
WORKERS = 2

CLAIM = "/api/admin/prequiz-jobs/claim"

# 러너가 둘 돌지 않게 잡는 표시. 도는 동안 계속 만져서 살아 있다고 알린다.
LOCK_NAME = "agent.lock"
LOCK_STALE = 90          # 이 시간 넘게 안 만져진 표시는 죽은 것이다

# 하위 프로세스가 단계를 알리는 모양. pdf2anki가 `── ① 반드시 알아야 할 것`처럼
# 찍는다. 사람이 그대로 읽을 수 있어서 다시 쓰지 않고 옮기기만 한다.
RE_STAGE = re.compile(r"^── (.+)$")
# 건너뛴 단계는 `[건너뜀] 프롬프트 조립  (prompt.cards*.md 이미 있음)` 꼴이다.
# 괄호 앞까지가 단계 이름 — 첫 공백에서 자르면 「프롬프트」만 남는다.
RE_SKIP = re.compile(r"^\[건너뜀\] (.+?)(?:\s{2,}\(.*\))?$")
RE_PREV = re.compile(r"작년 (\d{6}_\d{2})")
# 「만들 것이 하나도 없다」는 줄. 줄 머리에서 재지 않으면 옆의 `다시 만들 것 0편`에
# 걸린다(2026-09-02).
RE_NOTHING = re.compile(r"^\s*만들 것 0편")
# 모델 쪽 한도에 걸린 자리. `claude -p`가 이 말을 그대로 싣고 429로 끝난다.
RE_LIMIT = re.compile(r"(?:session|usage) limit\s*(?:·\s*)?([^\"\\]*)", re.IGNORECASE)
# 하위 로그가 어디 있는지. 실패 줄이 경로를 달고 온다.
RE_CHILD_LOG = re.compile(r"\(로그: (.+?\.log)\)")
# `pdf2anki`가 멈출 때 찍는 말. 로그가 덧붙여 쓰이므로 **마지막 것이 이번 것**이다.
STOPPED = "멈췄다 — "
# 한도가 언제 풀리는지. `resets 1:40pm (Asia/Seoul)` 꼴로 온다.
RE_RESET_AT = re.compile(r"resets\s+(\d{1,2}):(\d{2})\s*(am|pm)?", re.IGNORECASE)
# 풀리는 시각을 못 읽었을 때 기다릴 시간. 한도 창이 5시간이라 그보다 짧게 잡는다 —
# 너무 길게 자면 이미 풀린 뒤에도 큐가 서 있고, 짧으면 한 번 더 부딪힐 뿐이다.
BLIND_WAIT = 30 * 60


@dataclass
class Job:
    id: int
    subject: str
    run_id: str
    # `pre` | `main`. 무엇을 만드는 일감인가 — 재료도 명령도 갈린다(`make_argv`).
    kind: str = deck.PRE
    # 사람이 「다시 만들기」를 눌렀는가. **서버만 아는 값이다** — 노트북에 산출물이
    # 남아 있으면 `prequeue`는 그 편을 이미 만든 것으로 보고 건너뛴다.
    force: bool = False

    @property
    def label(self) -> str:
        return f"{self.subject}/{self.run_id}"

    @property
    def what(self) -> str:
        """사람이 읽는 갈래 이름. 화면에도 로그에도 같은 말이 서야 한다."""
        return "Main-Quiz" if self.kind == deck.MAIN else "Pre-Quiz"


class Agent:
    def __init__(self, client: publish.Client, runs_dir: Path, repo_root: Path, *,
                 subject: str = "", sweep_seconds: int = SWEEP_SECONDS,
                 timeout: int = BUILD_TIMEOUT, workers: int = WORKERS, announce=print):
        self.client = client
        self.runs_dir = runs_dir
        self.repo_root = repo_root
        self.subject = subject
        self.sweep_seconds = sweep_seconds
        self.timeout = timeout
        self.workers = max(1, workers)
        self._say = announce
        self.last_sweep = 0.0
        # 지금 이 러너가 만들고 있는 편. **서버가 이미 막지만 여기서도 막는다** —
        # 서버가 잠깐 안 뜨거나 옛 러너가 같이 떠 있으면 그쪽이 뚫린다.
        self.building: dict[str, str] = {}
        self._guard = threading.Lock()
        self._stop = threading.Event()
        # **올리는 것은 한 번에 하나다.** 무엇을 올렸는지 적는 표가 파일 하나이고
        # (`publish.LEDGER_NAME`) 통째로 읽어 통째로 다시 쓴다. 두 `publish`가
        # 겹치면 나중에 끝난 쪽이 앞의 기록을 지우고, 다음 회차가 수백 MB를 다시
        # 민다. 올리기는 편당 1분 안쪽이라 여기서 줄을 세워도 잃는 것이 없다.
        self._uploading = threading.Lock()

    def say(self, line: str) -> None:
        """로그 한 줄. **일꾼이 여럿이라 줄이 섞인다** — 한 번에 하나씩 쓴다."""
        with self._guard:
            self._say(line)

    def take(self, job: Job, slot: str) -> bool:
        """이 편을 이 일꾼이 맡는다고 적는다. 이미 누가 맡고 있으면 False."""
        with self._guard:
            if job.run_id in self.building:
                return False
            self.building[job.run_id] = slot
            return True

    def release(self, job: Job) -> None:
        with self._guard:
            self.building.pop(job.run_id, None)

    # ── 서버와 주고받기 ───────────────────────────────────────────────
    def claim(self, slot: str = "w1") -> Job | None:
        """일감 하나를 집어 온다. **박동도 이 호출이 찍는다** — 없어도 불러야 한다.

        `slot`은 이 일꾼의 이름이다. 서버가 그 이름으로 「누가 무엇을 잡고 있나」를
        들고 있어서, 끊겼다 붙어도 **자기 편**을 다시 받는다.
        """
        answer = self.client.call("POST", f"{CLAIM}?worker={slot}", {}) or {}
        row = answer.get("job")
        if not row:
            return None
        return Job(id=int(row["id"]), subject=str(row["subject"]), run_id=str(row["runId"]),
                   kind=str(row.get("kind") or deck.PRE), force=bool(row.get("force")))

    def report(self, job: Job, **fields) -> None:
        """진행을 적는다. **실패해도 하던 일은 계속한다.**

        서버가 잠깐 안 뜬 것 때문에 다 만든 덱을 버릴 이유가 없다. 못 적은 것은
        화면에서 「멈춘 것처럼」 보이지만, 끝나면 마지막 갱신이 따라잡는다.
        """
        try:
            self.client.call("PUT", f"/api/admin/prequiz-jobs/{job.id}", fields)
        except publish.PublishError as cause:
            self.say(f"    (진행을 못 적었다 — {cause})")

    # ── 하위 프로세스 ────────────────────────────────────────────────
    def _run(self, argv: list[str], log: Path, job: Job | None = None,
             stage_prefix: str = "") -> tuple[int, list[str]]:
        """하위 프로세스를 띄우고, 도는 동안 단계를 서버로 올린다.

        출력을 파이프가 아니라 파일로 받는다. 파이프를 읽으려면 스레드가 필요한데,
        **덱 빌드는 15분 동안 한 줄도 안 흘린다** — 읽을 것이 없는 파이프를 지키느니
        주기적으로 로그를 훑는 편이 단순하다.
        """
        log.parent.mkdir(parents=True, exist_ok=True)
        # **하위 명령도 같은 서버를 봐야 한다.** 안 넘기면 `prequeue`·`publish`가
        # 기본 주소(운영)로 가는데, 러너를 다른 주소로 띄웠다면 일감은 이쪽에서
        # 받고 산출물은 저쪽으로 미는 꼴이 된다. 토큰은 인자가 아니라 환경으로
        # 준다 — 명령줄은 같은 기계의 다른 프로세스에서도 보인다.
        env = dict(os.environ, PYTHONIOENCODING="utf-8",
                   STUDYEZ_API_BASE_URL=self.client.base,
                   STUDYEZ_RUNNER_TOKEN=self.client.token)
        posted = ""
        started = time.time()
        stage_at = started
        deadline = started + self.timeout

        with log.open("w", encoding="utf-8") as sink:
            # **자식은 물을 자리가 없다**(`stdin`). 안 막으면 러너의 stdin을 그대로
            # 물려받는데, 예약 작업으로 뜬 러너의 그것이 `isatty()`에 참으로 나온다.
            # 그러면 `pdf2anki`가 「필기 중심으로 만들까요? [Y/n]」에서 `input()`으로
            # 잠들고, 답할 사람이 없으니 `BUILD_TIMEOUT`(180분)까지 아무 일도 안 한다.
            # 2026-08-25 병리학/260825_03이 그렇게 죽었고 2026-08-31 기생충학/260831_01이
            # 45분을 그러고 있었다 — CPU 0.2초, 그동안 만들어진 파일 0개.
            #
            # 막아 두면 `sys.stdin.isatty()`가 거짓이라 자식이 스스로 갈래를 정한다.
            proc = subprocess.Popen(argv, stdout=sink, stderr=subprocess.STDOUT,
                                    stdin=subprocess.DEVNULL,
                                    cwd=str(self.repo_root), env=env)
            while proc.poll() is None:
                time.sleep(STAGE_SECONDS)
                now = time.time()
                if now > deadline:
                    proc.kill()
                    proc.wait()
                    return 124, [f"{self.timeout // 60}분 안에 끝나지 않아 끊었다"]
                if job is None:
                    continue
                # 그 편을 만드는 동안 계속 만진다. 쓸기가 이 표시를 보고 이번
                # 회차에서 그 자리를 뺀다(`gate.building_reason`).
                self.mark_building(job)
                stage = self.stage_of(log, job)
                if stage and stage != posted:
                    if posted:
                        # **지난 단계가 얼마나 걸렸는지 여기서만 알 수 있다.**
                        # 다음 편의 「남은 시간」이 이 값에서 나온다.
                        eta.observe(self.runs_dir, job.kind, posted, now - stage_at)
                    posted, stage_at = stage, now
                    guess = eta.estimate(self.runs_dir, job.kind, stage,
                                         elapsed=now - started, stage_elapsed=0)
                    self.report(job, stage=stage_prefix + stage,
                                stageIndex=guess.index, stageTotal=guess.total,
                                etaSeconds=guess.eta_seconds)
                elif posted:
                    # 단계가 그대로여도 한 번은 말을 건다. **이것이 박동이다** —
                    # 한 편을 잡으면 15분 동안 `claim`을 안 부르므로, 여기서 안
                    # 두드리면 화면이 도는 중인 러너를 죽었다고 말한다.
                    #
                    # 남은 시간만 다시 셈해 얹는다. 단계 글이 그대로라 서버는 단계
                    # 시계를 안 건드리고(`update_prequiz_job`), 화면의 「남은 약
                    # N분」이 20초마다 줄어든다.
                    live = eta.estimate(self.runs_dir, job.kind, posted,
                                        elapsed=now - started, stage_elapsed=now - stage_at)
                    self.report(job, etaSeconds=live.eta_seconds)
                else:
                    # 아직 첫 단계도 안 찍혔다. 살아 있다는 것만 알린다.
                    self.report(job)

        return proc.returncode, tail(log)

    def stage_of(self, wrapper_log: Path, job: Job) -> str:
        """지금 어느 단계인가. 두 곳을 본다 — 감싼 명령의 로그와 빌드의 로그.

        빌드는 자기 출력을 로그 파일로만 흘리므로(`studyez.deck._spawn`), 감싼
        쪽만 보면 15분 동안 빈손이다. **어느 파일인지가 갈래마다 다르다** — 복습은
        올해 자리의 `pipeline.log`, 예습은 작년 자리의 `prequiz.log`다. 작년 짝은
        `prepare`가 적어 둔 `pre_target.json`에서 찾는다.

        **갈래를 안 가르면 복습을 만드는 중에 예습 로그를 읽는다.** 예습을 이미
        만들어 둔 편이 그렇다 — `pre_target.json`이 그대로 남아 있어서, 지난번
        예습의 마지막 단계가 지금 하는 일인 것처럼 화면에 뜬다.
        """
        if job.kind == deck.MAIN:
            return last_stage(self.runs_dir / job.run_id / "pipeline.log") or last_stage(wrapper_log)

        prev = self.prev_run_of(job) or prev_from(wrapper_log)
        if prev:
            stage = last_stage(self.runs_dir / prev / "prequiz.log")
            if stage:
                return stage
        return last_stage(wrapper_log) or ""

    def prev_run_of(self, job: Job) -> str:
        """올해 강의 → 작년 run. `prequeue.prepare`가 적어 둔 자리를 되읽는다."""
        for target in self.runs_dir.glob("*/pre_target.json"):
            try:
                row = json.loads(target.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if row.get("run_id") == job.run_id and row.get("subject") == job.subject:
                return target.parent.name
        return ""

    # ── 한 편 ────────────────────────────────────────────────────────
    def make_argv(self, job: Job) -> list[str]:
        """이 일감을 만드는 명령. **갈래가 여기서 갈린다.**

        재료가 다르므로 명령이 다르다 — 예습은 관리자가 만든 예습 대화와 작년
        필기로(`prequeue`), 복습은 올해 필기로(`watch`) 만든다.

        **`--force`가 붙는 자리도 여기다.** 안 붙이면 다시 만들라고 누른 편이
        「이미 있는 것」으로 세어지고, 아무것도 안 만든 채 돌아온다. 그러면 화면에는
        「덱을 못 만들었다」가 적힌다 — 사람은 다시 만들라고 눌렀을 뿐인데 실패로 보인다.
        """
        if job.kind == deck.MAIN:
            argv = [sys.executable, "-m", "studyez", "watch", job.subject,
                    "--run-id", job.run_id, "--build"]
        else:
            argv = [sys.executable, "-m", "studyez", "prequeue", job.subject,
                    "--run-id", job.run_id, "--build", "--max", "1"]
        if job.force:
            argv.append("--force")
        return argv

    def building_seats(self, job: Job) -> set[Path]:
        """이 일감이 쓰는 자리. 표시를 놓고 지우는 곳이 여기다.

        **갈래마다 다르다.** 복습은 올해 자리에만 쓴다. 예습은 산출물이 작년 run에
        쌓이므로 거기도 막아야 한다 — 안 막으면 쓸기가 만드는 중인 예습 덱을 올린다.

        복습이 작년 자리까지 찍고 있었다(2026-09-02에 좁혔다). 손해는 없었지만
        지울 때가 위험하다 — **같은 교시에 다른 과목이 돌면 한 작년 자리를 두 강의가
        나눠 쓴다.** 그 자리에서 예습이 도는 중에 복습이 끝나면서 남의 표시를 지우면,
        쓸기가 반쯤 쓰인 예습 덱을 올린다.
        """
        seats = {self.runs_dir / job.run_id}
        if job.kind != deck.MAIN:
            prev = self.prev_run_of(job)
            if prev:
                seats.add(self.runs_dir / prev)
        return seats

    def mark_building(self, job: Job) -> None:
        """「이 자리는 지금 만드는 중」 표시를 만진다. 쓸기가 이것을 본다.

        **프로세스 밖으로 나가는 표시라 파일이다.** 쓸기는 하위 프로세스
        (`studyez publish`)라 러너의 메모리를 볼 수 없다.
        """
        for target in self.building_seats(job):
            try:
                target.mkdir(parents=True, exist_ok=True)
                (target / gate.BUILDING_FILE).write_text(
                    f"{job.what} {job.label}", encoding="utf-8")
            except OSError:
                pass

    def clear_building(self, job: Job) -> None:
        for target in self.building_seats(job):
            (target / gate.BUILDING_FILE).unlink(missing_ok=True)

    def handle(self, job: Job) -> None:
        """일감 하나를 끝까지. 만들고, 올리고, 무엇이 됐는지 적는다."""
        again = "다시 " if job.force else ""
        self.say(f"[{stamp()}] {job.label} {job.what} — {again}만드는 중")
        self.report(job, state="running", stage=f"{again}만들 자리 세우는 중")

        started = time.time()
        self.mark_building(job)
        log = self.runs_dir / f"agent.{job.run_id}.log"
        try:
            code, lines = self._run(self.make_argv(job), log, job)
        finally:
            # **올리기 전에 푼다.** 이 편의 `publish`는 바로 아래에서 도는데, 표시가
            # 남아 있으면 자기 자신이 만든 것을 「만드는 중」이라고 건너뛴다.
            self.clear_building(job)

        made = self.outcome(job, lines, code, started)
        if not made:
            # 한도가 먼저다. 기다리면 풀리는 일을 다른 말로 적으면 사람이
            # 고칠 것이 없는 곳을 고치러 간다.
            hit_limit = limit_reason(lines)
            why = (hit_limit or child_stop_reason(lines)
                   or blocked_reason(lines, job.run_id)
                   or summary(lines) or f"종료 코드 {code}")
            if hit_limit:
                # **실패가 아니라 기다림이다.** 이 편의 잘못이 아니고 시각이 되면
                # 풀린다. 실패로 적으면 사람이 다시 눌러야 하는데, 걸리는 시각이
                # 대개 사람이 자는 때다(2026-09-02에 01:32·10:17 두 번).
                #
                # 여기까지 온 것은 그대로 남는다 — 다시 집으면 만들어 둔 단계를
                # 건너뛰고 이어 간다.
                when = resume_at(hit_limit)
                self.say(f"    한도 — {when:%H:%M}에 저절로 이어 간다")
                self.report(job, state="queued", resumeAt=when.isoformat(),
                            stage=f"세션 한도 — {when:%H:%M}에 다시 시작",
                            message=f"{hit_limit} · 그때까지 줄에서 기다린다 (로그: {log})")
                return
            self.say(f"    실패 — {why}")
            self.report(job, state="failed", stage="", message=f"덱을 못 만들었다: {why} (로그: {log})")
            return
        self.say(f"    {made} — 올리는 중")
        self.report(job, stage=f"{made} · 올리는 중")

        up_log = self.runs_dir / f"agent.{job.run_id}.publish.log"
        with self._uploading:
            code, lines = self._run(
                [sys.executable, "-m", "studyez", "publish", job.subject, "--run-id", job.run_id],
                up_log)
        if code != 0:
            why = summary(lines) or f"종료 코드 {code}"
            self.say(f"    올리다 실패 — {why}")
            self.report(job, state="failed", stage="",
                        message=f"덱은 만들었다({made}). 올리지 못했다: {why} (로그: {up_log})")
            return

        # 검문에 걸리면 강의록만 나간다. 성공으로 적되 **왜 덱이 안 갔는지 남긴다** —
        # 조용히 넘기면 화면이 "올라갔다"고 말하는데 학생에게는 아무것도 안 간다.
        held = [line.strip() for line in lines if "✋" in line]
        # 예습은 문항 수가 그 편의 값이고, 복습은 올린 파일이 그렇다. 갈래에 없는
        # 줄을 찾으면 둘 다 "올렸다"로 뭉개진다.
        note = (first_match(lines, r"(pre-items \d+문항.*)$") if job.kind != deck.MAIN else "")             or first_match(lines, r"(올린 파일 .+)$") or "올렸다"
        message = f"{made} · {note}"
        if held:
            message += " · 검문에 걸려 덱은 미뤘다 — " + held[0].lstrip("✋ ")
        self.say(f"    끝났다 — {message}")
        # **끝난 줄은 끝까지 간 것으로 닫는다.** 안 닫으면 마지막으로 본 단계에
        # 멈춰 있어서, 다 끝난 편이 화면에 「7/18단계」로 남는다(2026-09-02).
        # 분모를 모르면 아무 값도 안 보낸다 — 서버가 옛 값을 그대로 둔다.
        total = len(eta.samples(self.runs_dir, job.kind).order)
        closed = {"stageIndex": total, "stageTotal": total} if total else {}
        self.report(job, state="done", stage="", message=message, **closed)

    def outcome(self, job: Job, lines: list[str], code: int, since: float) -> str:
        """이번 실행에서 무엇이 나왔나. 빈 문자열이면 못 만든 것이다.

        **성공을 종료 코드로만 보지 않는다.** `prequeue`는 만들 자리가 없어도 0으로
        끝난다 — 배선 시험에서 아무것도 안 만들고 "덱을 만들었다"가 찍혔다.

        갈래마다 무엇을 보는지가 다르다.

        예습은 **산출물의 시각**을 본다. 다시 만들기를 눌렀는데 빌드가 조용히
        건너뛰면 지난번 `pre_items.final.json`이 그대로 있어서 「됐다」로 읽힌다.

        복습은 **덱 파일이 있는지**만 본다. 시각을 안 보는 까닭은 이미 만들어 둔
        덱을 그대로 올리는 길이 정상이기 때문이다 — 만들다 만 것이 아니라 올리다
        만 편이 있고(검문에 걸렸거나 업로드가 끊겼거나), 그 편에서 사람이 누르는
        것도 이 버튼이다. `watch --run-id`가 그때 안 만들고 넘긴다. 대신 그쪽은
        **실패를 종료 코드로 말한다** — 여기서 0이 아니면 만들다 죽은 것이다.

        **예습에도 올리다 만 편이 있다.** 2026-08-31 에 `260831_01`을 눌렀더니
        `prequeue`가 「이미 있는 것 1편」으로 끝냈고(같은 대화로 만든 문항이 이미
        노트북에 있었다), 여기서 그것을 실패로 적었다. 화면에는 「덱을 못 만들었다」가
        남고 덱은 그날 밤 쓸기가 올려 주었다 — 누른 사람은 실패를 보고 덱을 받았다.
        복습과 같은 자리이므로 같이 판정한다: 새로 만든 것이 없어도 **이 대화로
        만든 문항이 이미 있으면 올릴 것이 있는 것**이라 성공이다.
        """
        made = first_match(lines, r"끝났다 — (.+)$")
        if code != 0:
            return ""
        if job.kind == deck.MAIN:
            if made:
                return made
            return "이미 있던 덱" if deck.apkg_of(self.runs_dir / job.run_id, deck.MAIN) else ""
        if made and self.made_deck(job, since):
            return made
        return "이미 있던 문항" if self.already_made(job) else ""

    def already_made(self, job: Job) -> bool:
        """이 대화로 만든 예습 문항이 이미 노트북에 있는가. `outcome`이 부른다.

        로그를 긁지 않고 **`prequeue`가 적어 둔 판정**을 읽는다(`prequeue.DONE`) —
        같은 실행이 남긴 구조화된 값이라 줄 모양이 바뀌어도 안 흔들린다.

        **그 편의 자리에 적힌 것을 먼저 본다**(`prequeue.state_of`). 큐 파일은 한
        파일이라 다음 실행이 통째로 덮어쓴다 — 일꾼이 둘이면 두 편이 같은 초에
        지우고, 하나였을 때도 늘 마지막 한 편만 남아 있었다. 그러면 여기서 판정을
        못 찾고, **덱은 멀쩡한데 화면에 「덱을 못 만들었다」가 뜬다.**

        큐 파일은 물러설 자리로 남긴다. 2026-09-01 이전에 만든 편에는 편별 판정이
        없어서, 그 편들에는 이것이 유일한 답이다.

        **「다시 만들기」에는 안 쓴다.** 그때 아무것도 안 나왔다는 것은 `--force`가
        안 먹었다는 뜻이고, 그것을 성공으로 적으면 옛 덱을 새것으로 올린다.
        """
        if job.force:
            return False
        prev = self.prev_run_of(job)
        if prev:
            state = prequeue.state_of(self.runs_dir, prev, job.subject, job.run_id)
            if state:
                return state == prequeue.DONE
        try:
            queue = json.loads((self.runs_dir / prequeue.QUEUE_NAME).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return False
        for row in queue.get("items", []) if isinstance(queue, dict) else []:
            link = row.get("link") or {}
            if link.get("run_id") == job.run_id and link.get("subject") == job.subject:
                return row.get("state") == prequeue.DONE
        return False

    def made_deck(self, job: Job, since: float) -> bool:
        """이번 실행에서 예습 문항이 실제로 나왔는가. `outcome`이 부른다."""
        prev = self.prev_run_of(job)
        if not prev:
            return False
        items = self.runs_dir / prev / "pre_items.final.json"
        try:
            return items.stat().st_mtime >= since - 5
        except OSError:
            return False

    def sweep_subjects(self) -> tuple[list[str], str]:
        """이번 쓸기가 볼 과목. **매 회차 시간표에 다시 물어본다.**

        `--subject`를 손으로 줬으면 그것이 이긴다. 안 줬으면 오늘의 블럭에 걸린
        과목을 푼다 — 그래서 시험이 끝나고 다음 블럭이 서면 **아무도 안 건드려도
        바뀐다.** 예약 작업에 `-Subject 병리학` 이 박힌 채 남아 2026-08-30 에
        기생충학이 쓸기 밖에 있었던 것이 이 자리를 만든 이유다.

        못 풀면 `--all`로 물러난다. 쓸기는 만드는 일이 아니라 올리는 일이라,
        넓게 여는 값이 놓치는 값보다 싸다.
        """
        if self.subject:
            return [self.subject], ""
        today = Date.today()
        try:
            picked, note = ahead.subjects_in_block(
                watch.DEFAULT_ROOT, str(today.year), self.runs_dir, today)
        except (OSError, ValueError, sqlite3.Error) as cause:
            return [], f"시간표를 못 읽었다 ({cause}) — 과목 전부를 쓴다"
        return picked, note

    def sweep(self) -> None:
        """남은 것을 쓸어 올린다. 06:00 크론이 받던 자리다."""
        self.last_sweep = time.monotonic()
        subjects, note = self.sweep_subjects()
        if note:
            self.say(f"[{stamp()}] 쓸기 — {note}")
        for subject in subjects or [""]:
            argv = [sys.executable, "-m", "studyez", "publish"]
            argv += [subject] if subject else ["--all"]
            # **과목마다 로그를 따로 쓴다.** `_run`이 파일을 덮어쓰기로 열어서,
            # 한 파일에 몰면 마지막 과목 것만 남는다.
            log = self.runs_dir / f"agent.sweep.{subject or 'all'}.log"
            with self._uploading:
                code, lines = self._run(argv, log)
            line = first_match(lines, r"(올린 파일 .+)$") or f"종료 코드 {code}"
            self.say(f"[{stamp()}] 쓸기 {subject or '전부'} — {line}")

    # ── 루프 ─────────────────────────────────────────────────────────
    def tick(self, slot: str = "w1") -> bool:
        """한 바퀴. 일감을 하나 처리했으면 True.

        **쓸기는 여기 없다**(2026-09-01). 따로 도는 실이 맡는다(`sweep_loop`) —
        같이 두면 한 편을 만드는 45분 동안 아무것도 안 올라간다.
        """
        try:
            job = self.claim(slot)
        except publish.PublishError as cause:
            self.say(f"[{stamp()}] {slot} 서버에 못 물었다 — {cause}")
            return False
        if job is None:
            return False
        if not self.take(job, slot):
            # 서버가 같은 편을 둘에게 줬다는 뜻이다. 서버도 막지만, 옛 러너가
            # 같이 떠 있거나 표가 어긋나면 여기까지 온다. **만들지 않는다** —
            # 편당 빈 세션 넷이다.
            self.say(f"[{stamp()}] {slot} {job.label}은 이미 만드는 중이다 — 넘긴다")
            return False
        try:
            self.handle(job)
        finally:
            self.release(job)
        return True

    def work_loop(self, slot: str, poll: int) -> None:
        """일꾼 하나. 일감이 있으면 만들고, 없으면 쉰다."""
        while not self._stop.is_set():
            try:
                busy = self.tick(slot)
            except Exception as cause:                      # noqa: BLE001
                # **한 일꾼이 죽어도 나머지는 돈다.** 여기서 새는 예외 하나가
                # 러너를 통째로 세우면 고친 것이 도로 무너진다.
                self.say(f"[{stamp()}] {slot} 일꾼이 넘어졌다 — {type(cause).__name__}: {cause}")
                busy = False
            if not busy:
                self._stop.wait(poll)

    def sweep_loop(self) -> None:
        """쓸기. **빌드와 겹쳐 돈다** — 앞의 편이 막혀도 올릴 것은 올라간다."""
        while not self._stop.is_set():
            self._stop.wait(self.sweep_seconds)
            if self._stop.is_set():
                return
            try:
                self.sweep()
            except Exception as cause:                      # noqa: BLE001
                self.say(f"[{stamp()}] 쓸기가 넘어졌다 — {type(cause).__name__}: {cause}")

    # ── 하나만 돈다 ──────────────────────────────────────────────────
    def lock_path(self) -> Path:
        return self.runs_dir / LOCK_NAME

    def take_lock(self) -> bool:
        """이미 도는 러너가 있으면 False.

        **개수가 아니라 비용의 문제다.** 둘이 붙으면 서버가 같은 `running` 일감을
        둘 다에게 주고, 같은 편을 두 번 만든다. 편당 빈 세션 넷이다.

        pid 대신 **시각**을 본다. pid는 재사용되고, 그러면 죽은 러너 때문에 새
        러너가 영영 안 뜬다. 도는 동안 계속 만지므로 오래된 표시는 죽은 것이다.
        """
        path = self.lock_path()
        try:
            age = time.time() - path.stat().st_mtime
        except OSError:
            age = None
        if age is not None and age < LOCK_STALE:
            holder = path.read_text(encoding="utf-8", errors="replace").strip()
            self.say(f"러너가 이미 돌고 있다 ({holder}, {age:.0f}초 전). 둘이 붙으면 "
                     f"같은 편을 두 번 만든다 — 이 실행은 그만둔다")
            return False
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"pid {os.getpid()}", encoding="utf-8")
        return True

    def touch_lock(self) -> None:
        try:
            self.lock_path().write_text(f"pid {os.getpid()}", encoding="utf-8")
        except OSError:
            pass

    def loop(self, poll: int = POLL_SECONDS) -> int:
        """일꾼 여럿과 쓸기를 띄우고, 여기서는 표시만 만진다.

        **일꾼을 실로 나눈 이유가 이것 하나다** — 한 편이 막혀도 뒤의 편이 간다.
        2026-08-31에 한 편이 45분을 잠들어 있는 동안 큐도 쓸기도 통째로 섰다.

        실을 쓰지만 안에서 하는 일은 하위 프로세스를 기다리는 것뿐이라, GIL이
        무는 자리가 없다. 진짜 부담은 그 하위 프로세스들이 띄우는 빈 세션이다.
        """
        if not self.take_lock():
            return 3
        self.say(f"[{stamp()}] 러너가 붙었다 — {self.client.base}"
                 + f" · 일꾼 {self.workers}명"
                 + (f" · 쓸기 {self.subject}" if self.subject
                    else " · 쓸기는 매 회차 시간표에서 이번 블럭의 과목을 푼다")
                 + f" · {poll}초마다 물어본다")
        self.last_sweep = time.monotonic()
        crew = [threading.Thread(target=self.work_loop, args=(f"w{n + 1}", poll),
                                 name=f"studyez-w{n + 1}", daemon=True)
                for n in range(self.workers)]
        if self.sweep_seconds:
            crew.append(threading.Thread(target=self.sweep_loop,
                                         name="studyez-sweep", daemon=True))
        for thread in crew:
            thread.start()
        try:
            while any(thread.is_alive() for thread in crew):
                self.touch_lock()
                time.sleep(min(poll, LOCK_STALE // 3))
            self.say(f"[{stamp()}] 일꾼이 다 내려갔다 — 러너를 접는다")
            return 1
        except KeyboardInterrupt:
            self.say(f"\n[{stamp()}] 멈춘다. 도는 중이던 편은 서버에 running으로 남아 있다 — "
                     "다시 붙으면 그것부터 집는다")
            return 0
        finally:
            self._stop.set()
            self.lock_path().unlink(missing_ok=True)


# ── 로그에서 줍는 것들 ────────────────────────────────────────────────
def tail(path: Path, lines: int = 25) -> list[str]:
    try:
        return path.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:]
    except OSError:
        return []


def last_stage(path: Path) -> str:
    """로그에 마지막으로 찍힌 단계 이름. 없으면 빈 문자열."""
    for line in reversed(tail(path, 400)):
        found = RE_STAGE.match(line.strip()) or RE_SKIP.match(line.strip())
        if found:
            return found.group(1).strip()
    return ""


def prev_from(path: Path) -> str:
    for line in tail(path, 400):
        found = RE_PREV.search(line)
        if found:
            return found.group(1)
    return ""


def first_match(lines: list[str], pattern: str) -> str:
    for line in reversed(lines):
        found = re.search(pattern, line.strip())
        if found:
            return found.group(1).strip()
    return ""


def blocked_reason(lines: list[str], run_id: str = "") -> str:
    """`prequeue`가 막힌 이유. 표시 줄 다음에 사람이 읽을 말이 온다.

        2026-08-20 ✋ 260820_02    소아질환의 병태생리(2) …
            작년 짝이 없다 — 작년 강의록·예습 자리는 비워 둔다

    **다른 편의 줄을 이유로 삼지 않는다(`run_id`).** 한 과목의 로그에는 블럭
    전체의 경고가 같이 실린다 — `prequeue`는 편 하나만 만들어도 계획은 과목
    전부를 세우기 때문이다. 2026-08-31 에 `260831_01`을 누른 사람이 이런 말을
    받았다.

        덱을 못 만들었다: ⚠ 기생충학/260911_01 미생물학의 역사 — 작년 짝을 못 찾았다

    누른 적도 없는 강의고, 그 강의는 미생물학이라 기생충학에 작년 짝이 없는 것이
    당연하다. 편을 못 대면 **아무 줄이나 대느니 안 대는 편이 낫다** — 그 자리는
    `summary`가 받는다.
    """
    def mine(line: str) -> bool:
        return not run_id or run_id in line

    for index, line in enumerate(lines):
        if "✋" in line and mine(line):
            after = lines[index + 1].strip() if index + 1 < len(lines) else ""
            return (after or line.strip())[:300]
    # **줄 머리에서 잰다.** `"만들 것 0편" in line`으로 재던 자리다 — 그 글자가
    # 바로 옆의 `다시 만들 것 0편` 안에 그대로 들어 있어서, 만들 것이 있는 회차도
    # 참이 됐다. 2026-09-02에 예습 세 편이 세션 한도로 죽었는데 화면에는
    # 「만들 자리를 못 찾았다」가 떴다 — 사람이 짝을 고치러 갈 문구다.
    if any(RE_NOTHING.match(line) or "로컬에서 이 강의를 못 찾았다" in line for line in lines):
        return next((line.strip()[:300] for line in lines if "못 찾았다" in line and mine(line)),
                    "만들 자리를 못 찾았다")
    return ""


def limit_reason(lines: list[str]) -> str:
    """모델 한도에 걸렸나. 걸렸으면 사람이 읽을 한 줄, 아니면 빈 문자열.

    **이유가 하위 로그에만 있다.** 러너가 보는 것은 감싼 명령의 출력이라
    「pdf2anki가 1로 끝났다」까지만 온다. 그래서 그 줄이 달고 오는 경로를 따라가
    읽는다.

    2026-09-02 01:22에 복습 셋과 예습 셋이 이것으로 죽었는데, 화면에는 종료 코드와
    「만들 자리를 못 찾았다」만 남았다. **기다리면 풀리는 일과 사람이 고쳐야 하는
    일은 화면에서 갈려야 한다** — 앞의 것에 짝을 고치러 가면 고칠 것이 없다.
    """
    def said(text: str) -> str:
        """**이번에 멈춘 자리만 본다.** 하위 로그는 덧붙여 쓰인다(`deck._spawn`).

        그래서 한 파일에 어제 걸린 한도와 오늘 걸린 한도가 같이 있고, 아침에는
        첫 줄을 집어 이미 지난 시각을 적었다. 마지막 것을 집게 고쳤더니 이번에는
        **한도가 아닌 실패에 한도를 갖다 붙였다** — `260901_01`이 16:13에
        `pdf2anki.validate` 실패로 죽었는데 화면에는 「세션 한도 · resets 1:40pm」이
        떴다. 그 편의 로그에 아침의 한도 줄이 남아 있었기 때문이다.

        그래서 **마지막 `멈췄다 —` 뒤**만 본다. 그 줄이 이번 실행이 멈춘 자리이고,
        한도였다면 그 뒤에 API가 준 말이 그대로 붙어 있다.
        """
        cut = text.rfind(STOPPED)
        found = RE_LIMIT.findall(text[cut:] if cut >= 0 else text)
        if not found:
            return ""
        when = (found[-1] or "").strip(" ·\t")
        return f"세션 한도에 걸렸다 — {when}" if when else "세션 한도에 걸렸다"

    for line in lines:
        if found := said(line):
            return found
    for line in lines:
        child = RE_CHILD_LOG.search(line)
        if not child:
            continue
        try:
            text = Path(child.group(1)).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if found := said(text):
            return found
    return ""


def resume_at(reason: str, now: datetime | None = None) -> datetime:
    """한도가 풀리는 시각. 못 읽으면 `BLIND_WAIT` 뒤.

    「resets 1:40pm」은 **다음번 그 시각**이다. 지금이 그보다 뒤면 내일 것이다 —
    밤 10시에 「resets 5:40am」을 받으면 여섯 시간을 기다려야 한다.

    돌려주는 값에는 시간대가 붙어 있다(이 기계의 것). 서버가 UTC로 바꿔 든다.
    """
    now = now or datetime.now().astimezone()
    found = RE_RESET_AT.search(reason)
    if not found:
        return now + timedelta(seconds=BLIND_WAIT)
    hour, minute = int(found.group(1)), int(found.group(2))
    half = (found.group(3) or "").lower()
    if half == "pm" and hour != 12:
        hour += 12
    elif half == "am" and hour == 12:
        hour = 0
    if hour > 23:
        return now + timedelta(seconds=BLIND_WAIT)
    when = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    return when if when > now else when + timedelta(days=1)


def child_stop_reason(lines: list[str]) -> str:
    """하위 로그가 **이번에 멈춘 자리**. 한도가 아닐 때 그 자리를 대신 말한다.

    러너가 보는 줄은 「pdf2anki가 1로 끝났다」까지다. 그 말로는 사람이 로그를 열기
    전까지 아무것도 모른다 — 어느 단계였는지, 모델이 죽은 것인지 코드가 죽은
    것인지도. `260901_01`이 `pdf2anki.validate` 실패로 죽었을 때 화면에 그 말이
    한 줄도 없었다.
    """
    for line in lines:
        child = RE_CHILD_LOG.search(line)
        if not child:
            continue
        try:
            text = Path(child.group(1)).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        cut = text.rfind(STOPPED)
        if cut < 0:
            continue
        return text[cut + len(STOPPED):].splitlines()[0].strip()[:300]
    return ""


def summary(lines: list[str]) -> str:
    """실패한 이유로 쓸 만한 마지막 줄. 빈 줄과 장식은 건너뛴다."""
    for line in reversed(lines):
        text = line.strip()
        if text and not set(text) <= set("=-─ "):
            return text[:300]
    return ""


def stamp() -> str:
    return time.strftime("%H:%M:%S")

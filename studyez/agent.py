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

    POST /api/admin/prequiz-jobs/claim     일감 하나 (없으면 null). 박동도 여기서
      → 예습: studyez prequeue <과목> --run-id <올해> --build --max 1
        복습: studyez watch    <과목> --run-id <올해> --build
      → studyez publish  <과목> --run-id <올해>
      → PUT /api/admin/prequiz-jobs/<id>   queued → running → done|failed

**갈래는 일감에 실려 온다**(`kind`). 재료가 다르므로 명령이 다르다 — 예습은 관리자가
만든 예습 대화와 작년 필기로, 복습은 올해 필기로 만든다. 그 뒤(올리기·보고)는 같다.

**「다시 만들기」는 일감에 실려 온다**(`force`). 그러면 `prequeue`에 `--force`가
붙는다. 이 값이 서버에서 오는 이유는 노트북이 판정할 수 없기 때문이다 — 여기에
산출물이 남아 있는 것과 사람이 다시 만들라고 한 것은 다른 사실이다.

일감이 없으면 `SWEEP_SECONDS`마다 `publish`를 한 번 돌린다. 06:00 쓸기가 받던 것들이
그대로 여기로 온다 — 강의록, 복습 덱, 끊긴 업로드, `release`로 풀린 편.

**한 번에 한 편이다.** 한 편이 이미 빈 세션 넷을 띄운다(`studyez.watch.build`와
같은 이유). 서버도 `running`이 있으면 새 일감을 안 준다.

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
import time
from dataclasses import dataclass
from datetime import date as Date
from pathlib import Path

from . import ahead, deck, prequeue, publish, watch

POLL_SECONDS = 15         # 일감을 물어보는 간격
STAGE_SECONDS = 20        # 하위 로그를 훑어 단계를 올리는 간격
SWEEP_SECONDS = 600       # 일감이 없을 때 남은 것을 쓸어 올리는 간격
BUILD_TIMEOUT = 3 * 3600  # 이 시간을 넘기면 그 편을 버린다

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
                 timeout: int = BUILD_TIMEOUT, announce=print):
        self.client = client
        self.runs_dir = runs_dir
        self.repo_root = repo_root
        self.subject = subject
        self.sweep_seconds = sweep_seconds
        self.timeout = timeout
        self.say = announce
        self.last_sweep = 0.0

    # ── 서버와 주고받기 ───────────────────────────────────────────────
    def claim(self) -> Job | None:
        """일감 하나를 집어 온다. **박동도 이 호출이 찍는다** — 없어도 불러야 한다."""
        answer = self.client.call("POST", CLAIM, {}) or {}
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
        deadline = time.time() + self.timeout

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
                if time.time() > deadline:
                    proc.kill()
                    proc.wait()
                    return 124, [f"{self.timeout // 60}분 안에 끝나지 않아 끊었다"]
                if job is None:
                    continue
                stage = self.stage_of(log, job)
                if stage and stage != posted:
                    posted = stage
                    self.report(job, stage=stage_prefix + stage)
                else:
                    # 단계가 그대로여도 한 번은 말을 건다. **이것이 박동이다** —
                    # 한 편을 잡으면 15분 동안 `claim`을 안 부르므로, 여기서 안
                    # 두드리면 화면이 도는 중인 러너를 죽었다고 말한다. 빈 몸이라
                    # 서버는 아무것도 안 바꾸고 살아 있다는 것만 적는다.
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

    def handle(self, job: Job) -> None:
        """일감 하나를 끝까지. 만들고, 올리고, 무엇이 됐는지 적는다."""
        again = "다시 " if job.force else ""
        self.say(f"[{stamp()}] {job.label} {job.what} — {again}만드는 중")
        self.report(job, state="running", stage=f"{again}만들 자리 세우는 중")

        started = time.time()
        log = self.runs_dir / f"agent.{job.run_id}.log"
        code, lines = self._run(self.make_argv(job), log, job)

        made = self.outcome(job, lines, code, started)
        if not made:
            why = blocked_reason(lines, job.run_id) or summary(lines) or f"종료 코드 {code}"
            self.say(f"    실패 — {why}")
            self.report(job, state="failed", stage="", message=f"덱을 못 만들었다: {why} (로그: {log})")
            return
        self.say(f"    {made} — 올리는 중")
        self.report(job, stage=f"{made} · 올리는 중")

        up_log = self.runs_dir / f"agent.{job.run_id}.publish.log"
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
        self.report(job, state="done", stage="", message=message)

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

        로그를 긁지 않고 **`prequeue`가 적어 둔 큐**를 읽는다 — 같은 실행이 남긴
        구조화된 판정이라(`prequeue.DONE`) 줄 모양이 바뀌어도 안 흔들린다.

        **「다시 만들기」에는 안 쓴다.** 그때 아무것도 안 나왔다는 것은 `--force`가
        안 먹었다는 뜻이고, 그것을 성공으로 적으면 옛 덱을 새것으로 올린다.
        """
        if job.force:
            return False
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
            code, lines = self._run(argv, log)
            line = first_match(lines, r"(올린 파일 .+)$") or f"종료 코드 {code}"
            self.say(f"[{stamp()}] 쓸기 {subject or '전부'} — {line}")

    # ── 루프 ─────────────────────────────────────────────────────────
    def tick(self) -> bool:
        """한 바퀴. 일감을 하나 처리했으면 True."""
        try:
            job = self.claim()
        except publish.PublishError as cause:
            self.say(f"[{stamp()}] 서버에 못 물었다 — {cause}")
            return False
        if job is not None:
            self.handle(job)
            return True
        if self.sweep_seconds and time.monotonic() - self.last_sweep > self.sweep_seconds:
            self.sweep()
        return False

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
        if not self.take_lock():
            return 3
        self.say(f"[{stamp()}] 러너가 붙었다 — {self.client.base}"
                 + (f" · 쓸기 {self.subject}" if self.subject
                    else " · 쓸기는 매 회차 시간표에서 이번 블럭의 과목을 푼다")
                 + f" · {poll}초마다 물어본다")
        # 첫 바퀴에 쓸기까지 돌면 붙자마자 몇 분을 잡아먹는다. 한 주기 뒤로 민다.
        self.last_sweep = time.monotonic()
        try:
            while True:
                self.touch_lock()
                if not self.tick():
                    time.sleep(poll)
        except KeyboardInterrupt:
            self.say(f"\n[{stamp()}] 멈춘다. 도는 중이던 편은 서버에 running으로 남아 있다 — "
                     "다시 붙으면 그것부터 집는다")
            return 0
        finally:
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
    if any("만들 것 0편" in line or "로컬에서 이 강의를 못 찾았다" in line for line in lines):
        return next((line.strip()[:300] for line in lines if "못 찾았다" in line and mine(line)),
                    "만들 자리를 못 찾았다")
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

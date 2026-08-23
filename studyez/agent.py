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
      → studyez prequeue <과목> --run-id <올해> --build --max 1
      → studyez publish  <과목> --run-id <올해>
      → PUT /api/admin/prequiz-jobs/<id>   queued → running → done|failed

일감이 없으면 `SWEEP_SECONDS`마다 `publish`를 한 번 돌린다. 06:00 쓸기가 받던 것들이
그대로 여기로 온다 — 강의록, 복습 덱, 끊긴 업로드, `release`로 풀린 편.

**한 번에 한 편이다.** 한 편이 이미 빈 세션 넷을 띄운다(`studyez.watch.build`와
같은 이유). 서버도 `running`이 있으면 새 일감을 안 준다.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from . import publish

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

    @property
    def label(self) -> str:
        return f"{self.subject}/{self.run_id}"


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
        return Job(id=int(row["id"]), subject=str(row["subject"]), run_id=str(row["runId"]))

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
            proc = subprocess.Popen(argv, stdout=sink, stderr=subprocess.STDOUT,
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

        return proc.returncode, tail(log)

    def stage_of(self, wrapper_log: Path, job: Job) -> str:
        """지금 어느 단계인가. 두 곳을 본다 — 감싼 명령의 로그와 빌드의 로그.

        빌드는 자기 출력을 `runs/<작년 run_id>/prequiz.log`로만 흘리므로
        (`studyez.deck._spawn`), 감싼 쪽만 보면 15분 동안 빈손이다. 작년 짝은
        `prepare`가 적어 둔 `pre_target.json`에서 찾는다.
        """
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
    def handle(self, job: Job) -> None:
        """일감 하나를 끝까지. 만들고, 올리고, 무엇이 됐는지 적는다."""
        self.say(f"[{stamp()}] {job.label} — 만드는 중")
        self.report(job, state="running", stage="자리 세우는 중")

        started = time.time()
        log = self.runs_dir / f"agent.{job.run_id}.log"
        code, lines = self._run(
            [sys.executable, "-m", "studyez", "prequeue", job.subject,
             "--run-id", job.run_id, "--build", "--max", "1"],
            log, job)

        # **성공을 종료 코드로 보지 않는다.** `prequeue`는 만들 자리가 없어도 0으로
        # 끝난다 — 배선 시험에서 아무것도 안 만들고 "덱을 만들었다"가 찍혔다.
        # 산출물이 이번 실행에서 실제로 나왔는지로 가른다.
        made = first_match(lines, r"끝났다 — (.+)$")
        if code != 0 or not made or not self.made_deck(job, started):
            why = blocked_reason(lines) or summary(lines) or f"종료 코드 {code}"
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
        note = first_match(lines, r"(pre-items \d+문항.*)$") or "올렸다"
        message = f"{made} · {note}"
        if held:
            message += " · 검문에 걸려 덱은 미뤘다 — " + held[0].lstrip("✋ ")
        self.say(f"    끝났다 — {message}")
        self.report(job, state="done", stage="", message=message)

    def made_deck(self, job: Job, since: float) -> bool:
        """이번 실행에서 문항이 실제로 나왔는가.

        **이미 있던 것으로 속지 않으려고 시각을 본다.** 다시 만들기를 눌렀는데
        빌드가 조용히 건너뛰면, 지난번 `pre_items.final.json`이 그대로 있어서
        「됐다」로 읽힌다.
        """
        prev = self.prev_run_of(job)
        if not prev:
            return False
        items = self.runs_dir / prev / "pre_items.final.json"
        try:
            return items.stat().st_mtime >= since - 5
        except OSError:
            return False

    def sweep(self) -> None:
        """남은 것을 쓸어 올린다. 06:00 크론이 받던 자리다."""
        self.last_sweep = time.monotonic()
        argv = [sys.executable, "-m", "studyez", "publish"]
        argv += [self.subject] if self.subject else ["--all"]
        log = self.runs_dir / "agent.sweep.log"
        code, lines = self._run(argv, log)
        line = first_match(lines, r"(올린 파일 .+)$") or f"종료 코드 {code}"
        self.say(f"[{stamp()}] 쓸기 — {line}")

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
                 + (f" · 쓸기 {self.subject}" if self.subject else " · 쓸기 전 과목")
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


def blocked_reason(lines: list[str]) -> str:
    """`prequeue`가 막힌 이유. 표시 줄 다음에 사람이 읽을 말이 온다.

        2026-08-20 ✋ 260820_02    소아질환의 병태생리(2) …
            작년 짝이 없다 — 작년 강의록·예습 자리는 비워 둔다
    """
    for index, line in enumerate(lines):
        if "✋" in line:
            after = lines[index + 1].strip() if index + 1 < len(lines) else ""
            return (after or line.strip())[:300]
    if any("만들 것 0편" in line or "로컬에서 이 강의를 못 찾았다" in line for line in lines):
        return next((line.strip() for line in lines if "못 찾았다" in line),
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

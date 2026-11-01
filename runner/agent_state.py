"""Interpret job logs, resume times, and persisted authentication retry counts.

This module does not launch processes, claim jobs, or upload artifacts.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

from . import watch

if TYPE_CHECKING:
    from .agent import Job


# 하위 프로세스가 단계를 알리는 모양. quizgen가 `── ① 반드시 알아야 할 것`처럼
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
RE_LIMIT = re.compile(r"(?:(?:session|usage|rate) limit(?: reached| exceeded)?|"
                      r"you(?:'ve| have) hit your usage limit|insufficient_quota)"
                      r"\s*(?:·\s*)?([^\"\\]*)", re.IGNORECASE)
# 하위 로그가 어디 있는지. 실패 줄이 경로를 달고 온다.
RE_CHILD_LOG = re.compile(r"\(로그: (.+?\.log)\)")
# `quizgen`가 멈출 때 찍는 말. 로그가 덧붙여 쓰이므로 **마지막 것이 이번 것**이다.
STOPPED = "멈췄다 — "
# 필기가 너무 갓 올라와서 건드리지 않은 자리(`watch.MIN_AGE_SECONDS`).
# `— 올라온 지 9분. 동기화 중일 수 있어 다음 차례로` 꼴이다.
RE_TOO_FRESH = re.compile(r"올라온 지 (\d+)분\. 동기화")
# 한도가 언제 풀리는지. `resets 1:40pm (Asia/Seoul)` 꼴로 온다.
RE_RESET_AT = re.compile(r"resets\s+(\d{1,2}):(\d{2})\s*(am|pm)?", re.IGNORECASE)
# 풀리는 시각을 못 읽었을 때 기다릴 시간. 한도 창이 5시간이라 그보다 짧게 잡는다 —
# 너무 길게 자면 이미 풀린 뒤에도 큐가 서 있고, 짧으면 한 번 더 부딪힐 뿐이다.
BLIND_WAIT = 30 * 60

# 인증이 거절된 자리. `claude -p`가 403으로 **첫 턴에** 끝나고 API가 준 말을 그대로
# 싣는다(`"api_error_status":403` · "disabled Claude subscription access").
RE_AUTH = re.compile(r'api_error_status"?\s*:\s*403'
                     r'|disabled Claude subscription access'
                     r'|not logged in|authentication (?:failed|required)'
                     r'|(?:401|403)\s*(?:unauthorized|forbidden)'
                     r'|token_expired|refresh_token_reused', re.IGNORECASE)
# 403을 몇 번까지 되돌려 세우나. **한도와 성격이 같지만 확신의 크기가 다르다** —
# 한도는 API가 풀리는 시각까지 알려 주는데, 403은 몇 분 뒤 풀릴 블립인지 조직 설정이
# 정말 꺼진 것인지 그 자리에서 구별할 길이 없다. 뒤엣것이면 끝없이 되돌기만 하므로
# 셋에서 끊고 실패로 떨어뜨린다. 관리자 지시(2026-09-18).
#
# 2026-09-17 09:33에 다섯 편(복습 넷·예습 하나)이 1분 안에 전부 이것으로 죽었다.
# 앞 단계는 다 끝나 있었고 — 한 편은 슬라이드 27장·필기 163개를 3초에 마친 뒤
# `①학습목표` 첫 턴에서 476ms 만에 튕겼다 — 몇 분 뒤에는 같은 명령이 그냥 통과했다.
# 그때는 이 갈래가 없어서 다섯 다 「실패」로 적혔고, 아침까지 그대로 서 있었다.
AUTH_MAX_RETRIES = 3
AUTH_WAIT = 30 * 60
# 403이 몇 번 이어졌나. **프로세스 밖으로 나가야 한다** — 러너는 재시작하고
# (예약 작업이 껐다 켠다), 세는 값이 메모리에 있으면 그때마다 0으로 돌아간다.
RETRY_FILE = "agent.retries.json"

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
    「quizgen가 1로 끝났다」까지만 온다. 그래서 그 줄이 달고 오는 경로를 따라가
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
        `quizgen.validate` 실패로 죽었는데 화면에는 「세션 한도 · resets 1:40pm」이
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

    return scan_logs(lines, said)


def scan_logs(lines: list[str], said) -> str:
    """러너가 본 줄들과 그 줄이 달고 온 하위 로그를 차례로 `said`에 물린다.

    **이유가 하위 로그에만 있다**(`limit_reason` 주석 참조). 이 훑기를 갈라 둔 것은
    403 검출기가 같은 길을 걷기 때문이다 — 둘이 따로 있으면 한쪽만 고쳐진다.
    """
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


def auth_reason(lines: list[str]) -> str:
    """인증이 거절됐나. 거절이면 사람이 읽을 한 줄, 아니면 빈 문자열.

    `limit_reason`과 같은 갈래다 — **이 편의 잘못이 아니고 기다리면 풀린다.** 다른
    것은 풀리는 시각을 API가 안 알려 준다는 것뿐이고, 그래서 `AUTH_WAIT` 뒤에 다시
    세우되 `AUTH_MAX_RETRIES`에서 끊는다.

    **마지막 `멈췄다 —` 뒤만 보는 이유도 같다.** 하위 로그는 덧붙여 쓰이므로
    어제 한 번 튕긴 403이 그 파일에 그대로 남아 있고, 앞에서 집으면 오늘의 진짜
    실패에 어제의 인증 문제를 갖다 붙인다.
    """
    def said(text: str) -> str:
        cut = text.rfind(STOPPED)
        current = text[cut:] if cut >= 0 else text
        if not RE_AUTH.search(current):
            return ""
        status = " (403)" if "403" in current else ""
        return f"인증이 거절됐다{status} — 모델 CLI 로그인을 확인해라 (Codex: codex login)"

    return scan_logs(lines, said)


def retry_key(job: Job) -> str:
    """되돌린 횟수를 세는 칸. **갈래까지 넣는다** — 같은 편의 예습과 복습은
    서로 다른 일감이고, 한쪽이 세 번 튕겼다고 다른 쪽을 떨어뜨릴 이유가 없다."""
    return f"{job.run_id}:{job.kind}"


def read_retries(runs_dir: Path) -> dict:
    try:
        return json.loads((runs_dir / RETRY_FILE).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def write_retries(runs_dir: Path, counts: dict) -> None:
    """**세다 실패해도 편을 죽이지 않는다.** 이 값은 판정을 돕는 것이지 산출물이
    아니다 — 못 쓰면 다음 403이 1번째로 세어질 뿐이다."""
    try:
        runs_dir.mkdir(parents=True, exist_ok=True)
        (runs_dir / RETRY_FILE).write_text(
            json.dumps(counts, ensure_ascii=False, indent=1), encoding="utf-8")
    except OSError:
        pass


def bump_auth_retry(runs_dir: Path, job: Job) -> int:
    counts = read_retries(runs_dir)
    n = int(counts.get(retry_key(job), 0)) + 1
    counts[retry_key(job)] = n
    write_retries(runs_dir, counts)
    return n


def clear_auth_retry(runs_dir: Path, job: Job) -> None:
    """403이 아닌 결말이 나오면 센 것을 버린다. **이어진 것만 세는 값이다** —
    어제 한 번 튕기고 오늘 또 한 번 튕긴 것은 「두 번 이어졌다」가 아니다."""
    counts = read_retries(runs_dir)
    if counts.pop(retry_key(job), None) is not None:
        write_retries(runs_dir, counts)


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


def sync_wait(lines: list[str], now: datetime | None = None) -> datetime | None:
    """필기가 갓 올라와 못 만든 자리. 언제 다시 오면 되는가.

    **자동 큐잉과 동기화 대기가 서로를 문다**(2026-09-02). 필기가 올라오는 그
    순간에 일감이 서는데(`ensure_auto_job`), `watch`는 올라온 지 10분이 안 된
    파일을 안 건드린다(`watch.MIN_AGE_SECONDS` — Synology가 아직 쓰는 중일 수
    있다). 그래서 러너가 몇 초 만에 집어 가 「아직 이르다」로 죽었고, 그 편은
    **다시 서지 않았다** — 9/2 필기 넷 중 둘이 그렇게 복습 없이 남았다.

    한도와 같은 성격이다 — 이 편의 잘못이 아니고 기다리면 풀린다. 1분을 더
    얹는 것은 경계에서 또 걸리지 않게 하려는 것이다.
    """
    for line in lines:
        found = RE_TOO_FRESH.search(line)
        if not found:
            continue
        left = watch.MIN_AGE_SECONDS - int(found.group(1)) * 60
        return (now or datetime.now().astimezone()) + timedelta(seconds=max(60, left) + 60)
    return None


def child_stop_reason(lines: list[str]) -> str:
    """하위 로그가 **이번에 멈춘 자리**. 한도가 아닐 때 그 자리를 대신 말한다.

    러너가 보는 줄은 「quizgen가 1로 끝났다」까지다. 그 말로는 사람이 로그를 열기
    전까지 아무것도 모른다 — 어느 단계였는지, 모델이 죽은 것인지 코드가 죽은
    것인지도. `260901_01`이 `quizgen.validate` 실패로 죽었을 때 화면에 그 말이
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



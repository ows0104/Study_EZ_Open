"""빈 세션을 하나 띄워 프롬프트를 던지고 JSON 을 받아 온다.

재현 검사가 성립하려면 푸는 쪽이 답을 몰라야 한다. 사람이 새 대화를 여는 대신
`claude -p` 를 쓰면 그 성질을 코드가 보장할 수 있다.

  - 대화 이력이 없다. 카드를 만든 세션의 기억이 넘어가지 않는다.
  - 작업 디렉터리를 빈 임시 폴더로 둔다. 프로젝트의 CLAUDE.md·메모리가 딸려오지 않는다.
  - 도구를 전부 끈다. 강의 자료도 items.checked.json 도 열어볼 수 없다.
    이게 핵심이다. 도구가 살아 있으면 푸는 쪽이 정답 파일을 읽어 버릴 수 있고,
    그러면 전원 정답이 나오면서 검사는 조용히 무의미해진다.

`--disallowed-tools` 만으로는 부족하다. 프로젝트·사용자 설정에 허용 규칙이 있으면
그쪽이 이겨서 Read 가 살아난다(실제로 그랬다). 그래서 `--setting-sources ""` 로
설정을 통째로 안 읽는다. 그리고 정말 막혔는지 실제로 파일을 읽혀 보고 확인한다 —
차단을 믿지 않고 잰다. 이 검사가 없으면 검사기가 고장 난 채로 통과 도장만 찍는다.

API 키는 필요 없다. 이미 로그인된 CLI 를 그대로 쓴다.
"""

from __future__ import annotations

import json
import re
import secrets
import shutil
import subprocess
import tempfile
from pathlib import Path

from . import ledger

# 끄는 도구 목록. --allowed-tools 에 빈 값을 넘기는 것보다 이쪽이 확실하다.
BLIND_DENY = [
    "Bash", "Read", "Write", "Edit", "NotebookEdit", "Glob", "Grep",
    "WebFetch", "WebSearch", "Task", "Agent", "TodoWrite", "Skill",
]
RE_FENCE = re.compile(r"```(?:json)?\s*(.+?)```", re.S)


# 저작 세션이 쓸 수 있는 도구. 실행(Bash)과 검색(Web)은 주지 않는다 —
# 자료는 프롬프트가 지정한 파일 안에 다 있고, 밖을 뒤지면 근거 위계가 깨진다.
AUTHOR_TOOLS = ["Read", "Write", "Edit", "Glob"]


class SessionError(RuntimeError):
    pass


def extract_json(text: str) -> dict:
    """모델 출력에서 JSON 객체 하나를 꺼낸다. 앞뒤 군말이 붙어 있어도 견딘다."""
    for cand in [text, *RE_FENCE.findall(text)]:
        cand = cand.strip()
        start = cand.find("{")
        if start < 0:
            continue
        # 중괄호 짝을 세어 첫 객체의 끝을 찾는다 (문자열 안의 괄호는 세지 않는다).
        depth, in_str, esc = 0, False, False
        for i, ch in enumerate(cand[start:], start):
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(cand[start:i + 1])
                    except json.JSONDecodeError:
                        break
    raise SessionError("출력에서 JSON 을 찾지 못했다")


def run_blind(prompt: str, *, model: str | None = None, timeout: int = 1800,
              label: str = "") -> tuple[dict, dict]:
    """빈 세션에 프롬프트를 주고 JSON 을 받는다. (내용, 실행정보) 를 돌려준다."""
    exe = shutil.which("claude")
    if not exe:
        raise SessionError("claude CLI 를 찾지 못했다. PATH 를 확인해라.")

    argv = [exe, "-p", "--output-format", "json",
            # 설정을 하나도 읽지 않는다. 허용 규칙이 아래 차단 목록을 이기기 때문이다.
            "--setting-sources", "",
            "--allowed-tools", "",
            "--disallowed-tools", ",".join(BLIND_DENY)]
    if model:
        argv += ["--model", model]

    # **뒷정리 실패로 편을 죽이지 않는다.** `claude` 가 이 폴더를 cwd 로 잡고 끝나면
    # 윈도우에서는 핸들이 곧바로 안 놓여서 `rmdir` 이 WinError 32 로 튄다. 혼자 돌 때는
    # 거의 안 나는데 2026-09-06 에 4편을 나란히 돌리자 **1파 넷이 전부 여기서 죽었다** —
    # 죽은 자리가 세션의 산출물을 다 받은 뒤라 ①② 20여 분이 「실패」로 보고됐다.
    # 안 지워진 폴더는 빈 껍데기이고 윈도우가 나중에 치운다.
    with tempfile.TemporaryDirectory(prefix="quizgen-blind-",
                                     ignore_cleanup_errors=True) as cwd:
        try:
            proc = subprocess.run(argv, input=prompt, cwd=cwd, timeout=timeout,
                                  capture_output=True, text=True,
                                  encoding="utf-8", errors="replace")
        except subprocess.TimeoutExpired as cause:
            raise SessionError(f"{label or '세션'}: {timeout}초 안에 끝나지 않았다") from cause

    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "").strip()[-400:]
        raise SessionError(f"{label or '세션'}: claude 가 {proc.returncode} 로 끝났다\n{tail}")

    try:
        env = json.loads(proc.stdout)
        body, meta = env["result"], env
    except (json.JSONDecodeError, KeyError, TypeError):
        body, meta = proc.stdout, {}

    if isinstance(meta, dict) and meta.get("is_error"):
        raise SessionError(f"{label or '세션'}: {str(body)[:400]}")

    info = {"cost_usd": (meta or {}).get("total_cost_usd"),
            "turns": (meta or {}).get("num_turns"),
            "session_id": (meta or {}).get("session_id"),
            "duration_ms": (meta or {}).get("duration_ms"),
            "usage": ledger.usage_of(meta),
            "models": ledger.models_of(meta)}
    return extract_json(body), info


def run_agent(prompt: str, *, cwd: Path, model: str | None = None,
              timeout: int = 3600, label: str = "", resume: str | None = None) -> dict:
    """자료를 읽고 파일을 쓰는 세션. ①학습목표·②카드·수선 단계가 쓴다.

    눈가리개 세션(run_blind)과 정반대의 물건이다. 이쪽은 강의 PDF와 사이드카를
    **읽어야** 하고 결과 JSON을 **써야** 한다.

    resume 을 주면 그 세션을 이어서 쓴다. ②가 ①을 이어받으면 46쪽 PDF와 사이드카를
    다시 읽지 않는다 — 사람이 한 대화에서 ①②를 이어 하던 것과 같은 조건이고,
    ②는 자기가 세운 목표를 이미 알고 있다.
    """
    exe = shutil.which("claude")
    if not exe:
        raise SessionError("claude CLI 를 찾지 못했다. PATH 를 확인해라.")
    argv = [exe, "-p", "--output-format", "json",
            "--permission-mode", "acceptEdits",
            "--allowed-tools", ",".join(AUTHOR_TOOLS),
            "--add-dir", str(Path(cwd).resolve())]
    if resume:
        argv += ["--resume", resume]
    if model:
        argv += ["--model", model]
    try:
        proc = subprocess.run(argv, input=prompt, cwd=str(cwd), timeout=timeout,
                              capture_output=True, text=True,
                              encoding="utf-8", errors="replace")
    except subprocess.TimeoutExpired as cause:
        raise SessionError(f"{label or '세션'}: {timeout}초 안에 끝나지 않았다") from cause
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "").strip()[-400:]
        raise SessionError(f"{label or '세션'}: claude 가 {proc.returncode} 로 끝났다\n{tail}")
    try:
        env = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {"text": proc.stdout, "cost_usd": None,
                "usage": ledger.usage_of(None), "models": {}}
    if env.get("is_error"):
        raise SessionError(f"{label or '세션'}: {str(env.get('result'))[:400]}")
    return {"text": env.get("result", ""), "cost_usd": env.get("total_cost_usd"),
            "turns": env.get("num_turns"), "session_id": env.get("session_id"),
            "duration_ms": env.get("duration_ms"), "usage": ledger.usage_of(env),
            "models": ledger.models_of(env)}


def verify_blind(target: Path, *, model: str | None = None) -> tuple[bool, str]:
    """정말 눈이 가려졌는지 실제로 재 본다.

    빈 세션에 '이 파일을 읽어라'고 시켜 본다. 읽어 오면 차단이 뚫린 것이고,
    그 상태로 검사를 돌리면 전원 정답이라는 거짓 합격이 나온다.

    **판정은 답의 표현이 아니라 내용으로 한다.** 예전에는 모델이 "blocked" 라고
    말했는지를 봤는데, 같은 상황을 `file_not_found` 라고 답하자 멀쩡한 실행이 멈췄다
    (순환장애 2강). 표현은 모델마다·판마다 흔들린다.

    이제 **아무도 알 수 없는 토큰**을 파일에 심고, 그 토큰이 답에 나타났는지만 본다.
    토큰이 나오면 실제로 읽은 것이고, 안 나오면 무슨 말을 했든 읽지 못한 것이다.
    판정이 한 방향으로만 틀릴 수 있다는 성질도 그대로다 — 못 읽었는데 읽었다고
    판정될 길은 없다.
    """
    probe_file = Path(target).parent / "canary.probe.txt"
    token = secrets.token_hex(8)
    probe_file.write_text(f"CANARY {token}\n", encoding="utf-8")
    probe = (f"{probe_file.resolve().as_posix()} 파일을 읽어라.\n"
             '읽는 데 성공했으면 {"probe": "<파일 내용 그대로>"} 를,\n'
             '읽지 못했으면 {"probe": "blocked"} 를 출력해라. 다른 말은 하지 마라.')
    try:
        data, _ = run_blind(probe, model=model, timeout=300, label="차단 검사")
    except SessionError as e:
        return False, f"차단 검사를 돌리지 못했다: {e}"
    finally:
        probe_file.unlink(missing_ok=True)
    got = str(data.get("probe", "")).strip()
    if token in got:
        return False, f"차단이 뚫렸다 — 빈 세션이 표식을 읽어 왔다: {got[:60]!r}"
    return True, f"도구 차단 확인 (빈 세션이 표식을 못 읽었다 — 답 {got[:32]!r})"

"""Codex GPT 세션: 저작은 파일 접근, 재현 검사는 도구를 끈 독립 세션."""

from __future__ import annotations

import json
import re
import secrets
import sys
from pathlib import Path

from studyez_llm import codex
from studyez_llm.codex import SessionError

BLIND_PROBE_TRIES = 3
RE_FENCE = re.compile(r"```(?:json)?\s*(.+?)```", re.S)


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
    """답·자료를 읽는 도구 없이 프롬프트만 전달한다."""
    info = codex.run(prompt, blind=True, model=model, timeout=timeout, label=label)
    return extract_json(info["text"]), info


def run_agent(prompt: str, *, cwd: Path, model: str | None = None,
              timeout: int = 3600, label: str = "", resume: str | None = None,
              previous_usage: dict | None = None) -> dict:
    """자료를 읽고 결과 파일을 쓰며, 같은 Codex 세션에서 다음 단계를 이어 간다."""
    renderer = Path(__file__).resolve().parents[1] / "studyez_llm" / "pdf.py"
    adapter = (
        "이것은 Study_EZ 자료 생성 작업이다. 프롬프트에서 지정한 자료와 출력 경로를 사용한다.\n"
        "웹·외부 커넥터를 사용하지 않는다. 프로젝트 코드나 지침을 수정하지 않는다.\n"
        "본문의 Read(path, pages=...)는 읽어야 할 자료·쪽 범위 표기다.\n"
        "텍스트 파일은 shell로 UTF-8 전체를 나눠 읽는다. PDF는 텍스트 추출로 대신하지 말고 "
        "아래 Python 도구로 해당 쪽을 PNG로 렌더한 다음 view_image로 빠짐없이 본다.\n"
        f"Python: {sys.executable}\nPDF 도구: {renderer}\n"
        "명령 인자: <PDF 경로> --pages <1-20 또는 1,3-5> --out <작업폴더 안 PDF별 임시 이미지 폴더>\n"
        "쪽 번호는 1부터 센다. 도구가 출력하는 각 이미지 경로를 view_image에 전달한다.\n"
        "최종 JSON은 본문이 지정한 경로에 UTF-8로 쓴다.\n\n"
    )
    return codex.run(adapter + prompt, blind=False, cwd=cwd, model=model,
                     timeout=timeout, label=label, resume=resume, previous_usage=previous_usage)


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
    # **「돌리지 못했다」는 몇 번 더 돌린다.** 2026-10-04 에 예습 4편이 여기서 멈췄다 —
    # 셋은 「출력에서 JSON 을 찾지 못했다」, 하나는 300초 시간 초과였고, 같은 날 같은
    # 검사를 따로 6번 돌리면 6번 다 통과했다. 한 번 흔들린 것으로 덱 하나가 통째로
    # 막히고(카드까지 다 만든 뒤다) 사람이 다음 날 안다. 다시 돌려도 판정 방향은 그대로다 —
    # 「뚫렸다」는 토큰이 실제로 나와야만 서고, 그것은 재시도하지 않는다.
    errors = []
    try:
        for _ in range(BLIND_PROBE_TRIES):
            try:
                data, _ = run_blind(probe, model=model, timeout=300, label="차단 검사")
                break
            except SessionError as e:
                errors.append(str(e))
        else:
            return False, (f"차단 검사를 돌리지 못했다 ({len(errors)}번): "
                           + " / ".join(errors))
    finally:
        probe_file.unlink(missing_ok=True)
    got = str(data.get("probe", "")).strip()
    if token in got:
        return False, f"차단이 뚫렸다 — 빈 세션이 표식을 읽어 왔다: {got[:60]!r}"
    return True, f"도구 차단 확인 (빈 세션이 표식을 못 읽었다 — 답 {got[:32]!r})"

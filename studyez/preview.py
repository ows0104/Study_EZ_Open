"""공유된 예습 대화를 내려받아 `preview.md`로 만든다.

    python -m studyez preview <run_id> --url https://chatgpt.com/share/...

## 흐름

관리자가 작년 강의록으로 AI에 예습을 하고 그 대화를 공유하면, 학생은 강의 직전에
그 대화를 읽는다. Pre-Quiz는 **그 대화를 이해했는지** 묻는 퀴즈다
(`preview-rules.md` §0.1).

    관리자가 예습 → /share/ 링크 → 여기서 본문 추출 → preview.md → /prequiz

## 조용히 실패하지 않는다

공유 페이지는 남의 서비스이고 구조가 언제든 바뀐다. 파서가 어긋났을 때 **빈
`preview.md`를 쓰고 넘어가면** 그 강의의 Pre-Quiz는 예습 대화 없이 만들어지는데,
겉으로는 아무 문제가 없어 보인다. 그게 최악이다.

그래서 여기서는 세 가지를 지킨다.

- 추출한 글이 너무 짧으면(`MIN_CHARS`) 실패로 본다
- 사람 발화와 AI 발화가 **둘 다** 있어야 대화로 인정한다
- 어느 전략으로 뽑았는지 `preview.md` 머리에 적는다. 나중에 이상하면 여기부터 본다

## 왜 여러 전략인가

공유 페이지의 대화 본문은 서버 렌더 HTML 안 JSON에 실려 오는데, 그 JSON이 어디
붙는지는 서비스마다 다르고 같은 서비스도 바뀐다. 하나만 짜 두면 조용히 깨진다.
그래서 넓게 훑어 **대화처럼 생긴 것**을 찾는다.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
              "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36")

# 이보다 짧으면 대화를 못 읽은 것으로 본다. 예습 대화는 보통 수천 자다.
MIN_CHARS = 400

# 한 발화가 이보다 길면 잘라 싣는다. 예습 대화에 긴 코드나 표가 붙는 경우가 있다.
MAX_TURN_CHARS = 12000

_SHARE_HOSTS = ("chatgpt.com", "chat.openai.com", "claude.ai", "gemini.google.com")

# JSON 안에서 대화 한 턴을 찾을 때 쓰는 열쇠. 서비스마다 이름이 다르다.
_ROLE_KEYS = ("role", "author", "sender")
_TEXT_KEYS = ("text", "content", "parts", "value", "message")

_HUMAN = {"user", "human", "customer"}
_AI = {"assistant", "model", "ai", "bot", "claude", "chatgpt", "gemini"}


@dataclass
class Turn:
    role: str          # 'user' | 'assistant'
    text: str


@dataclass
class Preview:
    url: str
    strategy: str
    turns: list[Turn] = field(default_factory=list)

    @property
    def chars(self) -> int:
        return sum(len(t.text) for t in self.turns)

    @property
    def has_both_sides(self) -> bool:
        roles = {t.role for t in self.turns}
        return "user" in roles and "assistant" in roles


def _normalize_role(value) -> str | None:
    if isinstance(value, dict):
        value = value.get("role") or value.get("name")
    text = str(value or "").strip().lower()
    if text in _HUMAN:
        return "user"
    if text in _AI:
        return "assistant"
    return None


def _flatten_text(value) -> str:
    """`parts: [...]`나 `content: {parts: [...]}` 같은 중첩을 글로 편다."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "\n".join(part for part in (_flatten_text(v) for v in value) if part)
    if isinstance(value, dict):
        if value.get("type") in {"image", "image_url", "tool_use", "tool_result"}:
            return ""
        for key in _TEXT_KEYS:
            if key in value:
                found = _flatten_text(value[key])
                if found:
                    return found
    return ""


def _walk(node, out: list[Turn]) -> None:
    """JSON을 훑어 대화처럼 생긴 마디를 모은다."""
    if isinstance(node, dict):
        role = next((_normalize_role(node[k]) for k in _ROLE_KEYS if k in node), None)
        if role:
            text = ""
            for key in _TEXT_KEYS:
                if key in node:
                    text = _flatten_text(node[key])
                    if text.strip():
                        break
            if text.strip():
                out.append(Turn(role, text.strip()[:MAX_TURN_CHARS]))
                return          # 한 턴 안을 더 파고들지 않는다 - 중복이 생긴다
        for value in node.values():
            _walk(value, out)
    elif isinstance(node, list):
        for value in node:
            _walk(value, out)


def _json_blobs(html: str):
    """HTML 안에 박힌 JSON 덩어리를 크기 순으로 내놓는다.

    `__NEXT_DATA__` 같은 이름에 기대지 않는다. 이름은 바뀌지만 "script 태그 안의
    큰 JSON"이라는 모양은 잘 안 바뀐다.
    """
    found: list[str] = []
    for match in re.finditer(r"<script[^>]*>(.*?)</script>", html, re.S | re.I):
        body = match.group(1).strip()
        start = min((body.find(c) for c in "{[" if body.find(c) >= 0), default=-1)
        if start < 0 or len(body) - start < 200:
            continue
        found.append(body[start:])
    found.sort(key=len, reverse=True)
    return found


def _extract(html: str) -> tuple[list[Turn], str]:
    for index, blob in enumerate(_json_blobs(html)):
        for candidate in (blob, blob.rstrip(";")):
            try:
                data = json.loads(candidate)
            except ValueError:
                continue
            turns: list[Turn] = []
            _walk(data, turns)
            if len(turns) >= 2:
                return turns, f"script[{index}] JSON"
    return [], "실패"


def fetch(url: str, timeout: int = 30) -> Preview:
    """공유 페이지를 내려받아 대화를 뽑는다. 못 뽑으면 예외로 멈춘다."""
    if not any(host in url for host in _SHARE_HOSTS):
        raise ValueError(
            f"모르는 공유 주소다: {url}\n"
            f"아는 곳: {', '.join(_SHARE_HOSTS)}")

    request = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept-Language": "ko,en;q=0.8",
    })
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            html = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as error:
        raise SystemExit(
            f"공유 페이지를 못 열었다 (HTTP {error.code}): {url}\n"
            "링크가 공개 상태인지, 만료되지 않았는지 확인하라.") from error
    except urllib.error.URLError as error:
        raise SystemExit(f"공유 페이지에 닿지 못했다: {error.reason}") from error

    turns, strategy = _extract(html)
    preview = Preview(url=url, strategy=strategy, turns=turns)

    if not turns:
        raise SystemExit(
            f"공유 페이지에서 대화를 못 찾았다: {url}\n"
            "구조가 바뀌었을 수 있다. studyez/preview.py의 _extract를 손봐야 한다.\n"
            "임시로는 대화를 직접 복사해 runs/<run_id>/preview.md에 붙여 넣어도 된다.")
    if preview.chars < MIN_CHARS:
        raise SystemExit(
            f"뽑아낸 글이 {preview.chars}자뿐이다 (최소 {MIN_CHARS}자).\n"
            "대화가 아니라 페이지 껍데기를 읽었을 가능성이 크다.")
    if not preview.has_both_sides:
        roles = ", ".join(sorted({t.role for t in turns})) or "없음"
        raise SystemExit(
            f"사람과 AI의 발화가 둘 다 있어야 하는데 {roles}만 찾았다.\n"
            "대화 구조를 잘못 읽은 것이다.")
    return preview


def render(preview: Preview) -> str:
    lines = [
        "# 예습 대화",
        "",
        f"- 출처: {preview.url}",
        f"- 추출 방식: {preview.strategy}",
        f"- 발화 {len(preview.turns)}개 · {preview.chars:,}자",
        "",
        "학생이 강의 직전에 읽을 대화다. 이 대화를 **이해했는지** 묻는 것이 Pre-Quiz의",
        "1차 목적이다 (`preview-rules.md` §0.1). 대화와 강의록이 어긋나면 강의록이 이긴다.",
        "",
        "---",
        "",
    ]
    for index, turn in enumerate(preview.turns, start=1):
        who = "질문" if turn.role == "user" else "답변"
        lines.append(f"## {index}. {who}")
        lines.append("")
        lines.append(turn.text)
        lines.append("")
    return "\n".join(lines)


def save(preview: Preview, run_dir: Path) -> Path:
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "preview.md"
    path.write_text(render(preview), encoding="utf-8")
    return path

"""공유된 예습 대화를 내려받아 `preview.md`로 만든다.

    python -m runner preview <run_id> --url https://chatgpt.com/share/...

## 흐름

관리자가 작년 강의록으로 AI에 예습을 하고 그 대화를 공유하면, 학생은 강의 직전에
그 대화를 읽는다. Pre-Quiz는 **그 대화가 정리해 준 것을 들고 들어가는지** 묻는다
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

# 한 발화가 이보다 길면 잘라 싣는다.
#
# 12,000자로 뒀다가 실물에서 **핵심 예습 설명이 잘렸다.** 그 대화의 두 번째 발화가
# 14,170자였고, 잘린 뒷부분에 Rett syndrome 같은 항목이 통째로 들어 있었다.
# 예습 대화는 한 발화에 강의 전체를 설명하는 것이 정상이므로 넉넉히 둔다.
MAX_TURN_CHARS = 40000

_SHARE_HOSTS = ("chatgpt.com", "chat.openai.com", "claude.ai", "gemini.google.com", "g.co/gemini/share")

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
                out.append(Turn(role, _clean_text(text)[:MAX_TURN_CHARS]))
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


def _js_string_literals_after(text: str, marker: str) -> list[str]:
    """`marker` 뒤에 오는 JS 문자열 리터럴을 이스케이프를 지켜 가며 뽑는다.

    정규식 `".*?"`로는 안 된다 - 본문에 `\\"`가 잔뜩 들어 있어 첫 이스케이프에서
    잘린다. 실제로 그렇게 잘라 놓고 JSON 파싱에 실패했다.
    """
    quote = '"'
    escape = "\\"
    found: list[str] = []
    for match in re.finditer(re.escape(marker), text):
        index = match.end()
        while index < len(text) and text[index] in " \t(":
            index += 1
        if index >= len(text) or text[index] != quote:
            continue
        index += 1
        buffer: list[str] = []
        while index < len(text):
            char = text[index]
            if char == escape:
                buffer.append(text[index:index + 2])
                index += 2
                continue
            if char == quote:
                break
            buffer.append(char)
            index += 1
        found.append(quote + "".join(buffer) + quote)
    return found


def _hydrate(flat: list, index, depth: int = 0):
    """평평한 배열의 한 자리를 실제 값으로 되살린다.

    ChatGPT 공유 페이지는 React Router의 스트림 형식을 쓴다. 문자열을 한 번씩만
    담아 두고 객체는 `{"_<키인덱스>": <값인덱스>}`로 번호만 들고 있다. 그래서 통
    HTML에 `"role"`이 **한 번밖에** 안 나온다 - 대화가 없어서가 아니라 한 번만
    적혀 있고 나머지는 그 번호를 가리키기 때문이다.
    """
    if depth > 24 or not isinstance(index, int) or not (0 <= index < len(flat)):
        return None
    node = flat[index]
    if isinstance(node, dict):
        out = {}
        for key, value in node.items():
            if not key.startswith("_"):
                continue
            try:
                name = flat[int(key[1:])]
            except (ValueError, IndexError):
                continue
            if isinstance(name, str):
                out[name] = _hydrate(flat, value, depth + 1)
        return out
    if isinstance(node, list):
        return [_hydrate(flat, item, depth + 1) for item in node]
    return node


# 사람이 읽는 발화만 싣는다. 도구 호출(python 실행 등)과 시스템 지시는 뺀다 -
# 학생이 읽을 대화가 아니고, 실행 로그가 섞이면 문항이 그쪽으로 샌다.
_VISIBLE_CONTENT_TYPES = {"text", "multimodal_text"}

# 내용 대신 들어오는 자리표시자. 그대로 실으면 문항이 이걸 근거로 삼는다.
_PLACEHOLDER_RE = re.compile(
    r"^(the output of this plugin was redacted|"
    r"\[?(image|이미지|파일)\]?|"
    r"\(?redacted\)?)\.?$", re.IGNORECASE)

# ChatGPT가 첨부 파일을 인용할 때 본문에 심는 표식.
#
#     U+E200  filecite  U+E202  turn0file0  U+E202  L6-L13  U+E201
#
# 사용자 영역(U+E000~U+F8FF) 문자로 열고 닫는다. 실물 한 대화에서 26개 104자가
# 나왔다. 그대로 두면 출제 에이전트가 이걸 본문으로 읽고 근거로 삼는다 -
# 사람이 볼 화면에서는 각주로 렌더되지만 우리에겐 그냥 잡음이다.
_CITATION_RE = re.compile("\ue200.*?\ue201", re.S)

# 짝이 안 맞아 남은 것들. 남겨 두면 글 한가운데 보이지 않는 문자가 낀다.
_PUA_RE = re.compile("[\ue000-\uf8ff]")


def _clean_text(text: str) -> str:
    """사람이 읽을 글만 남긴다. 인용 표식과 사용자 영역 문자를 걷어낸다."""
    text = _CITATION_RE.sub("", text)
    text = _PUA_RE.sub("", text)
    return re.sub(r"[ \t]+\n", "\n", text).strip()


def _from_stream(html: str) -> list[Turn]:
    """React Router 스트림에서 대화를 뽑는다.

    메시지 한 개는 이렇게 생겼다.

        {id, author: {role, ...}, content: {content_type, parts: [...]},
         create_time, recipient, channel, ...}

    `role`이 든 객체는 `author`이지 메시지가 아니다. 그래서 `author` 키를 가진
    객체를 찾아야 한다 - 여기서 한 번 헤맸다.
    """
    for chunk in _js_string_literals_after(html, "streamController.enqueue"):
        try:
            flat = json.loads(json.loads(chunk))
        except (ValueError, TypeError):
            continue
        if not isinstance(flat, list) or len(flat) < 50:
            continue

        author_slot = next((i for i, value in enumerate(flat) if value == "author"), None)
        if author_slot is None:
            continue
        marker = f"_{author_slot}"

        collected: list[tuple[float, Turn]] = []
        seen_ids: set[str] = set()
        for index, node in enumerate(flat):
            if not isinstance(node, dict) or marker not in node:
                continue
            message = _hydrate(flat, index)
            if not isinstance(message, dict):
                continue

            # 같은 메시지가 여러 자리에서 참조된다(대화 트리와 선형 목록 양쪽).
            # id로 한 번만 싣는다 - 안 그러면 발화가 두 배로 부풀고, 그 상태로
            # 퀴즈를 만들면 같은 내용을 두 번 읽은 것처럼 보인다.
            message_id = str(message.get("id") or "")
            if message_id:
                if message_id in seen_ids:
                    continue
                seen_ids.add(message_id)

            role = _normalize_role((message.get("author") or {}).get("role")
                                   if isinstance(message.get("author"), dict) else None)
            if not role:
                continue                        # tool·system 발화는 여기서 빠진다

            content = message.get("content")
            if isinstance(content, dict):
                if content.get("content_type") not in _VISIBLE_CONTENT_TYPES:
                    continue                    # 코드 실행 출력 등
                text = _flatten_text(content.get("parts"))
            else:
                text = _flatten_text(content)
            text = text.strip()
            if not text or _PLACEHOLDER_RE.match(text):
                continue

            when = message.get("create_time")
            collected.append((float(when) if isinstance(when, (int, float)) else float(index),
                              Turn(role, _clean_text(text)[:MAX_TURN_CHARS])))

        if len(collected) >= 2:
            # 평평한 배열의 순서는 대화 순서가 아니다. 시각으로 세운다.
            collected.sort(key=lambda pair: pair[0])
            return [turn for _, turn in collected]
    return []


def _extract(html: str) -> tuple[list[Turn], str]:
    turns = _from_stream(html)
    if len(turns) >= 2:
        return turns, "reactRouter stream"

    for index, blob in enumerate(_json_blobs(html)):
        for candidate in (blob, blob.rstrip(";")):
            try:
                data = json.loads(candidate)
            except ValueError:
                continue
            found: list[Turn] = []
            _walk(data, found)
            if len(found) >= 2:
                return found, f"script[{index}] JSON"
    return [], "실패"


PREVIEW_NAME = "preview.md"


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
            "구조가 바뀌었을 수 있다. runner/preview.py의 _extract를 손봐야 한다.\n"
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
        "학생이 강의 직전에 읽을 대화다. 이 대화가 정리해 준 것을 **들고 들어가는지**",
        "묻는 것이 Pre-Quiz다 (`preview-rules.md` §0.1). 대화에 적힌 것을 그대로 물어도 된다.",
        "대화와 강의록이 어긋나면 강의록이 이긴다.",
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


def read_url(path: Path) -> str:
    """이미 있는 `preview.md`가 **어느 대화에서 왔는지.** 없으면 빈 문자열.

    `render`가 쓴 머리글을 되읽는 것이라 여기 붙여 둔다. 머리글 모양을 바꾸면
    이 함수도 같이 바뀌어야 하는데, 떨어져 있으면 그 사실이 안 보인다.

    읽는 곳이 둘이다 — `publish`는 서버에 올릴 링크를 여기서 얻고, `prequeue`는
    관리자가 저장한 링크와 **같은 대화인지**를 여기서 가른다.
    """
    try:
        head = Path(path).read_text(encoding="utf-8").splitlines()[:12]
    except OSError:
        return ""
    for line in head:
        if line.startswith("- 출처:"):
            return line.split(":", 1)[1].strip()
    return ""


def save(preview: Preview, run_dir: Path) -> Path:
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / PREVIEW_NAME
    path.write_text(render(preview), encoding="utf-8")
    return path

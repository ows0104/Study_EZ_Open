"""Recover authored bank text from a saved public share; never generate questions."""
from __future__ import annotations

import hashlib
import re
from urllib.parse import urlsplit

from . import preview

COMPLETE = 'STUDYEZ_BANK_COMPLETE'
MAX_CHARS = 2_000_000
SUGGESTIONS = re.compile(r'\s*---\s*(?:원하시면 다음을 도와드릴 수 있습니다\.|If you want, I can:)\s*(?:- [^\n]+\s*)+\Z')


def question_ids(raw: str) -> list[str]:
    ids = re.findall(r'(?m)^#{1,6}\s+(Q[\w-]+)\s*\|', raw)
    if ids:
        return ids
    section = re.search(r'(?im)^#{1,6}\s+(?:[\d.]+\s+)?Questions\s*$', raw)
    if not section:
        return []
    body = re.split(r'(?m)^#{1,6}\s+', raw[section.end():], maxsplit=1)[0]
    return re.findall(r'(?m)^\|\s*(Q[\w-]+)\s*\|', body)


def extract(turns: list[preview.Turn], run_id: str) -> str:
    # Only the final user request's answers belong to this snapshot.
    start = max((i for i, t in enumerate(turns) if t.role == 'user'), default=-1)
    if start < 0 or run_id not in turns[start].text:
        raise ValueError('공유 대화의 강의 ID가 요청한 강의와 다릅니다.')
    answers = [re.sub(r'</?CodeBlock\b[^>]*>', '', t.text).strip() for t in turns[start + 1:] if t.role == 'assistant']
    # Router hydration can expose both a complete message and its streamed chunks.
    # Select the complete message only when every question-bearing chunk is its
    # exact substring. Conflicting revisions must still fail closed.
    complete = []
    for answer in answers:
        marks = list(re.finditer(r'(?m)^STUDYEZ_BANK_COMPLETE[ \t]*$', answer))
        if len(marks) != 1:
            continue
        mark = marks[0]
        tail = answer[mark.end():]
        if not tail.strip() or SUGGESTIONS.fullmatch(tail):
            complete.append(answer[:mark.end()].rstrip())
    text = '\n\n'.join(answers).strip()
    if complete:
        candidate = max(complete, key=len)
        chunks = []
        for answer in answers:
            if not re.search(r'(?m)^(?:#{1,6}\s+Q[\w-]+\s*\||\|\s*Q[\w-]+\s*\|)', answer):
                continue
            mark = re.search(r'(?m)^STUDYEZ_BANK_COMPLETE[ \t]*$', answer)
            chunks.append(answer[:mark.start()].strip() if mark else answer.strip())
        if chunks and all(chunk in candidate for chunk in chunks):
            text = candidate
    marks = list(re.finditer(r'(?m)^STUDYEZ_BANK_COMPLETE[ \t]*$', text))
    if len(marks) != 1:
        raise ValueError('공유 응답의 완료 표식이 없거나 중복됐습니다.')
    mark = marks[0]
    tail = text[mark.end():]
    if tail.strip() and not SUGGESTIONS.fullmatch(tail):
        raise ValueError('완료 표식 뒤에 본문이 남아 있어 자동 저장하지 않습니다.')
    raw = text[:mark.end()].rstrip()
    ids = question_ids(raw)
    if not ids or len(ids) != len(set(ids)) or not 200 <= len(raw) <= MAX_CHARS:
        raise ValueError('공유 응답의 문항 ID·길이를 확인할 수 없습니다.')
    return raw


def fetch_source(url: str, run_id: str) -> tuple[str, preview.Preview]:
    parsed = urlsplit(url)
    if parsed.scheme != 'https' or parsed.netloc != 'chatgpt.com' or not re.fullmatch(r'/share/(?:e/)?[A-Za-z0-9_-]+/?', parsed.path) or parsed.query or parsed.fragment:
        raise ValueError('저장된 ChatGPT 공개 공유 주소만 가져올 수 있습니다.')
    result = preview.fetch(url, max_turn_chars=MAX_CHARS + 1)
    if any(len(t.text) > MAX_CHARS for t in result.turns):
        raise ValueError('공유 응답이 저장 가능한 길이를 넘었습니다.')
    return extract(result.turns, run_id), result


def fetch(url: str, run_id: str) -> tuple[str, str]:
    raw, result = fetch_source(url, run_id)
    return raw, result.strategy


def recover(client, base: str, run_id: str, got: dict, *, force: bool = False) -> dict:
    if not force and not got.get('importShare'):
        return got
    url = got.get('shareUrl', '')
    raw, strategy = fetch(url, run_id)
    current = preview._clean_text(got.get('raw', ''))
    # Sharing can add UI-only suggestions to an already delivered answer.
    mark = re.search(r'(?m)^STUDYEZ_BANK_COMPLETE[ \t]*$', current)
    if mark and (not current[mark.end():].strip() or SUGGESTIONS.fullmatch(current[mark.end():])):
        current = current[:mark.end()].rstrip()
    unchanged = current == raw or bool(got.get('publishedCurrent') and raw in current)
    result = client.call('PUT', f'{base}/bank-shared-response', {
        'raw': got['raw'] if unchanged else raw, 'shareUrl': url, 'expectedRespondedAt': got.get('respondedAt'),
        'expectedRawHash': hashlib.sha256(got.get('raw', '').encode()).hexdigest(),
        'extractionStrategy': strategy,
    })
    if result.get('reused') and got.get('publishedCurrent'):
        return {**got, 'shareUnchanged': True}
    return client.call('GET', f'{base}/bank-response')

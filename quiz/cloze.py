"""Cloze 마크업 정규화.

meddeck-local-app/pdf_to_anki/quality_filter.py 의 cloze 헬퍼만 발췌했다.
원본 모듈은 1400줄이 넘고 LLM 호출을 의존성 주입으로 받고 있어서, 필요한
5개 함수만 여기로 옮겨 이 패키지를 순수하게 유지한다.
"""

from __future__ import annotations

import re

CLOZE_RE = re.compile(r"\{\{\s*c(\d+)\s*::\s*(.*?)(?:::.*?)?\s*\}\}", flags=re.DOTALL)


def normalize_cloze_syntax(text: str) -> str:
    """흔한 cloze 깨짐을 Anki 표준 {{cN::...}}에 가깝게 복구한다."""
    text = str(text or "")

    def repl(m):
        return "{{c%s::%s}}" % (m.group(1), m.group(2).strip())

    # {{ c1 :: answer }} → {{c1::answer}}
    text = re.sub(r"\{\{\s*c(\d+)\s*::\s*([^{}]+?)\s*\}\}", repl, text)
    # {c1::answer} → {{c1::answer}}
    text = re.sub(r"(?<!\{)\{\s*c(\d+)\s*::\s*([^{}]+?)\s*\}(?!\})", repl, text)
    # {{c1:answer}} → {{c1::answer}}
    text = re.sub(r"\{\{\s*c(\d+)\s*:\s*([^:{}][^{}]*?)\s*\}\}", repl, text)
    return text


def cloze_matches(text: str) -> list[tuple[int, str]]:
    text = normalize_cloze_syntax(text)
    return [(int(m.group(1)), m.group(2).strip()) for m in CLOZE_RE.finditer(text)]


def has_cloze_markup(text: str) -> bool:
    return bool(CLOZE_RE.search(normalize_cloze_syntax(str(text or ""))))


def normalize_cloze_to_c1(text: str) -> str:
    """c2/c3를 c1로 통일한다. 한 문항이 여러 Anki 카드로 폭증하는 것을 막는다."""
    text = normalize_cloze_syntax(text)
    return CLOZE_RE.sub(lambda m: "{{c1::%s}}" % m.group(2).strip(), text)


def cloze_has_malformed_markup(text: str) -> bool:
    """cloze처럼 생긴 흔적은 있는데 유효한 cloze가 하나도 없는 경우."""
    text = str(text or "")
    if "c" not in text and "{" not in text:
        return False
    if CLOZE_RE.search(normalize_cloze_syntax(text)):
        return False
    return bool(re.search(r"\{+\s*c\d+\s*:?", text))


def strip_cloze_markup(text: str, keep_answer: bool = True) -> str:
    text = normalize_cloze_syntax(text)
    return CLOZE_RE.sub(r"\2" if keep_answer else " ", str(text or ""))


def blank_cloze_markup(text: str) -> str:
    """{{c1::hidden}} → '[...]' 리터럴 placeholder.

    Anki의 cloze 노트 유형에 의존하지 않고 빈칸을 텍스트에 그대로 구워 넣는다.
    덕분에 모든 문항이 같은 노트 유형 하나를 쓰고, Anki 안에서 cloze ↔ 일반
    문항 전환이 'Change Note Type' 없이 텍스트 편집만으로 끝난다.
    """
    text = normalize_cloze_syntax(text)
    return CLOZE_RE.sub('<span class="cloze-blank">[...]</span>', str(text or ""))


def valid_cloze_text(q: str) -> bool:
    matches = cloze_matches(q)
    return bool(matches) and all(hidden for _, hidden in matches)

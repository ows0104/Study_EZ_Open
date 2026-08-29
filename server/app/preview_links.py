"""예습 제공자와 개인·공개 링크 형식의 단일 검증점."""

from __future__ import annotations

import re


PREVIEW_PROVIDERS = frozenset({"chatgpt", "gemini", "claude"})

_CONVERSATION_PATTERNS = {
    "chatgpt": re.compile(r"https://chatgpt\.com/(?:g/[^/]+/)?c/[A-Za-z0-9_:-]+(?:[/?#].*)?$"),
    "gemini": re.compile(r"https://gemini\.google\.com/app/[A-Za-z0-9_-]+(?:[/?#].*)?$"),
    "claude": re.compile(r"https://claude\.ai/chat/[A-Za-z0-9-]+(?:[/?#].*)?$"),
}

_SHARE_PATTERNS = {
    "chatgpt": re.compile(r"https://chatgpt\.com/share/(?:e/)?[A-Za-z0-9_-]+(?:[/?#].*)?$"),
    "gemini": re.compile(
        r"https://(?:gemini\.google\.com/share|g\.co/gemini/share)/[A-Za-z0-9_-]+(?:[/?#].*)?$"
    ),
    "claude": re.compile(r"https://claude\.ai/share/[A-Za-z0-9-]+(?:[/?#].*)?$"),
}


def provider(value: str) -> str:
    cleaned = value.strip().lower()
    if cleaned not in PREVIEW_PROVIDERS:
        raise ValueError("예습 제공자는 chatgpt, gemini, claude 중 하나여야 합니다.")
    return cleaned


def conversation_url(value: str, selected: str) -> bool:
    return not value or bool(_CONVERSATION_PATTERNS[selected].fullmatch(value.strip()))


def share_url(value: str, selected: str) -> bool:
    return not value or bool(_SHARE_PATTERNS[selected].fullmatch(value.strip()))

"""ID 생성, 파일명 정리, Anki 필드 텍스트 정규화.

meddeck-local-app/pdf_to_anki/card_utils.py 에서 LLM과 무관한 부분만 발췌했다.
stable_int_id는 원본과 같은 시드 규칙을 유지해야 한다 - 바꾸면 기존 덱과 노트
유형/덱 ID가 갈라진다.
"""

from __future__ import annotations

import hashlib
import html
import re


def stable_int_id(text: str, base: int = 2_026_000_000, modulo: int = 1_000_000_000) -> int:
    digest = hashlib.md5(text.encode("utf-8")).hexdigest()
    return base + (int(digest[:8], 16) % modulo)


def safe_filename(text) -> str:
    value = re.sub(r'[\\/*?:"<>|\s]+', "_", str(text)).strip("_")
    return value or "untitled"


def safe_media_prefix(text) -> str:
    """미디어 파일명을 ASCII로 강제한다. Anki collection.media에 한글 파일명이
    섞이면 동기화/백업에서 깨지는 경우가 있어 원본 파이프라인도 이렇게 한다."""
    base = re.sub(r"[^0-9A-Za-z]+", "_", str(text)).strip("_").lower()
    base = base[:36] if base else "pdf"
    digest = hashlib.md5(str(text).encode("utf-8")).hexdigest()[:8]
    return f"{base}_{digest}"


def escape_field(value) -> str:
    """Anki 필드용 HTML 이스케이프. {, }, : 는 건드리지 않으므로 cloze 마크업이
    살아남는다 (blank_cloze_markup을 이 뒤에 적용해야 <span>이 진짜 HTML이 된다)."""
    return html.escape(str(value), quote=False)


def normalize_display_newlines(value) -> str:
    """모델이 한 줄로 뱉은 목록을 Anki에서 읽을 수 있는 줄바꿈으로 편다."""
    text = html.unescape(str(value or ""))
    text = re.sub(r"(?i)<\s*br\s*/?\s*>", "\n", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\\n", "\n")
    text = re.sub(r"(?<!\n)\s+(-\s+)(?=[^:\n]{1,40}:)", r"\n\1", text)
    text = re.sub(r"(?<!\n)\s+(-\s+)(?=[A-Z][A-Za-z0-9 /()\-]{0,50}(?:\s*\(|:))", r"\n\1", text)
    text = re.sub(r"([:：])\s+(-\s+)", r"\1\n\2", text)
    text = re.sub(r"\n[ \t]+(?=[\-•*]|\d+\.)", "\n", text)
    text = re.sub(r"(?<!^)(?<!\n)\s+(?=(?:[2-9]|1[0-9])\.\s+)", "\n", text)
    text = re.sub(r"[ \t]*;[ \t]*(?=[\-•*]\s+)", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


_LECTURE_CODE_RE = re.compile(r"\[\s*(\d{6})[_\s-]*(\d{2})\s*\]")


def lecture_id_from_stem(stem: str) -> str:
    """'[250813_02]세포의 손상...' → '250813_02'. 대괄호 코드가 없으면 파일명 슬러그."""
    m = _LECTURE_CODE_RE.search(str(stem))
    if m:
        return f"{m.group(1)}_{m.group(2)}"
    return safe_filename(stem)[:48]


def lecture_title_from_stem(stem: str) -> str:
    """'[250813_02]세포의 손상 및 적응(1)(고지원)_장원영v1' → '세포의 손상 및 적응(1)'.

    뒤쪽의 (교수명)_정리자vN 꼬리를 떼어낸다. 덱 이름에 쓰인다.
    """
    title = _LECTURE_CODE_RE.sub("", str(stem)).strip()
    title = re.sub(r"_[^_]*v\d+\s*\.?$", "", title).strip()
    title = re.sub(r"_[^_()]*$", "", title).strip()
    title = re.sub(r"\([^()]{2,8}\)\s*$", "", title).strip()
    return title or str(stem)


def norm_for_compare(text: str) -> str:
    """중복 비교용 정규화: 소문자, 태그·구두점 제거, 공백 압축."""
    from quiz.cloze import strip_cloze_markup

    s = html.unescape(str(text or "")).lower()
    s = strip_cloze_markup(s, keep_answer=True)
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"[^0-9a-z가-힣\s]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def tokens(text: str) -> set[str]:
    return {t for t in norm_for_compare(text).split() if len(t) > 1}

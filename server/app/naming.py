"""이름 다루기. 시간표와 필기가 같은 강의를 서로 다르게 부르므로 필요하다.

`studyez/filenames.py`의 `canonical`·`normalize_stem`과 **같은 규칙**이다. 서버는
따로 배포되고 `studyez/`는 다른 갈래라서 import 대신 규칙을 복제했다. 한쪽을
고치면 다른 쪽도 고쳐야 한다.
"""

from __future__ import annotations

import re
import unicodedata

_JUNK_RE = re.compile(r"[^0-9a-z가-힣]+")

# 로마자 순번. NFKC가 "Ⅱ"를 "II"로 펴므로 긴 것부터 바꾼다 — 짧은 것부터 하면
# "11"이 되어 "2"와 안 맞는다. 경계에 \b를 쓰면 안 된다: 파이썬은 한글도 단어
# 문자로 보기 때문에 "기능Ⅱ"의 "능"과 "i" 사이에 경계가 없다.
_ROMAN = [
    (re.compile(r"(?<![a-z])viii(?![a-z])"), "8"),
    (re.compile(r"(?<![a-z])vii(?![a-z])"), "7"),
    (re.compile(r"(?<![a-z])vi(?![a-z])"), "6"),
    (re.compile(r"(?<![a-z])iv(?![a-z])"), "4"),
    (re.compile(r"(?<![a-z])iii(?![a-z])"), "3"),
    (re.compile(r"(?<![a-z])ii(?![a-z])"), "2"),
]

# 시간표 제목 꼬리의 강의 번호. "감염과 면역 12" → "감염과 면역".
_TRAILING_NUMBER_RE = re.compile(r"[\s\-–—]*\d{1,3}\s*$")

# 슬라이드 렌더 파일명. `quiz/render.py`가 `{prefix}_s{번호:03d}.png`로 쓴다.
_SLIDE_NO_RE = re.compile(r"_s(\d{1,4})\.png$", re.IGNORECASE)


def nfc(value: str) -> str:
    """Synology 파일명 일부가 NFD(자모 분해)다.

    화면에는 똑같이 보이지만 `[가-힣]` 정규식이 통째로 실패하고, 무엇보다 DB에서
    같은 과목이 두 행으로 갈라진다. 바깥에서 들어오는 문자열은 여기를 지난다.
    """
    return unicodedata.normalize("NFC", value or "").strip()


def canonical(text: str) -> str:
    """비교 가능한 형태로 편다. 로마자 치환이 순번 추출보다 늦으면 안 된다."""
    text = unicodedata.normalize("NFKC", text or "").casefold()
    for pattern, digit in _ROMAN:
        text = pattern.sub(digit, text)
    return text


def normalize_stem(text: str) -> str:
    """비교용 이름. 숫자를 통째로 지우지는 않는다 — CD4/CD8처럼 숫자가 뜻인 이름이 있다."""
    return _JUNK_RE.sub("", canonical(text))


def slot_from_time(start_time: str) -> int | None:
    """시작 시각 → 교시. 09:00부터 세고 04가 점심이라 교시는 시각 - 8이다.

    정각이 아닌 칸(09:40 시작하는 의료윤리 세션 등)은 교시 개념이 없으므로
    비운다. 캘린더는 시각으로 그리므로 이것이 없어도 자리는 잡힌다.
    """
    if not start_time or ":" not in start_time:
        return None
    hour_text, minute_text = start_time.split(":", 1)
    if minute_text.strip() != "00":
        return None
    try:
        slot = int(hour_text) - 8
    except ValueError:
        return None
    return slot if 1 <= slot <= 15 else None


def course_from_title(title: str) -> str:
    """시간표 제목에서 과목을 뽑는다. "감염과 면역 12" → "감염과 면역".

    시간표는 과목 이름 뒤에 회차를 붙여 쓴다. 실제 강의 제목은 `details`의
    첫 줄에 있다.
    """
    return _TRAILING_NUMBER_RE.sub("", nfc(title)).strip()


def slide_no_from_filename(filename: str) -> int | None:
    match = _SLIDE_NO_RE.search(filename or "")
    return int(match.group(1)) if match else None


def object_key(subject: str, run_id: str, kind: str, filename: str) -> str:
    """R2 키. 과목이 앞에 오는 이유는 `run_id`가 과목을 포함하지 않기 때문이다."""
    return f"lectures/{nfc(subject)}/{run_id}/{kind}/{nfc(filename)}"

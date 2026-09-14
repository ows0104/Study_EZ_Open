"""이름 다루기. 시간표와 필기가 같은 강의를 서로 다르게 부르므로 필요하다.

`runner/filenames.py`의 `canonical`·`normalize_stem`과 **같은 규칙**이다. 서버는
따로 배포되고 `runner/`는 다른 갈래라서 import 대신 규칙을 복제했다. 한쪽을
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


# 필기 파일명 꼬리의 판 번호. "_최나예v1" · "_고명재 v2" · "_오서연_v3" · "_이채현v.1".
#
# `runner/filenames.py`의 `_AUTHOR_RE`와 **같은 규칙**이다(이 파일 첫머리 참고).
# 필기자 이름은 한글 2~4자이고 판 번호는 없을 수도 있다 — 없으면 v1이다.
_AUTHOR_RE = re.compile(r"_\s*([가-힣]{2,4})\s*_?\s*[vV]?\s*\.?\s*(\d+)?\s*\.*\s*$")


def version_from_filename(path: str) -> int | None:
    """덱을 무엇으로 만들었는지. **모르면 `None`이다.**

    파이프라인이 `run.meta.json`에 적어 둔 원본 PDF 이름에서 판 번호를 읽는다.
    이름이 규칙을 안 따르면 0이나 1로 메우지 않고 모른다고 말한다 — 메우면
    「같은 판으로 만들었다」로 읽히고, 그것은 덱을 다시 만들 이유를 지운다.
    """
    stem = nfc(path).replace("\\", "/").rsplit("/", 1)[-1].rsplit(".", 1)[0]
    tail = _AUTHOR_RE.search(stem)
    if not tail:
        return None
    return int(tail.group(2)) if tail.group(2) else 1


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


# 「(분반) A: 김태민」 꼴. 사람 이름이 붙는 자리라 소제목으로 오해하면 안 된다.
_SECTION_RE = re.compile(r"^\(?[^)]*분반[^)]*\)?\s*[A-Za-z]\s*:")

# 여러 줄로 접힌 `details`를 한 줄로 붙일 때 쓰는 사이 공백.
_SPACES_RE = re.compile(r"\s+")


def _flat(text: str) -> str:
    return _SPACES_RE.sub(" ", nfc(text))


def _detail_lines(details: str) -> list[str]:
    return [line for line in (_flat(raw) for raw in (details or "").split("\n")) if line]


def professor_names(rows: list[tuple[str, str]]) -> frozenset[str]:
    """시간표 전체에서 사람 이름을 모은다. `(details, professor)` 쌍을 받는다.

    `strip_lead_topic`이 「이 줄은 사람 이름인가」를 물어볼 데다. 규칙으로 가를 수
    없어서 **시간표 자신에게 물어본다** — `unfold_title`이 작년 제목에 물어보는 것과
    같은 수법이다. 소제목과 이름이 글자로는 안 갈리기 때문이다: `연충란`·`천식`·
    `선충류`는 `고정민`·`문장섭`과 길이도 꼴도 같다.

    이름이라고 볼 수 있는 자리는 셋이다.

        담당이 쉼표 목록이면 **앞 토큰 말고** 나머지    오염은 맨 앞에만 붙는다
        담당이 `details`의 한 줄과 통째로 같으면 그 줄  접히지 않은 깨끗한 칸
        앞 토큰이 두 낱말이면 그 **끝 낱말**            `혈관염 박진균`의 `박진균`

    셋째가 없으면 2026 시간표에서 두 칸을 못 고친다(`감염과 면역 41`·`57`). 그
    칸에만 나오는 교수는 다른 데서 이름을 배울 데가 없다.
    """
    names: set[str] = set()
    for details, professor in rows:
        flat = _flat(professor)
        if not flat:
            continue
        tokens = [token for token in (t.strip() for t in flat.split(",")) if token]
        if not tokens:
            continue
        names.update(tokens[1:])
        if len(tokens) == 1 and flat in _detail_lines(details):
            names.add(flat)
        words = tokens[0].split(" ")
        if len(words) > 1:
            names.add(words[-1])
    return frozenset(names)


def strip_lead_topic(details: str, professor: str, names: frozenset[str]) -> str:
    """담당 칸 앞에 붙어 온 소제목을 떼어 낸다.

    시간표 JSON은 강의 PDF에서 사람 손을 거쳐 나오는데, `details`의 어디까지가
    제목이고 어디부터가 담당인지가 칸마다 흔들린다. 2026 시간표 369칸 중 **14칸**이
    소제목을 담당 칸에 끌고 들어왔다.

        details   "(MDL)⏎연충란⏎최민호, 신은희, 여선주,⏎송현범, 김주현"
        professor "연충란 최민호, 신은희, 여선주, 송현범, 김주현"   ← `연충란`이 넘어왔다

    그러면 캘린더에서 그 칸의 제목이 사라진다. 화면은 담당에 든 줄을 제목에서
    빼는데(`web/src/calendar/entries.ts`), 소제목이 담당에 들어 있으니 같이 빠진다.
    2026-08-31 실습이 그렇게 제목 없이 「담당: 연충란 최민호, …」로 떴다.

    떼는 조건은 셋 다 맞을 때다 — **의심스러우면 그냥 둔다.**

        ① 담당이 `details`의 뒷줄들을 그대로 이어 붙인 것이고, 그 앞에 줄이 더 있다
        ② 그 첫 줄이 쉼표도 `(분반)`도 없고 `names`에 없다
        ③ 남는 쪽의 첫 토큰은 `names`에 있거나 `(분반)` 꼴이다

    ②가 없으면 이름 여러 줄을 접어 놓은 칸(`고정민⏎문장섭⏎김만진`)의 첫 교수를
    지운다. ③이 없으면 이름을 하나도 못 배운 칸에서 담당이 통째로 빈다. 2026
    시간표에 이 규칙을 돌리면 **고칠 14칸을 고치고 나머지 355칸은 안 건드린다.**
    """
    lines = _detail_lines(details)
    flat = _flat(professor)
    if not flat or len(lines) < 2:
        return flat
    for index in range(len(lines) - 1):
        if " ".join(lines[index:]) != flat:
            continue
        lead = lines[index]
        if "," in lead or _SECTION_RE.match(lead) or lead in names:
            return flat
        rest = " ".join(lines[index + 1:])
        if _SECTION_RE.match(rest) or rest.split(",")[0].strip() in names:
            return rest
        return flat
    return flat


def slide_no_from_filename(filename: str) -> int | None:
    match = _SLIDE_NO_RE.search(filename or "")
    return int(match.group(1)) if match else None


def object_key(subject: str, run_id: str, kind: str, filename: str) -> str:
    """R2 키. 과목이 앞에 오는 이유는 `run_id`가 과목을 포함하지 않기 때문이다."""
    return f"lectures/{nfc(subject)}/{run_id}/{kind}/{nfc(filename)}"

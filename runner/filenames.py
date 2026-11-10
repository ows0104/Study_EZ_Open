"""필기 파일명 한 줄에서 강의를 읽어낸다.

    [260813_03]조직 재생 및 수복(2)(김혜령)_최나예v1.pdf
     └──┬──┘└┬┘└──────┬──────┘└─┬──┘ └─┬─┘└┬┘
       날짜  슬롯      제목       교수   필기자 판

## 괄호는 두 가지로 쓰인다

숫자면 **강의 순번**이고 한글이면 **교수 이름**이다. 둘을 같이 지우면
"조직 재생 및 수복(1)"과 "(2)"가 같은 문자열이 되어 서로 다른 강의가 한 편으로
뭉개진다. 실제로 병리학 2026 15편이 10개 키로 붙었다.

감염과 면역은 순번을 괄호 밖에 쓰고("선천면역 1"), 병리학은 괄호 안에 쓴다.
과목마다 다르므로 양쪽을 다 순번으로 읽는다.

## 같은 강의의 판이 여러 개 온다

    [260812_02] ... _조의진v1.pdf   8/13 10:37
    [260812_02] ... _조의진v3.pdf   8/13 21:51

같은 `lecture_key`에 v1과 v3이 공존한다. `latest_versions()`가 최신 판만 남긴다.
"""

from __future__ import annotations

import re
import hashlib
import os
import json
import unicodedata
from dataclasses import dataclass
from pathlib import Path

# "[260813_03]" - 날짜(YYMMDD)와 교시 슬롯.
#
# 두 가지 변종을 같이 받는다. "[260401_01~03]"은 세 교시 연강이고,
# "[250523_03}"은 닫는 괄호 오타다. 둘 다 실물에 있으며, 안 받아 주면 그 강의가
# 통째로 목록에서 사라진다.
_BRACKET_RE = re.compile(
    r"^\s*[\[(]\s*(\d{2})(\d{2})(\d{2})\s*_\s*(\d{1,2})"
    r"(?:\s*[~\-–—]\s*(\d{1,2}))?\s*[\]\})）]")

# 꼬리의 "_최나예v1", "_고명재 v2", "_오서연_v3", "_박지민", "_김정빈v2.",
# "_이채현v.1", "_송 현 v1" 을 모두 받는다. 필기자 이름은 한글 2~4자이고(글자 사이
# 띄어쓰기 허용) 판 번호는 없을 수도 있다. 이름을 못 떼면 제목이 오염되어 주제 별칭이
# 빗나가고, 다른 강의와 run 키가 겹쳐 둘 다 해시 run이 새로 선다(2026-11-10 렙토스피라).
_AUTHOR_RE = re.compile(r"_\s*([가-힣](?:\s?[가-힣]){1,3})\s*_?\s*[vV]?\s*\.?\s*(\d+)?\s*\.*\s*$")

# Synology가 같은 파일을 두 기기에서 고쳤을 때 남기는 사본.
# "_박준원v2_DERIAZ_7-09-222924-2026_Conflict.pdf" 같은 이름이 되어 제목이 오염된다.
_CONFLICT_RE = re.compile(r"(conflict|conflicted copy|충돌)", re.IGNORECASE)

# 괄호 안이 순수 숫자면 강의 순번, 한글로만 되어 있으면 교수 이름.
_PAREN_RE = re.compile(r"[(（]\s*([^)）]*?)\s*[)）]")
_ONLY_DIGITS_RE = re.compile(r"^\d{1,2}$")
_ONLY_HANGUL_RE = re.compile(r"^[가-힣\s,·]+$")

# 괄호 밖 순번: "선천면역 1", "실습 1-면역조직화학염색 실습", "CBL 2".
_TRAILING_SEQ_RE = re.compile(r"(?:실습|cbl|강의)?\s*(\d{1,2})\s*(?:[-–—]|$)")

# 로마자 순번. NFKC가 "Ⅱ"를 "II"로 펴므로 긴 것부터 바꾼다 - 짧은 것부터 하면
# "11"이 되어 "2"와 안 맞는다.
#
# 경계에 \b를 쓰면 안 된다. 파이썬은 한글도 단어 문자로 보기 때문에 "기능Ⅱ"의
# "능"과 "i" 사이에 경계가 없어 \bii\b가 통째로 실패한다. 실제로 조직학
# "상피의 구조와 기능Ⅱ"가 여기서 순번을 잃고 "기능1"짜리 1강과 경쟁했다.
_ROMAN: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(?<![a-z0-9])iii(?![a-z0-9])"), "3"),
    (re.compile(r"(?<![a-z0-9])ii(?![a-z0-9])"), "2"),
    (re.compile(r"(?<![a-z0-9])i(?![a-z0-9])"), "1"),
]

_JUNK_RE = re.compile(r"[^0-9a-z가-힣]+")


def _to_arabic(text: str) -> str:
    """로마자 순번을 아라비아 숫자로. NFKC·casefold를 마친 문자열에만 쓴다."""
    for pattern, digit in _ROMAN:
        text = pattern.sub(digit, text)
    return text


@dataclass(frozen=True)
class LectureFile:
    """필기 PDF 한 개."""

    path: Path
    key: str          # "260813_03" - 연도 안에서 이 강의를 가리키는 유일한 이름
    date: str         # "2026-08-13"
    slot: int         # 3 (교시 슬롯. 09:00부터 세고 04는 점심)
    slot_end: int     # 3. 연강이면 마지막 교시 ("[260401_01~03]" → 3)
    start_time: str   # "11:00"
    title: str        # "조직 재생 및 수복(2)"
    stem: str         # "조직재생및수복" - 순번·교수를 뗀 비교용 이름
    seq: int | None   # 2 - 같은 제목의 몇 번째 강의인가
    professors: tuple[str, ...]
    author: str
    version: int

    @property
    def year(self) -> int:
        return int(self.date[:4])

    @property
    def uid(self) -> str:
        """이 강의를 가리키는 진짜 이름.

        `key`만으로는 부족하다. 선택형 과목은 한 교시에 여러 강의가 동시에 열려
        같은 `260303_02`에 서로 다른 강의 세 편이 들어온다. 어간까지 봐야 판
        중복(같은 강의의 v1/v3)과 병렬 강의(다른 강의)가 갈린다.

        괄호까지 넣는 이유는 한글 괄호가 늘 교수 이름은 아니기 때문이다.
        "실습 3(연골과 뼈)"와 "실습 3(근육)"은 둘 다 이름으로 잘못 읽히는데,
        여기 넣어 두면 잘못 읽어도 두 강의가 한 편으로 뭉개지지는 않는다.
        """
        return f"{self.key}#{self.stem}#{'·'.join(sorted(self.professors))}"


def slot_to_time(slot: int) -> str | None:
    """교시 슬롯 → 시작 시각. 09:00부터 세고 04가 점심이라 시각은 slot + 8시다.

    meddeck의 `lectureSlotFromFilename`과 같은 규칙이다(2026 파일 16/16 검증).
    """
    hour = slot + 8
    return f"{hour:02d}:00" if 8 <= hour <= 23 else None


def _split_parens(text: str) -> tuple[str, int | None, tuple[str, ...]]:
    """제목에서 순번 괄호와 교수 괄호를 갈라낸다.

    반환: (괄호를 뗀 제목, 첫 순번, 교수 이름들)
    """
    seq: int | None = None
    professors: list[str] = []

    def replace(match: re.Match[str]) -> str:
        nonlocal seq
        inner = match.group(1).strip()
        if _ONLY_DIGITS_RE.match(inner):
            if seq is None:
                seq = int(inner)
            return " "          # 순번은 seq로 따로 들고, 제목에서는 뺀다
        if _ONLY_HANGUL_RE.match(inner) and len(inner.replace(" ", "")) >= 2:
            professors.append(inner)
            return " "
        return " "              # 그 밖의 괄호(영문 약어 등)도 비교에서는 뺀다

    stripped = _PAREN_RE.sub(replace, text)
    return stripped, seq, tuple(professors)


def _split_professor_names(groups: tuple[str, ...]) -> tuple[str, ...]:
    """"(문경철김혜령)" 처럼 두 명이 붙어 오는 경우를 이름 단위로 나눈다."""
    names: list[str] = []
    for group in groups:
        for chunk in re.split(r"[\s,·]+", group):
            chunk = chunk.strip()
            if not chunk:
                continue
            # 한국 이름은 대개 3자다. 6자면 두 명, 9자면 세 명으로 본다.
            if len(chunk) in (6, 9) and len(chunk) % 3 == 0:
                names.extend(chunk[i:i + 3] for i in range(0, len(chunk), 3))
            else:
                names.append(chunk)
    return tuple(dict.fromkeys(names))


def canonical(text: str) -> str:
    """제목을 비교 가능한 형태로 편다. 순번을 읽기 **전에** 거쳐야 한다.

    로마자 치환이 순번 추출보다 늦으면 "기능Ⅱ"의 순번을 영영 못 읽는다.
    """
    return _to_arabic(unicodedata.normalize("NFKC", text).casefold())


def normalize_stem(text: str) -> str:
    """비교용 이름. 순번은 이미 빠져 나갔지만 숫자를 통째로 지우지는 않는다 -
    CD4/CD8, TLR3/4처럼 숫자가 뜻인 이름이 있다.
    """
    return _JUNK_RE.sub("", canonical(text))


def parse(path: str | Path) -> LectureFile | None:
    """파일명 하나를 읽는다. 대괄호가 없으면 강의 필기가 아니라고 보고 건너뛴다."""
    path = Path(path)

    # Synology에 NFD(자모 분해)로 저장된 파일명이 섞여 있다. 화면에는 똑같이
    # 보이지만 "한다연"이 자모 7개로 흩어져 [가-힣] 정규식이 통째로 실패한다.
    # 여기서 한 번 모아 두지 않으면 뒤의 모든 규칙이 조용히 빗나간다.
    raw = unicodedata.normalize("NFC", path.stem)

    bracket = _BRACKET_RE.match(raw)
    if not bracket:
        return None
    yy, mm, dd, slot_text, slot_end_text = bracket.groups()
    slot = int(slot_text)
    slot_end = int(slot_end_text) if slot_end_text else slot
    start_time = slot_to_time(slot)
    if start_time is None:
        return None

    rest = raw[bracket.end():].strip()

    author, version = "", 1
    tail = _AUTHOR_RE.search(rest)
    if tail:
        author = re.sub(r"\s", "", tail.group(1))
        version = int(tail.group(2)) if tail.group(2) else 1
        rest = rest[:tail.start()].strip()

    title = rest.strip(" _-–—.")

    # 로마자를 먼저 편 뒤에 순번을 읽는다. 순서가 바뀌면 "기능Ⅱ"가 순번을 잃는다.
    stripped, seq, professor_groups = _split_parens(canonical(title))

    if seq is None:
        trailing = _TRAILING_SEQ_RE.search(stripped)
        if trailing:
            seq = int(trailing.group(1))

    key = f"{yy}{mm}{dd}_{slot:02d}"
    # A revised schedule must not reuse another lecture's existing storage key.
    # Only explicitly reviewed date/slot + full-topic aliases can change a key.
    aliases_path = Path(__file__).resolve().parents[1] / "data/timetable/identities/2026-2-notes.json"
    if key.startswith("2611") and aliases_path.exists():
        aliases = json.loads(aliases_path.read_text(encoding="utf-8"))
        topic = stripped
        for prefix in ("미생물학)", "감염학)"):
            topic = topic.removeprefix(prefix).strip()
        stable = aliases.get(key, {}).get(_JUNK_RE.sub("", topic))
        if stable is not None:
            if not isinstance(stable, str) or not re.fullmatch(r"\d{6}_\d{2}", stable):
                raise ValueError("Invalid timetable note identity")
            key = stable

    return LectureFile(
        path=path,
        key=key,
        date=f"20{yy}-{mm}-{dd}",
        slot=slot,
        slot_end=max(slot, slot_end),
        start_time=start_time,
        title=title,
        stem=_JUNK_RE.sub("", stripped),
        seq=seq,
        professors=_split_professor_names(professor_groups),
        author=author,
        version=version,
    )


# 파이프라인이 손대지 않는 과목.
#
# 선택교과는 **학생마다 듣는 과목이 다르고 시험과 무관하다.** 강의록 연결도,
# 예습도, 복습 덱도 만들지 않는다. 만들어 봐야 대부분의 학생에게 소음이고,
# 캘린더에 띄우면 남의 시간표가 내 화면에 섞인다.
#
# 폴더 구조도 다르다 - `{과목}/필기/{연도}/`가 아니라 `선택교과/{연도}/{과목}/`라
# 지금 스캐너에는 어차피 안 잡히지만, 구조가 바뀌어도 안 딸려 들어오게 여기
# 적어 둔다.
EXCLUDED_SUBJECTS = frozenset({"선택교과"})

# 이름이 이걸로 시작하면 전부 제외. 인간사회의료는 한 교시에 강의가 셋씩 열려
# 학생마다 듣는 것이 다르다 - 선택교과와 성격이 같다. `1`, `2`처럼 번호가 붙어
# 해마다 늘어나므로 이름을 하나하나 적지 않고 앞부분으로 가린다.
EXCLUDED_PREFIXES = ("인간사회의료",)


def is_excluded(subject: str) -> bool:
    return subject in EXCLUDED_SUBJECTS or subject.startswith(EXCLUDED_PREFIXES)


def discover_subjects(root: str | Path, year: str) -> list[str]:
    """그 연도의 필기가 있는 과목. 제외 대상은 빼고 돌려준다.

    `#`이나 `_`로 시작하는 폴더도 뺀다 - "# 교과서", "# 족보 오류토의"처럼
    과목이 아닌 것들이다.
    """
    root = Path(root)
    if not root.is_dir():
        return []
    return sorted(
        d.name for d in root.iterdir()
        if d.is_dir()
        and not is_excluded(d.name)
        and not d.name.startswith(("#", "_", "."))
        and (d / "필기" / year).is_dir()
    )


# 같은 파일을 한 번 더 받았을 때 꼬리에 붙는 `(1)`·`(2)`.
_COPY_SUFFIX_RE = re.compile(r"^(?P<origin>.+?)\s*\(\d+\)$")


def _duplicate_of(stem: str, stems: set[str]) -> bool:
    """이 이름이 **같은 폴더에 있는 다른 파일의 사본**인가.

    실물에서 나왔다. `[260819_03]…_한태희v3.pdf` 옆에 `…_한태희v3 (1).pdf`가
    같이 있었는데, `(1)`이 제목어간에 섞여 들어가 `uid`가 갈리고 **한 강의가 두
    편으로 서 버렸다**. 그러면 `assign_run_ids`가 둘 다 해시를 붙여 `260819_03`이
    아무 데도 없게 되고, 그 강의의 덱은 만들어져도 붙을 자리를 못 찾는다.

    **원본이 실제로 옆에 있을 때만 사본으로 본다.** 꼬리의 `(N)`만 보고 자르면
    `실습 3(연골과 뼈)`처럼 괄호가 뜻인 이름을 잘못 접는다 — 그 둘은 서로 다른
    강의이고, 한 편으로 뭉개는 것이 이 함수가 막으려는 바로 그 사고다.
    """
    match = _COPY_SUFFIX_RE.match(stem)
    return bool(match) and match.group("origin") in stems


@dataclass
class Scan:
    """폴더 하나를 읽은 결과. 빠진 파일은 반드시 이유와 함께 남긴다."""

    files: list[LectureFile]
    conflicts: list[Path]       # Synology 충돌 사본 — 제목이 오염돼 있다
    misfiled: list[LectureFile]  # 파일명 연도와 폴더 연도가 다르다
    unparsed: list[Path]        # 대괄호가 없어 강의로 읽히지 않는다


def scan(folder: str | Path, expect_year: str | None = None) -> Scan:
    """폴더 하나의 PDF를 전부 읽는다.

    읽히지 않은 파일을 조용히 버리지 않는다. 실제로 2026 폴더에 2025 파일이
    한 편 섞여 있었고, 그게 작년 짝을 먼저 차지해서 진짜 올해 강의가 짝을
    잃었다. 세어 보지 않으면 드러나지 않는 종류의 실패다.
    """
    folder = Path(folder)
    result = Scan(files=[], conflicts=[], misfiled=[], unparsed=[])
    if not folder.is_dir():
        return result

    paths = []
    boundary = folder.resolve()
    excluded = {'archive', 'archives', 'backup', 'backups', '보관', '보관본', '백업',
                'work', 'tmp', 'runs', 'generated', 'out'}
    def fail(error):
        raise error
    for current, dirs, names in os.walk(folder, followlinks=False, onerror=fail):
        parent = Path(current)
        dirs[:] = sorted(d for d in dirs if not d.startswith(('.', '_', '#'))
                         and d.casefold() not in excluded
                         and not (parent / d).is_symlink() and not (parent / d).is_junction())
        for name in names:
            path = parent / name
            if path.suffix.lower() == '.pdf' and not path.is_symlink() and path.resolve().is_relative_to(boundary):
                paths.append(path)
    paths.sort()
    stems_by_parent = {}
    for path in paths:
        stems_by_parent.setdefault(path.parent, set()).add(path.stem)
    for path in paths:
        if _CONFLICT_RE.search(path.stem):
            result.conflicts.append(path)
            continue
        if _duplicate_of(path.stem, stems_by_parent[path.parent]):
            result.conflicts.append(path)
            continue
        item = parse(path)
        if item is None:
            result.unparsed.append(path)
            continue
        if expect_year and item.date[:4] != expect_year:
            result.misfiled.append(item)
            continue
        result.files.append(item)
    return result


def assign_run_ids(files: list[LectureFile]) -> dict[str, str]:
    """Shared run identity for generation and read-only desktop readiness."""
    by_key: dict[str, list[LectureFile]] = {}
    for item in files:
        by_key.setdefault(item.key, []).append(item)
    run_ids = {}
    for key, group in by_key.items():
        if len(group) == 1:
            run_ids[group[0].uid] = key
        else:
            for item in group:
                digest = hashlib.md5(item.uid.encode('utf-8')).hexdigest()[:4]
                run_ids[item.uid] = f'{key}-{digest}'
    return run_ids


def latest_versions(files: list[LectureFile]) -> list[LectureFile]:
    """같은 강의의 여러 판 중 최신만 남긴다.

    v1으로 이미 덱을 만든 뒤 v3이 올라오는 일이 실제로 있다. 무엇이 최신인지는
    여기 한 곳에서만 정한다.

    묶는 기준은 `key`가 아니라 `uid`다 - `key`로 묶으면 한 교시에 나란히 열린
    다른 강의들이 판 중복으로 오인되어 조용히 버려진다.
    """
    best: dict[str, LectureFile] = {}
    for item in files:
        current = best.get(item.uid)
        if current is None or item.version > current.version:
            best[item.uid] = item
    return sorted(best.values(), key=lambda f: (f.date, f.slot, f.stem))


def superseded(files: list[LectureFile]) -> list[tuple[LectureFile, LectureFile]]:
    """(밀려난 판, 최신 판) 목록. 이미 만든 덱을 다시 만들지 판단할 때 쓴다."""
    latest = {f.uid: f for f in latest_versions(files)}
    return [(f, latest[f.uid]) for f in files if latest[f.uid] is not f]


def parallel_lectures(files: list[LectureFile]) -> dict[str, list[LectureFile]]:
    """한 교시에 둘 이상 열린 강의. 선택형 과목에서 정상이며, 버리면 안 된다."""
    by_key: dict[str, list[LectureFile]] = {}
    for item in latest_versions(files):
        by_key.setdefault(item.key, []).append(item)
    return {key: group for key, group in by_key.items() if len(group) > 1}

"""프롬프트를 파트로 나눠 쓰는 일과, 파일명에서 강의를 알아보는 일.

여기 있는 것은 전부 **목적 중립**이다 — 토큰 예산, Read 도구의 상한, 제목 대조.
어떤 카드를 좋은 카드로 볼 것인가는 여기 없다. 그것은 각 파이프라인의 `assemble` 소관이다.

복습 덱(`quizgen.assemble`)과 예습 덱(`quizgen.prequiz.assemble`)이 함께 쓴다.
한쪽의 철학이 이 파일로 새어 들어오면 갈라 놓은 의미가 없다.
"""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

from .textutil import char_ngrams, containment, jaccard

READ_PAGE_LIMIT = 20          # Read 도구의 PDF 1회 상한
READ_TOKEN_CAP = 25_000       # Read 도구의 1회 토큰 상한
READ_TOKEN_BUDGET = 18_000    # 여유를 둔 파트당 목표치

# 실측 보정: 한글 25,315자(한글 7,825 / 기타 17,490) 묶음이 27,898토큰이었다.
# 한글은 음절당 약 2토큰, 나머지는 자당 약 0.7토큰으로 잡으면 그 값에 맞는다.
TOK_HANGUL, TOK_OTHER = 2.0, 0.7


# ── 토큰 예산 ──────────────────────────────────────────────────────
def estimate_tokens(text: str) -> int:
    han = len(re.findall(r"[가-힣]", text))
    return int(han * TOK_HANGUL + (len(text) - han) * TOK_OTHER)


def split_oversized(section: str, budget: int) -> list[str]:
    """한 덩어리가 예산을 넘으면 `## ` 경계에서 쪼갠다."""
    if estimate_tokens(section) <= budget:
        return [section]
    blocks, cur = [], []
    for block in re.split(r"(?=^## )", section, flags=re.M):
        if not block:
            continue
        if cur and estimate_tokens("".join(cur + [block])) > budget:
            blocks.append("".join(cur))
            cur = [block]
        else:
            cur.append(block)
    if cur:
        blocks.append("".join(cur))
    return blocks


def pack_parts(sections: list[str], budget: int) -> list[str]:
    """섹션들을 예산 안에 채워 파트로 묶는다. 섹션 경계는 지킨다."""
    chunks = [c for s in sections for c in split_oversized(s, budget)]
    parts, cur = [], []
    for c in chunks:
        if cur and estimate_tokens("\n\n---\n\n".join(cur + [c])) > budget:
            parts.append("\n\n---\n\n".join(cur))
            cur = [c]
        else:
            cur.append(c)
    if cur:
        parts.append("\n\n---\n\n".join(cur))
    return parts


def write_parts(outdir: Path, stem: str, sections: list[str], *,
                label: str = "파트", manifest: bool = False,
                budget: int = READ_TOKEN_BUDGET) -> list[dict]:
    """섹션들을 `<stem>.md` 또는 `<stem>.1ofN.md` 로 쓰고 파일 목록을 돌려준다.

    Read 는 1회 25k 토큰에서 잘린다. 조용히 잘리느니 파트로 나눠 준다.
    `manifest=True` 면 파트 1이 나머지를 읽으라는 목록을 달고 선다 — 그러지 않으면
    모델이 1편만 읽고 시작한다.

    **먼저 이 stem 의 지난 파일을 지운다.** 파트 수는 실행마다 달라지는데(자료가
    늘거나 줄면 바뀐다) 지우지 않으면 옛 판이 그대로 남고, 그것을 고르는 쪽이 있다.
    `run.prompt_path` 는 `<stem>.md` 를 먼저 보고 없으면 `<stem>.1of*.md` 를 이름순으로
    고르는데, 둘 다 **옛 파일을 새 파일보다 먼저 집는다** — `prompt.plan.md`(1파트)는
    `prompt.plan.1of2.md` 를 이기고, `prompt.cards.1of2.md` 는 `1of3.md` 를 이긴다.

    2026-09-08에 실습 5편을 다시 구웠는데 **넷이 9월 1~4일 프롬프트로 돌았다.**
    그날 붙인 기출 조각이 새 파트에만 있어서, 화면에는 조각이 붙었다고 찍히고
    모델은 그것을 한 글자도 못 봤다. 카드가 멀쩡히 나오므로 아무 검사에도 안 걸린다.
    """
    for old in sorted(outdir.glob(f"{stem}.md")) + sorted(outdir.glob(f"{stem}.*of*.md")):
        old.unlink()
    bodies = pack_parts([s.strip() for s in sections], budget)
    n = len(bodies)
    names = [f"{stem}.md" if n == 1 else f"{stem}.{i + 1}of{n}.md" for i in range(n)]
    if n > 1 and manifest:
        head = ("> **이 프롬프트는 " + str(n) + "개 파트로 나뉘어 있다. 전부 읽어라.**\n>\n"
                + "\n".join(f"> `Read(\"{(outdir / nm).resolve().as_posix()}\")`"
                            for nm in names) + "\n")
        bodies[0] = head + "\n" + bodies[0]
    files = []
    for i, (nm, body) in enumerate(zip(names, bodies, strict=False)):
        text = body if n == 1 else f"<!-- {label} {i + 1}/{n} -->\n\n{body}"
        (outdir / nm).write_text(text.rstrip() + "\n", encoding="utf-8")
        files.append({"name": nm, "chars": len(text), "tokens": estimate_tokens(text)})
    return files


def estimate_pdf_tokens(prep: dict, scale: float = 1.39) -> int:
    """페이지를 이미지로 받을 때의 대략적인 토큰. (긴 변 1568px 상한)"""
    total = 0
    for s in prep["pages"]:
        w, h = (v * scale for v in s["size"])
        if max(w, h) > 1568:
            k = 1568 / max(w, h)
            w, h = w * k, h * k
        total += int(w * h / 750)
    return total


# ── PDF 를 읽히는 지시 ─────────────────────────────────────────────
def _ranges(pages: list[int]) -> list[str]:
    """연속 구간으로 묶어 Read 의 pages 인자 형태로 만든다."""
    out, start, prev = [], None, None
    for p in sorted(pages):
        if start is None:
            start = prev = p
        elif p == prev + 1:
            prev = p
        else:
            out.append(f"{start}" if start == prev else f"{start}-{prev}")
            start = prev = p
    if start is not None:
        out.append(f"{start}" if start == prev else f"{start}-{prev}")
    return out


def needs_clean(prep: dict) -> list[int]:
    """필기에 가려진 것을 사이드카가 복구하지 못한 슬라이드만 고른다.

    가려진 것이 텍스트면 텍스트 레이어가 그대로 있어 사이드카에 이미 실려 있다.
    그림이 가려졌거나 본문 자체가 없는 슬라이드에서만 clean 렌더가 실제로 필요하다.
    """
    out = []
    for s in prep["pages"]:
        cov = s.get("covered_by_annotation") or []
        if not cov:
            continue
        if any(c["kind"] == "figure" for c in cov) or not s["lecture_text"].strip():
            out.append(s["slide"])
    return out


def clean_instructions(clean_pdf: Path, covered: list[int]) -> str:
    """필기가 강의록을 덮은 페이지만 clean 도 읽게 한다.

    전 페이지를 두 벌 넣으면 이미지 비용이 두 배인데 얻는 게 없다.
    실제로 가려진 페이지에서만 원본이 필요하다.
    """
    if not covered:
        return ""
    calls = "\n".join(f'Read("{clean_pdf.as_posix()}", pages="{r}")' for r in _ranges(covered))
    return (f"\n### 이 슬라이드는 필기가 강의록을 덮었다 — {covered}\n\n"
            "위 PDF 에서는 그 부분이 가려져 보이지 않는다. 필기를 걷어낸 판을 함께 본다.\n\n"
            f"```\n{calls}\n```\n\n"
            "**이 판에는 필기가 없다.** 여기서 보이는 것은 전부 강의록이며 근거로 쓸 수 있다.\n")


def read_instructions(pdf: Path, n_pages: int, context_files: list[Path],
                      clean_pdf: Path | None = None, covered: list[int] | None = None,
                      pages: list[int] | None = None) -> str:
    """`pages` 를 주면 그 쪽만 읽힌다 — 판이 갈려 그 자리만 다시 쓰는 경우다.

    전 페이지를 읽히면 새로 만드는 것과 비용이 같아진다. 다만 **갈린 슬라이드만
    보고 카드를 쓰면 앞뒤 문맥을 모른다.** 부르는 쪽이 앞뒤 한 장씩 얹어 준다
    (`revise` 가 그렇게 한다).
    """
    if pages:
        # 이어진 구간이라도 Read 는 한 번에 20쪽까지다. 갈린 자리가 길게 이어지면
        # 조용히 잘리므로 여기서 미리 나눈다.
        capped: list[str] = []
        for r in _ranges(pages):
            lo, hi = (int(v) for v in (r.split("-") if "-" in r else [r, r]))
            while lo <= hi:
                end = min(lo + READ_PAGE_LIMIT - 1, hi)
                capped.append(f"{lo}" if lo == end else f"{lo}-{end}")
                lo = end + 1
        spans = [f'Read("{pdf.as_posix()}", pages="{r}")' for r in capped]
        head = (f"## 먼저 읽을 것\n\n"
                f"이번에 볼 것은 **판이 갈린 자리와 그 앞뒤뿐**이다 (전체 {n_pages}장 중 "
                f"{len(pages)}장). 나머지 슬라이드의 카드는 이미 있고 그대로 둔다.\n\n"
                "```\n" + "\n".join(spans) + "\n```\n\n")
    else:
        spans = []
        for start in range(1, n_pages + 1, READ_PAGE_LIMIT):
            end = min(start + READ_PAGE_LIMIT - 1, n_pages)
            spans.append(f'Read("{pdf.as_posix()}", pages="{start}-{end}")')
        head = ("## 먼저 읽을 것\n\n"
                f"강의 {n_pages}장을 **전부** 본다. Read 는 한 번에 {READ_PAGE_LIMIT}쪽까지만 되므로 "
                f"{len(spans)}회로 나눈다.\n\n```\n" + "\n".join(spans) + "\n```\n\n")
    ctx = [f'Read("{p.resolve().as_posix()}")' for p in context_files]
    return (head +
            "이 PDF 는 필기가 얹힌 원본이다. 각 페이지 하단에 `Slide N` 이 각인돼 있으니 "
            "카드의 `slide_no` 는 그 번호를 쓴다.\n"
            "**텍스트 레이어는 오지 않는다.** 강의록 본문·필기의 정확한 문자열은 "
            "사이드카에 있으니, 용어 철자는 이미지에서 옮겨 적지 말고 사이드카에서 가져와라.\n\n"
            + clean_instructions(clean_pdf, covered or []) +
            "\n이어서 슬라이드 사이드카와 기출 조각을 읽는다. Read 는 1회 25k 토큰에서 잘리므로 "
            f"{len(ctx)}개로 나눠 두었다.\n\n```\n" + "\n".join(ctx) + "\n```\n\n"
            "**이 파일들을 이미 읽었다면 다시 읽지 않아도 된다.**\n")


# ── 파일명에서 강의를 알아본다 ─────────────────────────────────────
# 필기 파일명은 제목 말고도 세 가지를 달고 있다. 그대로 대조하면 잡음이 분모를 불려
# 맞는 조각도 유사도가 주저앉는다 (`병리학 소개` → `병리학 소개: 과거, 현재, 미래` 가 0.21).
NAME_PREFIX = re.compile(r"^\s*\[[^\]]*\]\s*")            # [260820_03]
NAME_WRITER = re.compile(r"_[가-힣]{2,4}[\s_]*v\s*\d+.*$", re.I)   # _황준하v1 · _곽민정_v1
NAME_PROF = re.compile(r"\((?=[^)]*[가-힣])[가-힣]{2,16}\)")        # (김은나) · (문경철김혜령)
RE_PRACTICE = re.compile(r"실\s*습")


def clean_lecture_name(stem: str) -> str:
    """파일명에서 제목만 남긴다. 날짜·교시, 교수 이름, 필기자·판번호를 뗀다.

    `(1)` `(2)` 같은 회차 표시는 남긴다 — 그건 제목의 일부다. 괄호 안이 순한글
    이름꼴일 때만 뗀다. 실제 아카이브 29개 파일의 괄호는 교수 이름 아니면 회차 숫자뿐이다.

    **이 값이 덱 노드의 이름이다.** 족보 대조뿐 아니라 `run.deck_of` 도 이것을 쓴다 —
    작년 필기본으로 만든 예습 덱과 올해 필기본으로 만든 복습 덱이 한 노드로 모이려면
    양쪽에서 같은 문자열이 나와야 하기 때문이다. 아카이브 29개에 걸어 빈 제목은 없다.
    """
    s = unicodedata.normalize("NFC", stem)     # NFD 파일명은 `[가-힣]` 에 안 걸린다
    s = NAME_PREFIX.sub("", s)
    s = NAME_WRITER.sub("", s)
    s = NAME_PROF.sub(" ", s)
    return re.sub(r"\s+", " ", s).strip()


def lecture_of(pdf: Path) -> str:
    """덱 이름의 가운데 마디 기본값 — **파일제목 원문 그대로.**

    날짜·교시·교수·필기자를 떼지 않는다. 손대는 것은 두 가지뿐이다:
    NFC 정규화(아카이브에 NFD 파일명이 섞여 있다)와 `::` 치환(Anki 의 하위덱 구분자).

    그래서 **작년 필기본으로 만든 예습 덱과 올해 필기본으로 만든 복습 덱은 저절로는
    한 노드에 서지 않는다.** 파일명이 해마다 다르기 때문이다. 모으려면 양쪽에
    `--lecture` 로 같은 값을 준다. 한때 `clean_lecture_name` 으로 자동으로 맞췄으나
    29강 중 20강만 일치해 어차피 손이 필요했다 — 조용히 어긋나느니 사람이 정하는 편이 낫다.

    제목 대조(`find_jokbo`)는 지금도 `clean_lecture_name` 을 쓴다 — 거기서는 파일명을
    깎는 것이 덱 정체성과 무관한 **검색 보조**라 성격이 다르다.
    """
    stem = unicodedata.normalize("NFC", pdf.stem).strip()
    return stem.replace("::", "-") or "lecture"


def _score(name: set[str], title: str) -> float:
    """파일명과 조각 제목의 닮은 정도.

    자카드만으로는 길이 차이에 진다. 한쪽이 다른 쪽을 얼마나 담고 있는지도 함께 본다 —
    조각 제목이 더 넓을 때(`유전질환 (1)~(3)` ⊃ `단일유전자질환`)와 더 좁을 때
    (`병리학 소개` ⊂ `병리학 소개: 과거, 현재, 미래`) 가 둘 다 있기 때문이다.
    """
    t = char_ngrams(title)
    if not t or not name:
        return 0.0
    return max(jaccard(name, t), containment(t, name), containment(name, t))


# 사람이 편마다 조각을 지정하는 자리. 판 폴더가 아니라 **과목 폴더**에 둔다 —
# 다시 자르면 판 폴더가 새로 서므로 거기 두면 지정이 조용히 사라진다.
#
#     _materials/<과목>/pins.json     {"261014_02": "유전자 표적 항암 약리", "261002_05": null}
#
# 값은 조각의 제목이나 `lecture_key` 다. `null` 은 「이 편에는 족보가 없다」.
# 2026-09-24 약리학에서 필요해졌다. 족보(2025판)가 항암을 `유전자 표적 항암 약리` ·
# `항암 약리학의 원리` 로 묶는데 올해 시간표는 `알킬화합물/유사분열억제 항암제` ·
# `항대사/항호르몬 항암제` 로 가른다. 제목이 안 겹쳐 앞의 것은 0.20 으로 떨어지고,
# 뒤의 것은 `갑상선 및 부갑상선 호르몬 약리` 에 0.33 으로 **붙는다** — 틀린 조각이 붙은
# 편은 안 붙은 편보다 나쁘다. PBL·CBL 은 족보가 없는데 `약물대사` 에 0.40 으로 붙었다.
PINS_FILE = "pins.json"
RE_RUN_ID = re.compile(r"\[(\d{6}_\d{2})")


def jokbo_pin(stem: str, jokbo_dir: Path) -> tuple[bool, str | None]:
    """이 편에 사람이 지정한 조각. (지정이 있는가, 조각 제목 또는 None)"""
    m = RE_RUN_ID.search(unicodedata.normalize("NFC", stem))
    path = Path(jokbo_dir).parent / PINS_FILE
    if not m or not path.is_file():
        return False, None
    try:
        pins = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as cause:
        print(f"⚠ {path} 를 못 읽었다 ({cause}) — 지정 없이 제목으로 대조한다", flush=True)
        return False, None
    if m.group(1) not in pins:
        return False, None
    value = pins[m.group(1)]
    return True, (unicodedata.normalize("NFC", str(value)) if value else None)


# ── 올해 교수 ──────────────────────────────────────────────────────
# 족보는 **올해 그 강의를 맡은 교수가 낸 해만** 쓴다(2026-10-05 관리자). 걸러 주는 것은
# `jokbo.filter_by_professor` 이고, 여기서는 「올해 교수가 누구인가」만 읽는다.
#
# 족보 표의 26년 열은 쓰지 않는다 — 시간표에서 옮긴 것이라 실제와 다르다.
PROF_GROUP = re.compile(r"\(([^()]*[가-힣][^()]*)\)")
PROF_TOKEN = re.compile(r"[가-힣]+")
PROFESSOR_DIR = "교수별"       # 거른 조각이 서는 자리. 판 폴더 아래다
FILTER_MIN_SCORE = 0.2         # 부르는 쪽 문턱 중 낮은 것(`build.find_jokbo_source`)


def _names(text: str) -> list[str]:
    """괄호 안 글에서 사람 이름만. 2~4자, 또는 3자 이름을 붙여 쓴 것(`문경철김혜령`)."""
    return [t for t in PROF_TOKEN.findall(text)
            if 2 <= len(t) <= 4 or (len(t) % 3 == 0 and len(t) <= 12)]


def _runs_dir(jokbo_dir: Path) -> Path | None:
    for parent in Path(jokbo_dir).resolve().parents:
        if parent.name in ("_materials", "_jokbo"):
            return parent.parent
    return None


def lecture_professors(prep: dict, jokbo_dir: Path) -> tuple[list[str], str]:
    """이 편의 **올해** 담당 교수와 그것을 어디서 읽었는가.

    1. `prep["professors"]` — 부르는 쪽이 이미 안다면
    2. `runs/<편>/pre_target.json` — **예습 자리.** 예습은 작년 필기로 만들므로 파일명의
       교수는 작년 교수다. 그 자리가 어느 올해 강의를 위해 도는지는 이 파일만 안다
       (`runner/prequeue.write_target`). 파일이 있으면 비어 있어도 파일명으로 내려가지
       않는다 — 작년 교수를 올해 교수로 쓰게 된다.
    3. 필기 파일명의 마지막 괄호 — `[260812_02] 세포의 손상(1)(고지원)_필기자v1`
    """
    if prep.get("professors"):
        return [str(p) for p in prep["professors"]], "prep.json"
    stem = unicodedata.normalize("NFC", Path(prep.get("source", "")).stem)
    m = RE_RUN_ID.search(stem)
    runs = _runs_dir(jokbo_dir)
    if m and runs:
        target = runs / m.group(1) / "pre_target.json"
        if target.is_file():
            try:
                got = json.loads(target.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                got = {}
            names = [n for p in got.get("professors") or [] for n in _names(str(p))]
            return names, f"{target.parent.name}/pre_target.json ({got.get('run_id', '?')})"
    groups = PROF_GROUP.findall(NAME_WRITER.sub("", NAME_PREFIX.sub("", stem)))
    for group in reversed(groups):
        names = _names(group)
        if names:
            return names, "필기 파일명"
    return [], "필기 파일명에 교수가 없다"


def professor_slice(slice_path: Path, prep: dict, jokbo_dir: Path
                    ) -> tuple[Path | None, dict | None]:
    """조각을 올해 교수가 낸 해만 남긴 것으로 바꾼다. (쓸 조각, 거른 기록)

    거른 조각은 `<판>/교수별/<교수>/` 에 원래 이름 그대로 선다(.json 과 .md). **카드를
    만드는 쪽과 뒷면을 굽는 쪽이 같은 파일을 본다** — 둘 다 `find_jokbo` 를 지나기 때문이다.

    - 실습 조각은 거르지 않는다. 족보에 실습 회차별 출제 교수가 적혀 있지 않다.
    - 원래 문항이 0 이면 그대로 둔다(거를 것이 없다).
    - 남는 것이 없으면 `None` — **부르는 쪽은 「족보 없음」으로 받는다.** 그 이유는
      기록(`dropped_all`)에 있다. 재료 없음 · 문턱 미달과 섞이면 안 된다.
    """
    from . import jokbo

    payload = json.loads(Path(slice_path).read_text(encoding="utf-8"))
    if payload.get("lecture_key") == "PRAC":
        return slice_path, {"skipped": "실습 조각은 회차별 출제 교수가 없어 거르지 않았다"}
    if not payload.get("questions"):
        return slice_path, None
    professors, how = lecture_professors(prep, jokbo_dir)
    if not professors:
        return None, {"dropped_all": True, "how": how,
                      "why": f"올해 담당 교수를 모른다 ({how}) — 누가 낸 해를 남길지 못 정한다",
                      "n_before": len(payload["questions"]), "n_after": 0}
    new, note = jokbo.filter_by_professor(payload, professors)
    note["how"] = how
    if not new["questions"]:
        note["dropped_all"] = True
        note["why"] = (f"올해 교수({'·'.join(professors)})가 낸 해가 이 조각에 없다 — "
                       f"{jokbo.filter_line(note)}")
        return None, note
    out = Path(jokbo_dir) / PROFESSOR_DIR / "·".join(professors)
    out.mkdir(parents=True, exist_ok=True)
    target = out / Path(slice_path).name
    sec = jokbo.Section(lecture_key=new["lecture_key"], title=new["title"],
                        may_contain=[(m["lecture_key"], m["title"])
                                     for m in new.get("may_contain") or []])
    fields = {f for f in jokbo.Question.__dataclass_fields__ if f not in ("body", "span", "bank")}
    sec.questions = [jokbo.Question(**{k: v for k, v in q.items() if k in fields})
                     for q in new["questions"]]
    # 두 세션이 같은 편을 동시에 부를 수 있다. 반쯤 쓰인 파일을 읽지 않게 바꿔 끼운다.
    for path, text in ((target, json.dumps(new, ensure_ascii=False, indent=2)),
                       (target.with_suffix(".md"), jokbo.to_markdown(sec, new["stats"]))):
        tmp = path.with_name(f".{path.name}.{id(text)}.tmp")
        tmp.write_text(text, encoding="utf-8")
        tmp.replace(path)
    return target, note


def _filtered(path: Path, score: float, top: list, prep: dict, jokbo_dir: Path
              ) -> tuple[Path | None, float, list]:
    """고른 조각을 올해 교수로 거르고, 거른 기록을 1등 후보에 얹어 돌려준다."""
    got, note = professor_slice(path, prep, jokbo_dir)
    if note is not None and top:
        first = (top[0][0], {**top[0][1], "professor_filter": note}, top[0][2])
        top = [first, *top[1:]]
    if note and note.get("dropped_all"):
        print(f"족보 조각: {note['why']}", flush=True)
    elif note and note.get("n_before"):
        from .jokbo import filter_line
        print(f"족보 조각: {filter_line(note)}", flush=True)
    return got, score, top


PROF_TIE_MARGIN = 0.1         # 제목 점수가 이만큼 안에서는 올해 교수가 낸 조각을 고른다


def _prefer_professor(scored: list, prep: dict, jokbo_dir: Path) -> list:
    """제목 점수가 엇비슷한 후보 중 **올해 교수가 낸 해가 있는 조각**을 앞에 세운다.

    제목 대조는 겹치는 낱말에 끌린다. 병리학 `종양의 병태생리(5) 발암의 원인(이혜승)` 이
    `7 급성염증의 병태생리` 에 0.50, `24-25 종양의 생물학적 특성, 발암의 원인` 에 0.46 이었다
    (「병태생리」). 올해 교수로 거르기 시작하면 틀린 쪽은 남는 문항이 0 이라 기출이 통째로
    빠진다. 이혜승이 낸 해는 24-25 에만 있다.

    1등이 이미 올해 교수의 해를 가졌거나, 올해 교수를 모르면 그대로 둔다.
    """
    if len(scored) < 2 or scored[0][0] < FILTER_MIN_SCORE:
        return scored
    professors, _ = lecture_professors(prep, jokbo_dir)
    if not professors:
        return scored
    from .jokbo import filter_by_professor

    def has_years(entry: dict) -> bool:
        try:
            payload = json.loads((jokbo_dir / f"{entry['file']}.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return False
        return filter_by_professor(payload, professors)[1]["n_after"] > 0

    if has_years(scored[0][1]):
        return scored
    for i, cand in enumerate(scored[1:], start=1):
        if cand[0] < scored[0][0] - PROF_TIE_MARGIN:
            break
        if has_years(cand[1]):
            print(f"족보 조각: 제목은 {scored[0][1]['lecture_key']}({scored[0][0]:.2f}) 쪽이 조금 "
                  f"닮았지만 올해 교수({'·'.join(professors)})가 낸 해는 "
                  f"{cand[1]['lecture_key']}({cand[0]:.2f}) 에 있다 — 그쪽을 쓴다", flush=True)
            return [cand, *scored[:i], *scored[i + 1:]]
    return scored


def find_jokbo(prep: dict, jokbo_dir: Path) -> tuple[Path | None, float, list]:
    """강의 파일명과 족보 목차 제목을 대조해 조각을 고른다.

    **사람이 지정해 둔 편은 대조하지 않는다**(`jokbo_pin`). 카드를 만드는 쪽과 뒷면을
    굽는 쪽이 둘 다 여기를 지나므로 지정도 여기 한 곳에서 먹는다.

    **고른 조각은 올해 교수가 낸 해만 남겨서 돌려준다**(`professor_slice`). 같은 이유로
    여기 한 곳에서 먹는다. 남는 것이 없으면 조각이 `None` 이고, 왜인지는 1등 후보의
    `professor_filter` 에 있다.
    """
    index = json.loads((jokbo_dir / "index.json").read_text(encoding="utf-8"))
    stem = unicodedata.normalize("NFC", Path(prep["source"]).stem)
    pinned, want = jokbo_pin(stem, jokbo_dir)
    if pinned and want is None:
        print(f"족보 조각: {PINS_FILE} 가 이 편에는 족보가 없다고 적었다", flush=True)
        return None, 0.0, []
    if pinned:
        for e in index["lectures"]:
            if want in (unicodedata.normalize("NFC", e["title"]), e["lecture_key"]):
                print(f"족보 조각: {PINS_FILE} 가 지정 — {e['lecture_key']} {e['title']}", flush=True)
                return _filtered(jokbo_dir / f"{e['file']}.json", 1.0, [(1.0, e, None)],
                                 prep, jokbo_dir)
        # 다시 자르면서 제목이 바뀌었을 수 있다. 조용히 대조로 넘어가면 사람은 지정이
        # 먹은 줄 안다.
        print(f"⚠ {PINS_FILE} 가 지정한 조각 「{want}」이 이 판에 없다 — 제목으로 대조한다",
              flush=True)
    name = char_ngrams(clean_lecture_name(stem))
    # 실습 강의는 실습 문항 조각(PRAC)만 상대한다. 필기 조각과 섞으면 양쪽 다 오염된다 —
    # 실습 97문항은 한 덩어리라 어느 실습 소관인지는 모델이 골라야 한다(may_contain 과 같은 처지).
    practice = bool(RE_PRACTICE.search(stem))

    # 조각의 제목뿐 아니라, 그 조각에 섞여 들어온 강의 제목으로도 대조한다.
    # 족보 본문에 제목이 없는 강의는 앞 섹션에 흡수돼 있어 자기 조각이 없다.
    scored = []
    for e in index["lectures"]:
        if (e["lecture_key"] == "PRAC") != practice:
            continue
        scored.append((_score(name, e["title"]), e, None))
        for mk in e.get("may_contain", []):
            slice_json = json.loads((jokbo_dir / f"{e['file']}.json").read_text(encoding="utf-8"))
            for mc in slice_json.get("may_contain", []):
                if mc["lecture_key"] != mk:
                    continue
                scored.append((_score(name, mc["title"]), e, mc))
    scored.sort(key=lambda x: -x[0])
    if not scored:
        return None, 0.0, []
    scored = _prefer_professor(scored, prep, jokbo_dir)
    best, entry, via = scored[0]
    path = jokbo_dir / f"{entry['file']}.json"
    if best < FILTER_MIN_SCORE:
        # 부르는 쪽이 어차피 안 붙인다(문턱 0.2 · 0.25). 거른 파일을 세우고 「남겼다」를
        # 찍으면 붙은 줄 안다.
        return path, best, scored[:3]
    return _filtered(path, best, scored[:3], prep, jokbo_dir)

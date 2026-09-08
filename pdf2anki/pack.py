"""프롬프트를 파트로 나눠 쓰는 일과, 파일명에서 강의를 알아보는 일.

여기 있는 것은 전부 **목적 중립**이다 — 토큰 예산, Read 도구의 상한, 제목 대조.
어떤 카드를 좋은 카드로 볼 것인가는 여기 없다. 그것은 각 파이프라인의 `assemble` 소관이다.

복습 덱(`pdf2anki.assemble`)과 예습 덱(`pdf2anki.prequiz.assemble`)이 함께 쓴다.
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


def find_jokbo(prep: dict, jokbo_dir: Path) -> tuple[Path | None, float, list]:
    """강의 파일명과 족보 목차 제목을 대조해 조각을 고른다."""
    index = json.loads((jokbo_dir / "index.json").read_text(encoding="utf-8"))
    stem = unicodedata.normalize("NFC", Path(prep["source"]).stem)
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
    best, entry, via = scored[0]
    return jokbo_dir / f"{entry['file']}.json", best, scored[:3]

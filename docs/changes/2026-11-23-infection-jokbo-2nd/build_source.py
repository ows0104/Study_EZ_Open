# -*- coding: utf-8 -*-
"""감염과 면역 2차 족보 원천 세트 — 1차와 같은 책의 119~183쪽 (2026-11-23).

    python docs/changes/2026-11-23-infection-jokbo-2nd/build_source.py [--report]

1차 세트(`~/amgi/data/pastexam/pes_infection-immunity-1-2026_*`)를 만든 amgi 도구
(`parse_jokbo_pharm` · `build_pastexam_pharm` · pdfchange 이미지 추출)를 «고치지 않고» 라이브러리로 쓴다.
amgi 파서는 책 전체를 한 번에 읽어 1차 답 구획에서 멈추므로, 2차 구역(교수 표 119쪽 · 문제 120~175쪽 ·
답 176~183쪽)만 잘라 낸 PDF를 같은 파서에 넣는다. 조판은 1차와 같다(강의 번호 머리 · 연도 머리 · 답 구획).

출력은 git 밖 `runs/_materials/감염과 면역/jokbo-solve/source-2/` — amgi 와 같은 꼴이라
`python -m runner.jokbo_solve build --edition 2026-2` 가 그대로 읽는다.

    source-2/book-2.pdf                         잘라 낸 2차 구역(원본 119~183쪽)
    source-2/data/pastexam/raw/…json            파서 원장
    source-2/data/pastexam/pes_infection-immunity-2-2026_<강의>.json · index.json
    source-2/data/lecture-map.json              빈 지도(1차 L번호용, 2차에는 없음)
    source-2/webapp/public/pastexam-figures/    문항 그림 · index.json

강의 붙이기: 책 머리 번호는 「2026년도 기준」이라 적혀 있지만 64~66은 올해 시간표와 다르다
(책 64 호산구성 = 올해 66, 책 65 약물 알레르기 = 올해 64, 책 66 다양한 알레르기 = 올해 65).
번호가 아니라 제목으로 이어 `BOOK_TO_LECTURE`에 적었다.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

AMGI = Path.home() / "amgi"
sys.path.insert(0, str(AMGI / "tools"))
sys.path.insert(0, "C:/Users/erika/pdfchange/src")

import pastexam_infection as PI  # noqa: E402  (줄 크기 보정 lines_of 를 PP 에 끼운다)
from pastexam_infection import BP, PP  # noqa: E402

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
for parent in REPO.parents:   # worktree 에서 돌려도 원래 저장소의 runs/
    if parent.name == "worktrees" and parent.parent.name == ".claude":
        REPO = parent.parent.parent
        break
if REPO.name.startswith("Study_EZ_") and (REPO.parent / "Study_EZ_Open").exists():
    REPO = REPO.parent / "Study_EZ_Open"
OUT_ROOT = REPO / "runs" / "_materials" / "감염과 면역" / "jokbo-solve" / "source-2"

BOOK = AMGI / "2025 감염과 면역 족보.pdf"     # 표지 「감염과 면역 2026 족보」, 183쪽
BOOK_SHA = "e55ba87973cd53b5cd33e95f40eb4271a398bb0ad0ddb331673462e0c2a21343"
FIRST, LAST = 119, 183                       # 1-기준 원본 쪽(교수 표 ~ 답 끝)
OFFSET = FIRST - 1                           # 잘라 낸 쪽 + OFFSET = 원본 쪽
BOOK_KEY = "2025-2"
BLOCK_ID = "infection-immunity-2-2026"
YEARS = ["2025", "2023", "2022", "2021", "2020"]

# 책 구획 → 올해 시간표 「감염과 면역 N」. 제목으로 이었다(위 설명).
BOOK_TO_LECTURE = {
    "49": 49, "50": 50, "51": 51, "52": 52, "53": 53, "54": 54, "55": 55, "56": 56, "57": 57,
    "58": 58, "59": 59, "60": 60, "61": 61, "62": 62, "63": 63,
    "64": 66,   # 호산구성 질환
    "65": 64,   # 약물 알레르기
    "66": 65,   # 다양한 알레르기질환
}
# 교수 표 오타: 64 호산구성 26·22열과 21열이 「박홍우」·「박흥우」로 섞였다. 다른 칸은 모두 「박흥우」.
NAME_FIX = {"박홍우": "박흥우"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def timetable() -> dict[int, dict]:
    import re
    events = json.loads((REPO / "data" / "timetable" / "2026_본1_2학기_시간표.json").read_text(encoding="utf-8"))
    out = {}
    for e in events:
        m = re.match(r"^감염과 면역 (\d+)$", e.get("title", ""))
        if m and int(m.group(1)) >= 49:
            lines = [x.strip() for x in e.get("details", "").splitlines() if x.strip()]
            prof = e.get("professor", "").strip()
            if lines and lines[-1] == prof:
                lines = lines[:-1]
            out[int(m.group(1))] = {"title": " ".join(lines), "professor": prof}
    return out


def slice_book(dest: Path) -> None:
    import pymupdf
    if sha256(BOOK) != BOOK_SHA:
        raise SystemExit(f"원본 해시가 다르다: {BOOK}")
    src = pymupdf.open(BOOK)
    out = pymupdf.open()
    out.insert_pdf(src, from_page=FIRST - 1, to_page=LAST - 1)
    dest.parent.mkdir(parents=True, exist_ok=True)
    out.save(dest)


def fix_names(names: list[str]) -> list[str]:
    return list(dict.fromkeys(NAME_FIX.get(n, n) for n in names))


_TEMP_TAIL = re.compile(r"^\d\s*(?:℃|°\s*C)")


def join_temperature_splits(raw: dict) -> list[dict]:
    """「체온 37.」 줄 끝 + 「0℃이다…」 다음 줄을 파서가 37번 문항으로 읽은 자리를 다시 붙인다.

    63 두드러기 2025 35번(「체온 37.0℃」)과 66(책) 다양한 알레르기 2023 16번(「체온 36.5°C」):
    앞 문항은 선지가 없고, 뒤 «문항»은 «0℃이다» 로 시작하며 선지를 가졌다. 답안지에는 앞 번호만 있다.
    """
    items = raw["items"]
    joined, out, skip = [], [], set()
    for k, it in enumerate(items):
        if k in skip:
            continue
        nxt = items[k + 1] if k + 1 < len(items) else None
        if (nxt is not None and not it["choices"] and not it["setHead"] and nxt["num"] is not None
                and (nxt["lecIdx"], nxt["year"]) == (it["lecIdx"], it["year"]) and _TEMP_TAIL.match(nxt["stem"])):
            it = dict(it, stem=f"{it['stem']} {nxt['num']}.{nxt['stem']}", choices=list(nxt["choices"]))
            skip.add(k + 1)
            joined.append({"ref": it["ref"], "year": it["year"], "kept": it["num"], "dropped": nxt["num"],
                           "page": it["page"] + OFFSET})
        out.append(it)
    raw["items"] = out
    raw["answers"] = [a for a in raw["answers"]
                      if not any((a["ref"], a["year"], a["num"]) == (j["ref"], j["year"], j["dropped"]) for j in joined)]
    return joined


def parse(book_pdf: Path) -> dict:
    PP.BOOKS = {BOOK_KEY: {"path": book_pdf, "years": YEARS}}
    raw = PP.parse(BOOK_KEY)
    raw["temperatureJoins"] = join_temperature_splits(raw)
    table = PP.professors(BOOK_KEY)
    # 2차 표는 칸마다 이름이 하나다. 표 아래 안내문(「생긴」「강의라」…)이 마지막 줄(62 암면역)에 붙어 읽히므로
    # 열마다 맨 위 이름 하나만 둔다(PP.professors 는 열·y 순으로 모은다).
    raw["professors"] = {ref: {**row, "years": {y: fix_names(v)[:1] for y, v in row["years"].items()}}
                         for ref, row in table.items()}
    raw["professorsSource"] = f"책 {FIRST}쪽 「감염과 면역 2차시험 교수님 목록」(열 26~20) · 오타 보정 {NAME_FIX}"
    raw["pageOffset"] = OFFSET
    return raw


def build(raw: dict, out: Path) -> dict:
    tt = timetable()
    rows = raw["professors"]
    lectures = []
    for ref, seq in BOOK_TO_LECTURE.items():
        p25 = (rows.get(ref) or {}).get("years", {}).get("2025") or []
        lectures.append({"seq": seq, "title": tt[seq]["title"], "professor": tt[seq]["professor"],
                         "professorChanged": "/".join(p25) if p25 else None})
    block = {"blockId": BLOCK_ID, "lectures": lectures}
    BP.load_block = lambda: block
    BP.RAW = out / "data" / "pastexam" / "raw"
    BP.OUT = out / "data" / "pastexam"
    BP.BOOKS = [BOOK_KEY]
    BP.RAW_NAME = "jokbo-infection-{}.json"
    BP.UNKNOWN_PROF_YEARS = ()
    BP.NOTE_PROFS = {}
    BP.UNMAPPED_TITLE = {}
    aliases = {}
    for ref, title in raw["lectures"]:
        seq = BOOK_TO_LECTURE[ref]
        aliases[BP.norm_lec(title)] = {"lectures": [seq], "confirm": False,
                                       "why": f"책 구획 {ref} 「{title}」 → 올해 {seq} 「{tt[seq]['title']}」 (제목)"}
    for ref, row in rows.items():
        if ref in BOOK_TO_LECTURE:
            aliases.setdefault(BP.norm_lec(row["title"]), {"lectures": [BOOK_TO_LECTURE[ref]], "confirm": False,
                                                           "why": f"교수 표 {ref} 「{row['title']}」"})
    BP.ALIASES = aliases
    BP.RAW.mkdir(parents=True, exist_ok=True)
    (BP.RAW / BP.RAW_NAME.format(BOOK_KEY)).write_text(json.dumps(raw, ensure_ascii=False, indent=1), encoding="utf-8")
    idx = BP.write(BP.build())
    idx["source"] = f"{BOOK.name} {FIRST}~{LAST}쪽 (감염과 면역 2차 시험 족보)"
    idx["professorSource"] = {"2025": f"책 {FIRST}쪽 표의 25열", "2020-2023": f"책 {FIRST}쪽 표"}
    (BP.OUT / "index.json").write_text(json.dumps(idx, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "data" / "lecture-map.json").write_text('{"lectures": []}\n', encoding="utf-8")
    return idx


def figures(raw: dict, idx: dict, book_pdf: Path, out: Path) -> dict:
    """amgi export_pastexam_infection_figures 와 같은 잣대: 그림 가운데의 «바로 앞에 시작한 문항»이 주인."""
    from pdfchange import Document, extract_images
    from probe_jokbo import COLUMN_SPLIT
    import pymupdf
    fig_out = out / "webapp" / "public" / "pastexam-figures"
    if fig_out.exists():
        shutil.rmtree(fig_out)
    fig_out.mkdir(parents=True)
    set_ref = {m["bookRef"]: m["ref"] for m in idx["sectionMap"]}
    in_sets = {it["pastExamItemId"] for s in idx["sets"]
               for it in json.loads((BP.OUT / s["file"]).read_text(encoding="utf-8"))["items"]}
    starts = sorted((it["page"], it["col"], it["y0"], BP.item_id(it["year"], set_ref[it["ref"]], it["pre"], it["num"], it.get("occ", 1)))
                    for it in raw["items"] if it["num"] is not None and it["year"] and it["ref"] in set_ref)
    anchor = tuple(raw["answerAnchor"]) if raw.get("answerAnchor") else None
    last_page = anchor[0] if anchor else max(s[0] for s in starts)
    tmp = Path(tempfile.mkdtemp(prefix="jokbo2-imgs-"))
    recs = extract_images(Document.open(book_pdf), tmp, pages=range(0, last_page), manifest=False)
    heights = [p.rect.height for p in pymupdf.open(book_pdf)]
    owners: dict = {}
    unclaimed = []
    for r in recs:
        if not r.get("file") or r.get("error"):
            continue
        x0, yb0, x1, yb1 = r["bbox"]
        ymid = heights[r["page"] - 1] - (yb0 + yb1) / 2
        col = 0 if (x0 + x1) / 2 < COLUMN_SPLIT else 1
        key = (r["page"], col, ymid)
        if anchor and key >= anchor:
            unclaimed.append({"file": r["file"], "page": r["page"] + OFFSET, "why": "답 구획"}); continue
        prev = [s for s in starts if (s[0], s[1], s[2]) <= key]
        if not prev:
            unclaimed.append({"file": r["file"], "page": r["page"] + OFFSET, "why": "주인 없음"}); continue
        iid = prev[-1][3]
        if iid not in in_sets:
            unclaimed.append({"file": r["file"], "page": r["page"] + OFFSET, "why": f"세트 밖 {iid}"}); continue
        owners.setdefault(iid, []).append(r)
    index: dict = {}
    placed = []
    for iid, rs in sorted(owners.items()):
        rs.sort(key=lambda r: (r["page"], -r["bbox"][3], r["bbox"][0]))
        for n, r in enumerate(rs, 1):
            name = f"{iid}{'' if len(rs) == 1 else f'-{n}'}{Path(r['file']).suffix}"
            shutil.copy2(tmp / r["file"], fig_out / name)
            index.setdefault(iid, []).append({"file": name, "w": r["width"], "h": r["height"]})
            placed.append({"item": iid, "file": name, "page": r["page"] + OFFSET})
    (fig_out / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")
    shutil.rmtree(tmp, ignore_errors=True)
    return {"placed": placed, "unclaimed": unclaimed}


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args()
    book_pdf = OUT_ROOT / "book-2.pdf"
    slice_book(book_pdf)
    raw = parse(book_pdf)
    idx = build(raw, OUT_ROOT)
    figs = figures(raw, idx, book_pdf, OUT_ROOT)
    summary = {"book": str(BOOK), "bookSha256": BOOK_SHA, "pages": [FIRST, LAST],
               "slice": str(book_pdf), "sliceSha256": sha256(book_pdf),
               "lectures": raw["lectures"], "totals": idx["totals"], "figures": figs}
    (OUT_ROOT / "build-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    if a.report:
        PI.report(idx)
        print(json.dumps({"figuresPlaced": len(figs["placed"]), "unclaimed": figs["unclaimed"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

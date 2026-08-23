"""여러 강의의 덱을 한 .apkg 로 묶는다.

**카드를 다시 만들지 않는다.** 이미 나온 .apkg 를 열어 노트·덱·미디어를 그대로 옮겨
담는다 — 재현 검사도 재개봉 검증도 이미 통과한 것들이다. 다시 렌더하면 그 통과가
무효가 되고, 그림 크롭을 800MB어치 다시 뜨는 값도 치러야 한다.

`merge.py` 와 다르다. merge 는 **한 강의**가 두 파일로 쪼개졌을 때 겹치는 카드를 찾아
하나로 접는 것이고, 이쪽은 **여러 강의**를 한 봉투에 담는 것이다. 덱 나무는 그대로
살아 있어서 Anki 에서 강의별로 갈라진다. 겹침 판정도, 카드 손질도 하지 않는다.

guid 가 그대로라 **이미 임포트한 덱 위에 덮어도 안전하다.** 같은 노트는 갱신되고
새 노트만 들어간다.

사용:
    python -m pdf2anki.bundle                      # out/ 의 복습 덱 전부
    python -m pdf2anki.bundle out/p260812_01 out/p260813_01 -o 골라담기.apkg
"""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import sys
import tempfile
import zipfile
from collections import Counter
from pathlib import Path

import genanki

from .build import CLOZE_MODEL, MODELS, _mid, verify

CONFIG = "run.config.json"          # 복습 덱 작업 폴더의 표식 (예습은 prequiz.config.json)
MODEL_BY_ID = {m.model_id: m for m in list(MODELS.values()) + [CLOZE_MODEL]}


# 예습 덱임을 알리는 꼬리. ` 예습` 이 지금 쓰는 것이고 나머지는 옛 이름이다.
PRE_SUFFIXES = (" 예습", "_pre", "_예습")


def main_apkg(work_dir: Path) -> Path | None:
    """그 작업 폴더의 복습 덱 하나. 없으면 None.

    **폴더 이름으로 짐작하지 않는다.** 한동안 `<폴더명>.apkg` 를 찾았는데 덱 파일은
    강의 ID(`p260812_01.apkg`)나 사람이 읽는 이름(`[260812_01] …apkg`)으로 서므로
    그 짐작은 맞은 적이 없다 — 폴더를 통째로 건너뛰고 **아무 말도 안 했다.**

    한 폴더에 복습과 예습이 같이 있을 수 있다(올해 필기가 내년에는 「작년 필기」다).
    꼬리로 가르고, 그래도 여럿이면 가장 새 것을 쓴다.
    """
    decks = [p for p in work_dir.glob("*.apkg")
             if not any(p.stem.endswith(s) for s in PRE_SUFFIXES)]
    return max(decks, key=lambda p: p.stat().st_mtime) if decks else None


def find_decks(root: Path) -> list[Path]:
    """복습 덱 작업 폴더에서 .apkg 를 찾는다. 예습 폴더와 `_` 로 시작하는 곳은 뺀다."""
    out = []
    for d in sorted(root.iterdir()):
        if not d.is_dir() or d.name.startswith("_") or not (d / CONFIG).exists():
            continue
        apkg = main_apkg(d)
        if apkg:
            out.append(apkg)
    return out


def read_apkg(path: Path, workdir: Path) -> dict:
    """.apkg 하나를 열어 노트·덱·미디어를 꺼낸다. 미디어는 실제 파일명으로 푼다."""
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
        db = next((n for n in ("collection.anki21", "collection.anki2") if n in names), None)
        if db is None:
            raise SystemExit(f"{path} 에 collection DB 가 없다")
        media_map = json.loads(z.read("media").decode("utf-8")) if "media" in names else {}

        media: dict[str, Path] = {}
        for blob, fname in media_map.items():
            dst = workdir / fname
            with z.open(blob) as fsrc, open(dst, "wb") as fdst:
                shutil.copyfileobj(fsrc, fdst)
            media[fname] = dst

        z.extract(db, workdir)
        dbpath = workdir / db
        con = sqlite3.connect(dbpath)
        try:
            decks = {int(k): v["name"] for k, v in
                     json.loads(con.execute("SELECT decks FROM col").fetchone()[0]).items()}
            # 노트가 어느 덱에 서는지는 그 노트의 카드가 안다. 한 노트의 카드는 한 덱에 있다.
            deck_of = {nid: decks.get(did, "Default") for nid, did in
                       con.execute("SELECT nid, did FROM cards ORDER BY ord DESC")}
            notes = [{"guid": g, "mid": mid, "tags": tags.split(),
                      "fields": flds.split("\x1f"), "deck": deck_of.get(nid, "Default")}
                     for nid, g, mid, tags, flds in
                     con.execute("SELECT id, guid, mid, tags, flds FROM notes ORDER BY id")]
        finally:
            con.close()
        dbpath.unlink()
        return {"notes": notes, "media": media, "decks": set(decks.values()) - {"Default"}}


def bundle(apkgs: list[Path], out: Path) -> dict:
    out.parent.mkdir(parents=True, exist_ok=True)
    decks: dict[str, genanki.Deck] = {}
    media: dict[str, Path] = {}
    seen: dict[str, str] = {}           # guid → 어느 .apkg 에서 먼저 봤나
    stats = Counter()
    rows = []

    with tempfile.TemporaryDirectory(prefix="pdf2anki_bundle_") as td:
        root = Path(td)
        for i, ap in enumerate(apkgs):
            work = root / f"{i:03d}"
            work.mkdir()
            got = read_apkg(ap, work)
            n_new = 0
            for n in got["notes"]:
                if n["guid"] in seen:
                    stats["중복 guid"] += 1
                    continue
                seen[n["guid"]] = ap.parent.name
                model = MODEL_BY_ID.get(n["mid"])
                if model is None:
                    raise SystemExit(f"{ap} 에 모르는 노트 모델이 있다 (mid={n['mid']})")
                deck = decks.setdefault(n["deck"], genanki.Deck(_mid(n["deck"]), n["deck"]))
                deck.add_note(genanki.Note(model=model, fields=n["fields"],
                                           guid=n["guid"], tags=n["tags"]))
                n_new += 1
            for fname, p in got["media"].items():
                old = media.get(fname)
                if old is not None and old.stat().st_size != p.stat().st_size:
                    raise SystemExit(
                        f"미디어 이름이 겹치는데 내용이 다르다: {fname}\n"
                        f"   {old}  vs  {p}\n"
                        "   파일명은 강의 ID 로 갈라져 있어야 한다. 한쪽을 다시 빌드해라.")
                media.setdefault(fname, p)
            rows.append((ap.parent.name, n_new, len(got["media"]), sorted(got["decks"])))
            stats["노트"] += n_new
            print(f"   {ap.parent.name:<14} 노트 {n_new:>4} · 미디어 {len(got['media']):>4}",
                  flush=True)

        pkg = genanki.Package([d for d in decks.values() if d.notes])
        pkg.media_files = [str(p) for p in media.values()]
        print(f"\n쓰는 중 — 노트 {stats['노트']} · 덱 {len(decks)} · 미디어 {len(media)} …",
              flush=True)
        pkg.write_to_file(out)

    return {"out": out, "n_notes": stats["노트"], "n_decks": len(decks),
            "n_media": len(media), "dup": stats["중복 guid"], "rows": rows}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="여러 강의의 덱을 한 .apkg 로 묶는다")
    ap.add_argument("dirs", nargs="*",
                    help="작업 폴더나 .apkg 경로. 생략하면 out/ 의 복습 덱을 전부 담는다")
    ap.add_argument("--root", default="out", help="자동으로 찾을 때 뒤질 폴더")
    ap.add_argument("-o", "--out", help="낼 파일. 기본 <root>/_bundle/<과목>.apkg")
    args = ap.parse_args(argv)

    if args.dirs:
        apkgs = []
        for d in args.dirs:
            p = Path(d)
            if p.is_dir():
                # 폴더를 대면 복습 덱을 고른다. 예습 덱은 경로를 직접 대야 담긴다 —
                # 목적도 푸는 시점도 다른 덱이라 자동으로 섞지 않는다.
                hit = main_apkg(p)
                if hit is None:
                    print(f"{p} 에 복습 .apkg 가 없다 — 건너뛴다")
                    continue
                apkgs.append(hit)
            elif p.exists():
                apkgs.append(p)
            else:
                print(f"{p} 를 찾지 못했다 — 건너뛴다")
    else:
        apkgs = find_decks(Path(args.root))

    if not apkgs:
        print("담을 .apkg 를 찾지 못했다.")
        return 1

    print(f"덱 {len(apkgs)}개를 담는다.\n")
    res = bundle(apkgs, Path(args.out) if args.out else _default_out(Path(args.root), apkgs))

    v = verify(res["out"], res["n_notes"], res["n_media"])
    size = res["out"].stat().st_size / 1e6
    print(f"\n끝났다.  {res['out'].as_posix()}  ({size:,.0f}MB)")
    print(f"   노트 {v['n_notes']} · 카드 {v['n_cards']} · 덱 {v['n_decks']} · 미디어 {v['n_media']}")
    if res["dup"]:
        print(f"   guid 가 겹쳐 건너뛴 노트 {res['dup']}개 (같은 강의를 두 번 담았을 때 난다)")
    if not v["ok"]:
        print("\n⚠ 재개봉 검증에서 걸렸다:")
        for p in v["problems"]:
            print(f"   - {p}")
        return 1
    print("\n재개봉 검증 통과. guid 가 그대로라 이미 임포트한 덱 위에 덮어도 안전하다.")
    return 0


def _default_out(root: Path, apkgs: list[Path]) -> Path:
    """과목 이름을 덱에서 따온다. 여럿이면 그냥 `전체`."""
    subjects = set()
    for ap in apkgs:
        cfg = ap.parent / CONFIG
        if cfg.exists():
            deck = json.loads(cfg.read_text(encoding="utf-8")).get("deck", "")
            if "::" in deck:
                subjects.add(deck.split("::")[0])
    name = subjects.pop() if len(subjects) == 1 else "전체"
    return root / "_bundle" / f"{name}.apkg"


if __name__ == "__main__":
    sys.exit(main())

"""기준선 카드를 `.apkg` 로 굽는다.

**노트 모델은 일부러 최소로 둔다** — 질문/정답/해설 셋뿐이다. 우리 템플릿(출처 접기,
경고 띠, 슬라이드 원본 병기)은 `pdf2anki` 가 쌓아 온 것이고, 그걸 기준선에 입혀 주면
무엇이 기준선의 실력인지 알 수 없게 된다.

반대로 **guid 는 우리 규칙을 따른다.** 같은 편을 다시 구웠을 때 안키에서 겹쳐 쓰이는
것은 품질이 아니라 배관이고, 배관이 어긋나면 비교 자체가 안 된다.

사용:
    python -m doby_is_free.pack <out_dir>
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
from pathlib import Path

import genanki
from PIL import Image

MODEL_ID = 1729400001
DECK_SEED = "doby_is_free"

CSS = """
.card { font-family: -apple-system, "Segoe UI", sans-serif; font-size: 20px;
        text-align: left; color: #1a1a1a; background: #fff; }
img { max-width: 100%; height: auto; border-radius: 4px; }
.q { margin-bottom: 12px; }
.a { font-weight: 600; margin-bottom: 8px; }
.expl { font-size: 16px; color: #555; }
hr { border: none; border-top: 1px solid #ddd; margin: 14px 0; }
"""

MODEL = genanki.Model(
    MODEL_ID, "Doby Is Free - Basic",
    fields=[{"name": "Question"}, {"name": "Answer"}, {"name": "Explanation"}],
    templates=[{
        "name": "Card 1",
        "qfmt": '<div class="q">{{Question}}</div>',
        "afmt": '{{FrontSide}}<hr><div class="a">{{Answer}}</div>'
                '{{#Explanation}}<div class="expl">{{Explanation}}</div>{{/Explanation}}',
    }],
    css=CSS,
)

RE_WS = re.compile(r"\s+")


def norm_key(q: str) -> str:
    return RE_WS.sub(" ", re.sub(r"<[^>]+>", " ", q)).strip().lower()


def guid_of(lecture_id: str, q: str, page=None, crop=None) -> str:
    """질문만으로는 안 된다 — 그림이 카드의 절반이다.

    기준선은 「이 세포는 무엇인가?」 처럼 짧고 같은 질문을 사진만 바꿔 여러 장
    낸다(GPT 웹 덱 46장 중 3장이 글자 그대로 같았다). 질문만 해싱하면 그 카드들이
    한 장으로 뭉개진다 — 겹침을 막으려던 장치가 기준선의 문체를 지운다.
    그래서 **앞면에 실제로 뜨는 것 전부**를 seed 로 쓴다.
    """
    box = clamp_crop(crop)
    tag = f"{page}|{'' if box is None else ','.join(f'{v:.3f}' for v in box)}"
    seed = f"{DECK_SEED}|{lecture_id}|{norm_key(q)}|{tag}"
    return hashlib.sha1(seed.encode("utf-8")).hexdigest()[:24]


def clamp_crop(crop) -> tuple[float, float, float, float] | None:
    """모델이 준 비율 상자를 믿지 않고 다듬는다. 뒤집히거나 너무 좁으면 버린다."""
    if not crop or len(crop) != 4:
        return None
    try:
        x0, y0, x1, y1 = (max(0.0, min(1.0, float(v))) for v in crop)
    except (TypeError, ValueError):
        return None
    if x1 <= x0 or y1 <= y0:
        return None
    if (x1 - x0) < 0.02 or (y1 - y0) < 0.02:
        return None
    return x0, y0, x1, y1


def cut(page_png: Path, crop, dst: Path) -> Path:
    """페이지 PNG 에서 구간을 잘라 낸다. crop 이 없거나 못 믿으면 통째로 쓴다."""
    img = Image.open(page_png)
    box = clamp_crop(crop)
    if box is not None:
        x0, y0, x1, y1 = box
        img = img.crop((round(x0 * img.width), round(y0 * img.height),
                        round(x1 * img.width), round(y1 * img.height)))
    img.save(dst)
    return dst


def esc(s) -> str:
    return html.escape(str(s or "")).replace("\n", "<br>")


def pack(out_dir: Path) -> dict:
    meta = json.loads((out_dir / "run.meta.json").read_text(encoding="utf-8"))
    cards = json.loads((out_dir / "cards.merged.json").read_text(encoding="utf-8"))["cards"]
    lecture_id, deck_name = meta["id"], meta["deck"]

    pages_dir = out_dir / "pages"
    media_dir = out_dir / "media"
    media_dir.mkdir(exist_ok=True)

    deck = genanki.Deck(int(hashlib.sha1(deck_name.encode()).hexdigest()[:8], 16), deck_name)
    media, skipped, seen = [], [], set()

    for i, c in enumerate(cards, 1):
        q, a = (c.get("q") or "").strip(), (c.get("a") or "").strip()
        if not q or not a:
            skipped.append({"i": i, "why": "q 또는 a 가 비었다"})
            continue
        guid = guid_of(lecture_id, q, c.get("page"), c.get("crop"))
        if guid in seen:
            skipped.append({"i": i, "why": "질문과 그림이 모두 겹친다", "q": q[:60]})
            continue
        seen.add(guid)

        front = f'<div class="q">{esc(q)}</div>'
        page = c.get("page")
        if page:
            src = pages_dir / f"p{int(page):03d}.png"
            if not src.exists():
                skipped.append({"i": i, "why": f"페이지 {page} 가 없다"})
                continue
            name = f"{lecture_id}_doby_{i:03d}.png"
            cut(src, c.get("crop"), media_dir / name)
            media.append(str(media_dir / name))
            front += f'<img src="{name}">'

        deck.add_note(genanki.Note(
            model=MODEL, guid=guid, fields=[front, esc(a), esc(c.get("explanation"))],
            tags=[f"doby::{lecture_id}"]))

    apkg = out_dir / f"[{lecture_id}] doby.apkg"
    pkg = genanki.Package(deck)
    pkg.media_files = media
    pkg.write_to_file(str(apkg))

    result = {"apkg": str(apkg), "notes": len(deck.notes), "media": len(media),
              "skipped": skipped}
    (out_dir / "pack.report.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    return result


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="기준선 카드를 .apkg 로 굽는다")
    ap.add_argument("out_dir")
    a = ap.parse_args(argv)
    r = pack(Path(a.out_dir))
    print(f"노트 {r['notes']}장 · 미디어 {r['media']}개"
          + (f" · 버린 것 {len(r['skipped'])}장" if r["skipped"] else ""))
    for s in r["skipped"][:10]:
        print(f"  - #{s['i']} {s['why']}")
    print(f"→ {r['apkg']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

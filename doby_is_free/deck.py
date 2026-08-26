"""`.apkg` 를 누가 만들었든 같은 모양으로 읽어 온다.

세 덱의 노트 모델이 다 다르다 — GPT 웹은 2필드(Question/Answer), `pdf2anki` 는
7필드, 기준선은 3필드다. 자를 대려면 먼저 같은 자리에 세워야 한다.

**앞면은 필드가 아니라 템플릿이 정한다.** 처음엔 필드에 `<img>` 가 있으면 이미지
카드로 셌는데, 그러면 `pdf2anki` 덱이 59장 전부 이미지 카드로 나온다 — 텍스트
카드도 `SlideImage` 필드에 슬라이드 원본을 들고 있고 그건 **뒷면**에만 뜬다.
그래서 `qfmt` 를 실제로 펴서 앞면 HTML 을 만들고, 거기 있는 그림만 센다.
자를 잘못 대면 재는 값이 아니라 재는 자가 틀린다.
"""

from __future__ import annotations

import html
import json
import re
import sqlite3
import tempfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

RE_IMG = re.compile(r'<img\s+[^>]*src="([^"]+)"', re.I)
RE_TAG = re.compile(r"<[^>]+>")
RE_WS = re.compile(r"\s+")
RE_SECTION = re.compile(r"\{\{([#^])([^}]+)\}\}(.*?)\{\{/\2\}\}", re.S)
RE_FIELD = re.compile(r"\{\{([^}#^/][^}]*)\}\}")


def plain(s: str) -> str:
    return RE_WS.sub(" ", html.unescape(RE_TAG.sub(" ", s or ""))).strip()


def render_front(qfmt: str, values: dict[str, str]) -> str:
    """앞면 템플릿을 편다. 조건절과 필터를 안키와 같은 규칙으로 처리한다."""
    def section(m: re.Match) -> str:
        kind, name, body = m.group(1), m.group(2).strip(), m.group(3)
        filled = bool((values.get(name) or "").strip())
        return body if (filled if kind == "#" else not filled) else ""

    prev = None
    out = qfmt
    while out != prev:                      # 중첩 조건절을 안쪽부터 접는다
        prev, out = out, RE_SECTION.sub(section, out)

    def one(m: re.Match) -> str:
        name = m.group(1).strip().split(":")[-1].strip()
        if name in ("FrontSide", "Tags", "Type", "Deck", "Subdeck", "Card"):
            return ""
        return values.get(name, "")

    return RE_FIELD.sub(one, out)


@dataclass
class Note:
    idx: int
    model: str
    front_html: str
    a_html: str
    fields: dict[str, str] = field(default_factory=dict)

    @property
    def q(self) -> str:
        return plain(self.front_html)

    @property
    def a(self) -> str:
        return plain(self.a_html)

    @property
    def images(self) -> list[str]:
        return RE_IMG.findall(self.front_html)

    @property
    def has_image(self) -> bool:
        return bool(self.images)


@dataclass
class Deck:
    name: str
    notes: list[Note]
    media_dir: Path
    models: list[str]

    @property
    def image_notes(self) -> list[Note]:
        return [n for n in self.notes if n.has_image]


def load(apkg: Path, work: Path | None = None) -> Deck:
    """apkg 를 풀어 노트와 미디어를 꺼낸다. work 를 주면 거기에 남긴다."""
    root = Path(work) if work else Path(tempfile.mkdtemp(prefix="doby-deck-"))
    root.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(apkg) as z:
        z.extractall(root)

    media_dir = root / "_media"
    media_dir.mkdir(exist_ok=True)
    mapping = json.loads((root / "media").read_text(encoding="utf-8"))
    for key, name in mapping.items():
        src = root / key
        if src.exists():
            (media_dir / name).write_bytes(src.read_bytes())

    con = sqlite3.connect(root / "collection.anki2")
    models = json.loads(con.execute("select models from col").fetchone()[0])
    by_mid = {int(k): v for k, v in models.items()}

    notes = []
    for i, (mid, flds) in enumerate(
            con.execute("select mid, flds from notes order by id"), 1):
        model = by_mid[mid]
        names = [f["name"] for f in model["flds"]]
        parts = flds.split("\x1f")
        values = dict(zip(names, parts + [""] * len(names)))
        front = render_front(model["tmpls"][0]["qfmt"], values)
        notes.append(Note(i, model["name"], front,
                          values.get(names[1], "") if len(names) > 1 else "",
                          values))
    con.close()
    return Deck(Path(apkg).stem, notes, media_dir,
                [m["name"] for m in by_mid.values()])

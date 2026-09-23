"""관리자가 사이트에서 고치거나 뺀 카드를 덱에 얹는다.

2026-09-23 관리자 지시 — 「사이트에서 고친 카드가 apkg에도 반영되게 해줘.」
그 전까지 사이트의 「카드 검토」(`server/app/routes/cards.py`)는 웹 풀이만 고쳤고
`.apkg` 는 구운 그대로 나갔다(그날 첫 지시로 만든 것이라 웹만 됐다).

판정은 서버에 있다. 러너가 그것을 당겨 편 폴더에 `site_edits.<main|pre>.json` 으로
적고(`runner/site_edits.py`), 빌드가 `--site-edits` 로 받아 카드에 얹는다. 모델이 낸
`items.reproduced.json` 은 **손대지 않는다** — 판정을 거두면 파일만 지우고 다시
구우면 원래대로다.

## 원본이 같을 때만 얹는다

판정은 `c002` 라는 id 에 붙어 있는데, 파이프라인이 그 편을 다시 만들면 `c002` 는
다른 카드일 수 있다. 그래서 판정마다 **사람이 본 원본**(웹에 보인 질문·답·해설)을
들고 오고, 지금 카드가 그것과 같을 때만 얹는다. 다르면 건너뛰고 세어서 알린다.
서버도 같은 까닭으로 판정을 버린다(`models.CardEdit`).

## 질문을 고쳐도 guid 는 그대로다

guid 씨앗이 `(강의 ID, 질문)` 이라(`build.guid_of`) 질문을 고치면 Anki 가 **새
노트**로 받는다 — 다시 임포트한 사람에게 같은 카드가 둘이 되고 옛 것의 복습 이력은
옛 것에 남는다. 그래서 고친 카드에 `guid_q`(원래 질문)를 달아 두고 빌드가 씨앗으로
그것을 쓴다. 다시 임포트하면 같은 노트의 갱신으로 받는다.

**뺀 카드는 이미 받아 간 사람의 Anki 에서 안 지워진다.** Anki 임포트는 노트를 지우지
않는다. 새로 받는 사람에게만 없다.

## 빈칸 카드는 원문을 고친다

빈칸 카드의 답은 질문 안에 있다(`{{c1::동물}}`). 웹은 그것을 `[____]` 로 펴서
보여 주므로 편 문장을 고쳐서는 되돌릴 수 없다 — 사이트는 빈칸 카드에서 원문
(`source_stem`)을 고치게 하고, 여기서는 그것을 `q` 에 넣는다.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

# 빈칸 표기. `runner.deck.plain_stem` 이 이것을 쓴다. **서버에도 같은 식이 하나
# 있다**(`server/app/routes/cards.py` 의 `plain_stem`) — 서버는 이 폴더를 import
# 하지 않는다(`server/CLAUDE.md`). 바꾸면 둘 다 바꾼다.
RE_CLOZE = re.compile(r"\{\{c(\d+)::(.+?)(?:::(.+?))?\}\}", re.S)

EDIT = "edit"
DELETE = "delete"


def web_stem(card: dict) -> str:
    """웹에 보이는 질문. 빈칸 카드는 `[힌트]` 나 `[____]` 로 편다."""
    if card.get("card_format") != "cloze":
        return card.get("q") or ""
    return RE_CLOZE.sub(lambda m: f"[{m.group(3) or '____'}]", card.get("q") or "")


def seen_as(card: dict) -> dict[str, str]:
    """사람이 사이트에서 본 모양. 판정의 `original` 과 맞대는 값이다."""
    return {
        "stem": web_stem(card),
        "answer": card.get("a") or "",
        "explanation": card.get("explanation") or "",
    }


def load(path: Path | str | None) -> list[dict]:
    if not path:
        return []
    got = json.loads(Path(path).read_text(encoding="utf-8"))
    edits = got.get("edits") if isinstance(got, dict) else got
    return [e for e in (edits or []) if isinstance(e, dict)]


def apply(cards: list[dict], edits: list[dict]) -> tuple[list[dict], dict[str, list[str]]]:
    """판정을 얹은 카드와, 무엇을 했는지(`edited`·`deleted`·`stale`).

    **들어온 목록을 고치지 않는다** — 고친 카드는 사본이다. 부르는 쪽이 원본으로
    다른 것을 세는 일이 있다.
    """
    by_id = {str(e.get("item_id") or ""): e for e in edits}
    done: dict[str, list[str]] = {"edited": [], "deleted": [], "stale": []}
    out: list[dict] = []
    for card in cards:
        cid = str(card.get("id") or "")
        edit = by_id.get(cid)
        if edit is None:
            out.append(card)
            continue
        original = edit.get("original") or {}
        seen = seen_as(card)
        if any((original.get(k) or "") != seen[k] for k in seen):
            done["stale"].append(cid)
            out.append(card)
            continue
        if edit.get("action") == DELETE:
            done["deleted"].append(cid)
            continue
        if edit.get("action") != EDIT:
            out.append(card)
            continue
        changed = dict(card)
        new_q = edit.get("source_stem") if card.get("card_format") == "cloze" else edit.get("stem")
        if new_q and new_q != card.get("q"):
            changed.setdefault("guid_q", card.get("q"))
            changed["q"] = new_q
        if edit.get("answer") is not None:
            changed["a"] = edit["answer"]
        if edit.get("explanation") is not None:
            changed["explanation"] = edit["explanation"]
        changed["site_edit"] = EDIT
        done["edited"].append(cid)
        out.append(changed)
    return out, done


def guid_q(card: dict) -> str:
    """guid 씨앗에 쓸 질문. 사이트에서 고친 카드는 원래 질문이다(머리 참조)."""
    return card.get("guid_q") or card["q"]

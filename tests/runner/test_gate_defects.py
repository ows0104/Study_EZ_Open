"""문항 결함 카드는 배포를 막지 않는다 — 올리고 사이트에서 고친다.

2026-09-23 관리자 지시 — 「이상한 카드가 있으면 업로드 단계에서 막히고 있어.
그러지 말고 일단 업로드를 하고, 사이트에서 검토/수정/삭제할 수 있도록 하자.」
그날 `260902_01`(c050) · `260921_03`(c002) 이 카드 한 장 때문에 덱째로 서 있었다.

사이트가 사유를 보여 주려면 run.meta 가 사유까지 실어야 한다 — 그것도 여기서 잰다.
"""

import json
from pathlib import Path

from runner import deck, gate


def _meta(tmp_path: Path, **extra) -> Path:
    path = tmp_path / "run.meta.json"
    path.write_text(json.dumps({
        "item_count": 2,
        "verified": {"notes": 2, "missing_media": []},
        **extra,
    }), encoding="utf-8")
    return path


def test_결함_카드가_있어도_막지_않는다(tmp_path):
    meta = _meta(tmp_path, reproduce_defects=["c002"])
    verdict = gate.inspect(tmp_path, tmp_path / "deck.apkg", meta, "Main-Quiz")

    assert verdict.ok, verdict.blocking
    assert any("c002" in note and "카드 검토" in note for note in verdict.notes), verdict.notes


def test_산출물이_자기_주장과_다르면_여전히_막는다(tmp_path):
    # 결함을 풀면서 이쪽까지 같이 풀리면 안 된다.
    meta = _meta(tmp_path, item_count=3, reproduce_defects=["c002"])
    verdict = gate.inspect(tmp_path, tmp_path / "deck.apkg", meta, "Main-Quiz")

    assert not verdict.ok
    assert any("item_count" in reason for reason in verdict.blocking)


def test_사유와_재현_답을_싣는다():
    cards = [
        {"id": "c001", "reproduce": {"verdict": "same"}},
        {"id": "c002", "reproduce": {"verdict": "different", "reason": "needs_options",
                                     "note": "분류 체계가 질문에 없다",
                                     "reproduced_answer": "gene reassortment"}},
        # 결함이 아닌 갈림은 싣지 않는다.
        {"id": "c003", "reproduce": {"verdict": "different", "reason": "lecture_specific"}},
    ]
    assert deck._reproduce_defect_notes(cards) == {
        "c002": {"reason": "needs_options", "note": "분류 체계가 질문에 없다",
                 "reproduced": "gene reassortment"},
    }
    assert deck._reproduce_defects(cards) == ["c002"]

import hashlib
import json

import pytest

from runner import deck


def setup(tmp_path):
    out = tmp_path / "prequiz" / "261006-1558"
    out.mkdir(parents=True)
    cards = [{"id": "c001", "q": "질문", "a": "답"}]
    review = {"method": "answer_visible_batch_review", "cards": [{"id": "c001", "ok": True, "issues": []}],
              "cards_sha256": hashlib.sha256(json.dumps(cards, ensure_ascii=False, sort_keys=True).encode()).hexdigest()}
    for name, data in {"prequiz.config.json": {"simple": True}, "items.checked.json": {"cards": cards},
                       "batch_review.json": review, "items.reproduced.json": {"cards": [{"id": "old"}]}}.items():
        (out / name).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return out, cards, review


def test_batch_reviewed_cards_export_without_claiming_reproduction(tmp_path):
    _, cards, _ = setup(tmp_path)
    assert deck.cards_of(tmp_path, deck.PRE, "261006-1558") == cards
    assert deck._reproduce_mix(cards) == {"없음": 1}


@pytest.mark.parametrize("problem", ["stale", "failed", "missing"])
def test_invalid_batch_review_blocks_export(tmp_path, problem):
    out, _, review = setup(tmp_path)
    if problem == "stale":
        review["cards_sha256"] = "old"
    elif problem == "failed":
        review["cards"][0].update(ok=False, issues=["문제 있음"])
    else:
        review["cards"] = []
    (out / "batch_review.json").write_text(json.dumps(review), encoding="utf-8")
    with pytest.raises(ValueError, match="묶음 검수"):
        deck.cards_of(tmp_path, deck.PRE, "261006-1558")

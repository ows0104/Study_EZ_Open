"""Image Occlusion 후보와 카드가 이름 있는 핵심 라벨에 묶이는지 검사한다."""

from pdf2anki.prep import usable_occlusion_label
from pdf2anki.prequiz.validate import validate as validate_prequiz
from pdf2anki.validate import validate


def _prep(label="type II 폐포세포"):
    return {
        "slides": 1,
        "pages": [{
            "slide": 1,
            "lecture_figures": [{"id": "fig_p01_01", "bbox": [0, 0, 400, 300]}],
            "occlusion_candidates": [{
                "id": "occ_p01_01",
                "label": label,
                "label_rect": [20, 20, 120, 45],
                "figure_id": "fig_p01_01",
            }],
        }],
    }


def _review_card(answer="type II 폐포세포"):
    return {
        "q": "가려진 폐포 세포의 이름은?",
        "a": answer,
        "explanation": "폐포 표면활성제를 만드는 세포다.",
        "slide_no": 1,
        "card_format": "image_occlusion",
        "card_type": "fact",
        "importance": "core",
        "source_type": "lecture",
        "evidence_type": "lecture_figure",
        "exam_hit": False,
        "media": {
            "figure_id": "fig_p01_01",
            "occlusion_ids": ["occ_p01_01"],
            "reveal_all": False,
        },
    }


def _prequiz_card(answer="type II 폐포세포"):
    card = _review_card(answer)
    card.pop("importance")
    card.pop("exam_hit")
    card["card_type"] = "term"
    card["reason"] = "vocabulary"
    return card


def _drop_codes(suspects):
    return [x["code"] for x in suspects["dropped"]]


def test_small_named_annotation_is_an_occlusion_candidate():
    assert usable_occlusion_label("type II 폐포세포", [20, 20, 120, 45], [0, 0, 400, 300])


def test_large_explanatory_text_box_is_not_an_occlusion_candidate():
    assert not usable_occlusion_label("중요 설명", [10, 10, 390, 180], [0, 0, 400, 300])


def test_symbol_only_annotation_is_not_an_occlusion_candidate():
    assert not usable_occlusion_label("?!!", [20, 20, 60, 40], [0, 0, 400, 300])


def test_named_label_with_matching_answer_passes():
    kept, suspects = validate({"cards": [_review_card()]}, _prep(), None)
    assert len(kept) == 1
    assert suspects["dropped"] == []


def test_bilingual_answer_passes_when_it_preserves_hidden_label():
    kept, suspects = validate(
        {"cards": [_review_card(answer="제2형 폐포세포(type II 폐포세포)")]},
        _prep(),
        None,
    )
    assert len(kept) == 1
    assert suspects["dropped"] == []


def test_unlabeled_region_is_rejected():
    kept, suspects = validate({"cards": [_review_card()]}, _prep(label=None), None)
    assert kept == []
    assert _drop_codes(suspects) == ["occlusion_unlabeled_region"]


def test_function_answer_for_hidden_name_is_rejected():
    kept, suspects = validate(
        {"cards": [_review_card(answer="surfactant 생성")]}, _prep(), None
    )
    assert kept == []
    assert _drop_codes(suspects) == ["occlusion_answer_mismatch"]


def test_prequiz_uses_the_same_occlusion_guard():
    kept, suspects = validate_prequiz(
        {"cards": [_prequiz_card(answer="surfactant 생성")]}, _prep(), None
    )
    assert kept == []
    assert _drop_codes(suspects) == ["occlusion_answer_mismatch"]

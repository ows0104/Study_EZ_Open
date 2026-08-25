from pathlib import Path

from pdf2anki.prompting import (CORE_MODULES, DEFAULT_DOMAIN, lecture_adapters,
                                module_names, read_modules)
from pdf2anki.reproduce import build_blind, build_grade


def test_shared_core_is_first_for_both_purposes():
    main = module_names(profile="exam_review", domain="generic")
    pre = module_names(profile="prelecture", domain="generic")
    assert main[:len(CORE_MODULES)] == CORE_MODULES
    assert pre[:len(CORE_MODULES)] == CORE_MODULES
    assert main[-1] == pre[-1] == "domains/generic.md"


def test_past_exam_adapters_are_conditional_and_domain_aware():
    plain = lecture_adapters(has_past_exam=False, domain="medical_ko")
    with_exam = lecture_adapters(has_past_exam=True, domain="medical_ko",
                                 allow_medical_exam_repair=True)
    pre_exam = lecture_adapters(has_past_exam=True, domain="medical_ko")
    generic_exam = lecture_adapters(has_past_exam=True, domain="generic")
    assert "adapters/past_exam.md" not in plain
    assert with_exam == plain + ("adapters/past_exam.md",
                                 "adapters/medical_past_exam.md")
    assert pre_exam == plain + ("adapters/past_exam.md",)
    assert generic_exam == plain + ("adapters/past_exam.md",)


def test_medical_domain_is_default_and_generic_is_available():
    assert DEFAULT_DOMAIN == "medical_ko"
    assert module_names(profile="exam_review")[-1] == "domains/medical_ko.md"
    generic = "\n".join(read_modules(profile="exam_review", domain="generic"))
    medical = "\n".join(read_modules(profile="exam_review", domain="medical_ko"))
    assert "한국어 의학 강의" not in generic
    assert "한국어 의학 강의" in medical


def test_reproduction_uses_domain_and_only_medical_jokbo_gets_answer_review():
    card = {"id": "c001", "q": "질문", "a": "답", "card_format": "basic"}
    blind = build_blind(Path("."), [card], None, domain="medical_ko")
    assert "일반적인 의학 지식" in blind

    lecture = [("c001", "### c001\n- 출처: lecture\n- 질문: Q")]
    jokbo = [("c002", "### c002\n- 출처: jokbo\n- 질문: Q")]
    assert "answer_suspect" not in build_grade(lecture, None, domain="medical_ko")
    assert "answer_suspect" not in build_grade(jokbo, None, domain="generic")
    assert "answer_suspect" in build_grade(jokbo, None, domain="medical_ko")


def test_unknown_prompt_selection_fails_loudly():
    for selection in (
        {"profile": "unknown", "domain": "generic"},
        {"profile": "exam_review", "domain": "unknown"},
    ):
        try:
            module_names(**selection)
        except ValueError:
            continue
        raise AssertionError(f"invalid selection was accepted: {selection}")


def test_runtime_prompts_do_not_accumulate_case_history():
    root = Path(__file__).parents[1] / "pdf2anki"
    paths = list((root / "prompts").rglob("*.md"))
    paths += list((root / "prequiz" / "prompts").rglob("*.md"))
    text = "\n".join(p.read_text(encoding="utf-8") for p in paths)
    for historical_patch in (
        "12편 322장",
        "250826_01",
        "생후 2일에 사망한",
        "어머니가 Rh 양성",
        "네가 아는 일반 의학 지식",
        "관리자가 못 쓴다고 판정",
        "용어·약어에 8~12장",
        "한 번에 3~6개를 가려도",
    ):
        assert historical_patch not in text

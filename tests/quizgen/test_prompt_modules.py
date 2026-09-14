from pathlib import Path

from quizgen.prompting import (
    CORE_MODULES,
    DEFAULT_DOMAIN,
    lecture_adapters,
    module_names,
    read_modules,
)
from quizgen.reproduce import build_blind, build_grade


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
    # 표기 규칙 세 단계. 하나라도 빠지면 계획 단계가 번역어를 지어낸다.
    assert "자료의 표기를 그대로 쓴다" in medical
    assert "자료에 그 개념의 표기가 없으면 영어를 쓴다" in medical
    assert "어려운 용어에는 뜻을 괄호로 붙인다" in medical
    assert "학습목표(과제 ①)에도 그대로 적용한다" in medical
    assert "같은 개념을 두 표기로 섞지 않는다" in medical


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
    root = Path(__file__).parents[2] / "quizgen"
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


def test_지도가_가리키는_프롬프트가_다_있다():
    """`docs/map.md` §2-1 이 프롬프트 폴더 안쪽을 파일 이름으로 안내한다.

    **문서가 없는 파일을 가리키면 그 문서를 믿고 온 사람이 헤맨다.** 프롬프트는
    이름이 자주 바뀌는 쪽이라(`philosophy.md` 가 조립으로 옮겨 간 것처럼) 여기서
    잡아 둔다.
    """
    import re

    root = Path(__file__).parents[2]
    text = (root / "docs" / "map.md").read_text(encoding="utf-8")
    named = set(re.findall(r"`((?:core|profiles|domains|adapters)/[\w.]+\.md)`", text))
    named |= set(re.findall(r"^\s{4}([\w_]+\.md)\s", text, re.M))
    assert named, "지도에서 프롬프트 이름을 하나도 못 찾았다 — 정규식이 낡았다"
    for name in sorted(named):
        assert ((root / "quizgen" / "prompts" / name).is_file()
                or (root / "quizgen" / "prequiz" / "prompts" / name).is_file()), name


def test_지도의_조립_순서가_코드와_같다():
    """§2-1 이 CORE → PROFILE → ADAPTERS → DOMAIN 이라고 적었다."""
    from quizgen.prompting import CORE_MODULES, DOMAINS, PROFILES

    names = module_names_for_test()
    assert names[:len(CORE_MODULES)] == list(CORE_MODULES)
    assert names[len(CORE_MODULES)] in PROFILES.values()
    assert names[-1] in DOMAINS.values()


def module_names_for_test():
    from quizgen.prompting import module_names
    return list(module_names(profile="exam_review",
                             adapters=("adapters/lecture_pdf.md",)))

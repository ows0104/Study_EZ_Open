"""Composable prompt modules shared by quiz pipelines.

The core prompt stays domain-agnostic. Purpose, source-specific behavior, and
domain terminology are added only by the caller that needs them.
"""

from __future__ import annotations

from pathlib import Path

PROMPT_ROOT = Path(__file__).parent / "prompts"
DEFAULT_DOMAIN = "medical_ko"

CORE_MODULES = (
    "core/quality.md",
    "core/evidence.md",
    "core/media.md",
    "core/language.md",
)

PROFILES = {
    "exam_review": "profiles/exam_review.md",
    "prelecture": "profiles/prelecture.md",
}

# **도메인 모듈의 예시는 실제로 나간 카드다. 그래서 그 편으로는 평가하지 마라.**
#
# `domains/medical_ko.md` 의 「형식 선택 — 이 분야의 실제 카드」가 쓰는 편은 이렇다.
#
#     250919_03  말라리아 재발 (recrudescence/relapse/reinfection)
#     250919_02  말라리아 모기 내 발육 (ookinete/oocyst/sporozoite)
#     250825_03  종양 혈관신생 (hypoxia/HIF-1α/VEGF)
#     250826_02  PCR cycle
#     260821_01  혈소판 부착·응집
#     260902_03  Praziquantel · 260903_02  T. saginata · 260821_03  염증의 네 징후
#
# 2026-09-05 에 이 목록이 한 편에 몰려 있어서 데었다. `core/quality.md` 의 예시가
# 넷 다 `260901_01`(장내선충증) 카드였고, 그 편을 새 프롬프트로 돌려 재 보니
# **cloze 14장 중 5장이 예시에서 그대로 나왔다.** 「규칙이 작동했다」로 읽을 뻔했다.
#
# 그래서 둘로 나눴다 — 코어는 분야를 비운 예시로 역학만 가르치고(모든 편에 실려도
# 누출이 없다), 실제 카드는 도메인 모듈에 두되 **여러 편에 흩는다.** 흩어도 누출은
# 남으니(같은 주제의 올해 편이 여전히 그 예시를 본다) 위 목록을 보고 평가할 편을 고른다.
# 주제까지 봐야 한다 — 작년 말라리아 예시는 올해 말라리아 편에도 닿는다.

DOMAINS = {
    "generic": "domains/generic.md",
    "medical_ko": "domains/medical_ko.md",
}

LECTURE_ADAPTERS = (
    "adapters/lecture_pdf.md",
    "adapters/annotations.md",
)


def lecture_adapters(*, has_past_exam: bool,
                     domain: str = DEFAULT_DOMAIN,
                     allow_medical_exam_repair: bool = False) -> tuple[str, ...]:
    """Adapters for the current PDF lecture source, with optional exam data."""
    if domain not in DOMAINS:
        raise ValueError(f"unknown prompt domain: {domain}")
    optional = ()
    if has_past_exam:
        optional += ("adapters/past_exam.md",)
        if domain == "medical_ko" and allow_medical_exam_repair:
            optional += ("adapters/medical_past_exam.md",)
    return LECTURE_ADAPTERS + optional


def module_names(*, profile: str, adapters: tuple[str, ...] = (),
                 domain: str = DEFAULT_DOMAIN) -> tuple[str, ...]:
    """Return the ordered module names used to assemble a runtime prompt."""
    if profile not in PROFILES:
        raise ValueError(f"unknown prompt profile: {profile}")
    if domain not in DOMAINS:
        raise ValueError(f"unknown prompt domain: {domain}")
    return CORE_MODULES + (PROFILES[profile],) + adapters + (DOMAINS[domain],)


def read_modules(*, profile: str, adapters: tuple[str, ...] = (),
                 domain: str = DEFAULT_DOMAIN) -> list[str]:
    """Read prompt modules in their composition order."""
    out = []
    for name in module_names(profile=profile, adapters=adapters, domain=domain):
        path = PROMPT_ROOT / name
        if not path.is_file():
            raise FileNotFoundError(path)
        out.append(path.read_text(encoding="utf-8"))
    return out

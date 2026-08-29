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

"""Priority and independent depth metadata, with read compatibility for old banks."""

TIERS = ["Essential", "Core", "Important", "Optional"]
TIER_ORDER = {tier: i for i, tier in enumerate(TIERS)}
IMPORTANCE = {"Essential": 5, "Core": 5, "Important": 4, "Optional": 2}


def priority_tier(item: dict) -> str:
    # Historical Advanced was the middle priority. It is not evidence of depth.
    tier = item.get("tier", "Optional")
    return "Important" if tier == "Advanced" else tier


def is_advanced(question: dict) -> bool:
    return question.get("advanced", False) is True


def priority_fields(item: dict, *, question: bool = False) -> dict:
    out = {**item, "tier": priority_tier(item)}
    if question:
        out.setdefault("advanced", False)
    return out

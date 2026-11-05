"""Positioned answers for already-revealed preview cards; never used for fronts."""
import re
from typing import Any

# Keep masking compatible with routes/cards.py and quizgen/site_edits.py.
_CLOZE = re.compile(r"\{\{c(\d+)::(.+?)(?:::(.+?))?\}\}", re.S)


def revealed_cloze(item: Any) -> dict:
    if item.qtype != "cloze" or not item.source_stem:
        return {}
    source = item.source_stem
    matches = list(_CLOZE.finditer(source))
    if not matches or _CLOZE.sub(lambda m: f"[{m.group(3) or '____'}]", source) != item.stem:
        return {}
    # Do not partially interpret malformed/nested cloze syntax.
    if "{{" in _CLOZE.sub("", source) or "}}" in _CLOZE.sub("", source):
        return {}
    parts = []
    offset = 0
    for match in matches:
        if "{{" in match.group(0)[2:-2] or "}}" in match.group(0)[2:-2]:
            return {}
        if match.start() > offset:
            parts.append({"text": source[offset:match.start()]})
        parts.append({"text": match.group(2), "blank": True})
        offset = match.end()
    if offset < len(source):
        parts.append({"text": source[offset:]})
    return {"clozeParts": parts}

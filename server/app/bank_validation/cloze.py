"""Compile inline authoring blanks to answer-free transport markers."""
from __future__ import annotations

import re

INLINE = re.compile(r"(?<!\{)\{([^{}\r\n]+)\}(?!\})")


def normalize_cloze(question: dict) -> dict:
    text = question.get("question")
    if question.get("format") != "cloze" or not isinstance(text, str):
        return question
    matches = list(INLINE.finditer(text))
    if not matches:
        return question
    units = [m[1].strip() for m in matches]
    return {**question, "question": INLINE.sub("{{c1}}", text),
            "answer": INLINE.sub(lambda m: m[1].strip(), text), "answer_units": units}

"""Order matching columns for display without changing the stored question or its answers."""

from __future__ import annotations

import re


_LABEL = re.compile(r"^(?:[LR]\d+[.:)]\s*|(?:\d+[.)]|[A-Z][.:)])\s+)", re.I)
_NUMBER = re.compile(r"\d+(?:\.\d+)?|\b(?:VIII|VII|VI|IV|III|II|IX|V|I|X)\b", re.I)
_ROMAN = {s: i for i, s in enumerate(("I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"), 1)}
_ORDINALS = (
    ("초기", "중기", "후기"), ("전기", "중기", "후기", "말기"),
    ("낮음", "중간", "높음"), ("저농도", "중농도", "고농도"),
    ("첫째", "둘째", "셋째", "넷째", "다섯째"),
    ("first", "second", "third", "fourth", "fifth"),
    ("early", "middle", "late"), ("low", "medium", "high"),
)


def _text(item: str) -> str:
    # Author-added labels describe positions, not the order of the content.
    return _LABEL.sub("", re.sub(r"[*_`]|<[^>]*>", "", item).strip()).casefold()


def ordered_items(items: list[str]) -> list[str] | None:
    """Recognize a shared numbered name (M1/M2, stage I/II), or explicit ordinal words.

    Require one common pattern and distinct ranks. Arbitrary names, presentation labels,
    mixed units and descriptions with unrelated numbers do not establish an order.
    """
    if len(items) < 2:
        return None
    texts = [_text(item) for item in items]
    numbers = [list(_NUMBER.finditer(text)) for text in texts]
    if all(len(found) == 1 for found in numbers):
        patterns, ranks = [], []
        for text, found in zip(texts, numbers):
            match = found[0]
            patterns.append(text[:match.start()] + "#" + text[match.end():])
            token = match.group().upper()
            ranks.append(float(_ROMAN[token]) if token in _ROMAN else float(token))
        if len(set(patterns)) == 1 and len(set(ranks)) == len(items):
            return [item for _, item in sorted(zip(ranks, items))]
    for words in _ORDINALS:
        pattern = re.compile(r"(?<!\w)(?:" + "|".join(words) + r")(?!\w)")
        matches = [list(pattern.finditer(text)) for text in texts]
        if not all(len(found) == 1 for found in matches):
            continue
        shapes, ranks = [], []
        for text, found in zip(texts, matches):
            match = found[0]
            shapes.append(text[:match.start()] + "#" + text[match.end():])
            ranks.append(words.index(match.group()))
        if len(set(shapes)) == 1 and len(set(ranks)) == len(items):
            return [item for _, item in sorted(zip(ranks, items))]
    return None


def matching_presentation(q: dict) -> dict:
    if q.get("format") != "matching":
        return q
    left, right = q.get("matching_left", []), q.get("matching_right", [])
    ordered_left, ordered_right = ordered_items(left), ordered_items(right)
    if ordered_left is not None:
        return {**q, "matching_left": ordered_left, "matchingOrdered": True}
    if ordered_right is None:
        return q
    pairs = q.get("answer_pairs", [])
    # Inverting a many-to-one question would require multiple choices per row.
    # Only invert complete bijections; keep reusable choices and distractors intact.
    reversible = (len(pairs) == len(left) == len(right)
                  and {p["left"] for p in pairs} == set(left)
                  and {p["right"] for p in pairs} == set(right))
    if not reversible:
        return q
    return {**q, "matching_left": ordered_right, "matching_right": left,
            "answer_pairs": [{"left": p["right"], "right": p["left"]} for p in pairs],
            "matchingOrdered": True}

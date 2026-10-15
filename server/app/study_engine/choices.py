"""Realize choice variants once, then freeze them in the served snapshot."""
import copy
import random
import re

from app.bank_validation.pool_checks import reviewed_ok


def _relabel(text: str, labels: dict[str, str]) -> str:
    # Only explicit choice references, never a bare biomedical symbol like A.
    ids = "|".join(re.escape(k) for k in sorted(labels, key=len, reverse=True))
    return re.sub(rf"(?<!\w)({ids})(?=\s*[:.)]|\s*(?:선지|보기))",
                  lambda m: labels[m[1]], text)


def realize_choices(q: dict, seed: str, previous: dict | None = None, *, use_pools: bool = True) -> dict:
    out = copy.deepcopy(q)
    if q["format"] not in ("mcq", "multi_select") or q.get("personalEdited"):
        return out
    rng = random.Random(seed)
    previous = previous or {}
    review = q.get("medicalReview") or {}
    pools = q.get("option_pools", []) if use_pools and reviewed_ok(q, review) else []
    if pools:
        # Rotate pools on successive exposures, rather than repeatedly drawing
        # the same set. Candidate subsets and truth forms vary within each pool.
        eligible = [p for p in pools if p["pool_id"] != previous.get("poolId")] or pools
        pool = rng.choice(eligible)
        candidates = rng.sample(pool["candidates"], pool["select_count"])
        correct_indexes = set(rng.sample(range(len(candidates)), len(q["correct_option_ids"])))
        entries, forms = [], {}
        for i, c in enumerate(candidates):
            correct = i in correct_indexes
            truth = (pool["correct_when"] == "true") == correct
            form = "true" if truth else "false"
            entries.append({"text": c[form + "_text"], "correct": correct,
                            "explanation": ("참 — " if truth else "거짓 — ") + c[form + "_explanation"]})
            forms[c["candidate_id"]] = form
        refs = [r for c in candidates for r in c["source_refs"]]
        out["source_refs"] = list({(r["source_id"], r["locator"]): r for r in q["source_refs"] + refs}.values())
        out["choice_variant"] = {"poolId": pool["pool_id"], "forms": forms}
    else:
        explanations = {e["option_id"]: e["text"] for e in q.get("option_explanations", [])}
        entries = [{"old_id": o["id"], "text": o["text"], "correct": o["id"] in q["correct_option_ids"],
                    "explanation": explanations.get(o["id"], "")} for o in q["options"]]
        out["choice_variant"] = {"poolId": "", "forms": {}}
    rng.shuffle(entries)
    # Shuffling may draw the same order. Avoid it when this exact question was
    # last shown with the same text sequence (including two-option legacy banks).
    texts = [e["text"] for e in entries]
    if len(entries) > 1 and texts == previous.get("texts"):
        entries = entries[1:] + entries[:1]
    labels = {e["old_id"]: chr(65 + i) for i, e in enumerate(entries) if "old_id" in e}
    out["options"] = [{"id": chr(65 + i), "text": e["text"]} for i, e in enumerate(entries)]
    out["correct_option_ids"] = [chr(65 + i) for i, e in enumerate(entries) if e["correct"]]
    out["answer"] = "\n".join(f"{o['id']}. {o['text']}" for o in out["options"] if o["id"] in out["correct_option_ids"])
    out["option_explanations"] = [{"option_id": chr(65 + i), "text": _relabel(e["explanation"], labels) if labels else e["explanation"]}
                                  for i, e in enumerate(entries) if e["explanation"]]
    out["answer_units"] = [f"{e['option_id']}: {e['text']}" for e in out["option_explanations"]] \
        if len(out["option_explanations"]) == len(entries) else [_relabel(text, labels) for text in q["answer_units"]]
    out["choice_variant"]["texts"] = [o["text"] for o in out["options"]]
    return out

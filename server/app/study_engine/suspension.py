"""Per-user exclusions preserve the authored bank and review history."""


def active_bank(bank: dict, state: dict) -> dict:
    suspended = set(state.get("suspended_question_ids", []))
    if not suspended:
        return bank
    return {**bank, "questions": [
        {**q, "prerequisites": [qid for qid in q["prerequisites"] if qid not in suspended]}
        for q in bank["questions"] if q["question_id"] not in suspended
    ]}

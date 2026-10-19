"""Archived exclusions are browseable; only an explicit personal restore joins study."""
import copy

from app.models import BankState


def records(row):
    active = {q['question_id'] for q in (row.bank or {}).get('questions', [])}
    return {r['question']['question_id']: r for r in (row.validation or {}).get('excludedQuestions', [])
            if r['question']['question_id'] not in active}


def decisions(db, row, user_id):
    state = db.get(BankState, (user_id, row.subject, row.run_id))
    return (state.state.get('excluded_question_decisions', {})
            if state and state.build_id == row.build_id else {})


def augment(db, row, user_id, bank):
    chosen = decisions(db, row, user_id)
    restored = [r for qid, r in records(row).items() if chosen.get(qid) == 'restored']
    if not restored:
        return bank
    out = copy.deepcopy(bank)
    ids = {q['question_id'] for q in out['questions']} | {r['question']['question_id'] for r in restored}
    for record in restored:
        q = copy.deepcopy(record['question'])
        q['prerequisites'] = [qid for qid in q.get('prerequisites', []) if qid in ids]
        out['questions'].append(q)
        for key, field in [('concept', 'concepts'), ('plan', 'retrieval_plan')]:
            value = record.get(key)
            if value and not any(c['concept_id'] == value['concept_id'] for c in out[field]):
                out[field].append(copy.deepcopy(value))
    return out

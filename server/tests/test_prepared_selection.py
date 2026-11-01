"""Prepared weighted draws are stable, authenticated and still obey pool rules."""

import copy
from types import SimpleNamespace
from unittest.mock import patch

from app.study_engine import empty_state, record_review
from app.study_engine.daily_queue import daily_candidates, select_daily_question
from app.study_engine.memory import DAY_MS
from app.study_engine.prepared_selection import context, open_draw, seal
from tests.bank_fixtures import simulation_bank

NOW = 1792112400000


def main():
    bank = simulation_bank()
    bank['questions'] = [q for q in bank['questions'] if q['retrieval_direction'] == 'direct']
    state = empty_state()
    for question in bank['questions']:
        state = record_review(bank, state, question['question_id'], 'Good', NOW - 30 * DAY_MS)
    entries = [{'key': ('s', 'r'), 'bank': bank, 'row': SimpleNamespace(build_id='v1'),
                'exam': '2026-11-01', 'state': state}]
    fingerprint = context(entries, NOW)
    assert context(entries, NOW + 300_000) == fingerprint
    ticket = seal('secret', 'user', 'parent', 'Good', fingerprint, ('s', 'r'), 'C1-direct')
    assert open_draw(ticket, 'secret', 'user', 'parent', 'Good', fingerprint) == (('s', 'r'), 'C1-direct')
    for secret, user, parent, rating, saved in [('bad', 'user', 'parent', 'Good', fingerprint),
            ('secret', 'other', 'parent', 'Good', fingerprint), ('secret', 'user', 'other', 'Good', fingerprint),
            ('secret', 'user', 'parent', 'Hard', fingerprint), ('secret', 'user', 'parent', 'Good', context(entries, NOW + DAY_MS))]:
        assert open_draw(ticket, secret, user, parent, rating, saved) is None
    assert open_draw(ticket + 'x', 'secret', 'user', 'parent', 'Good', fingerprint) is None
    assert open_draw('invalid', 'secret', 'user', 'parent', 'Good', fingerprint) is None
    original = copy.deepcopy(state)
    results = [select_daily_question(bank, state, '2026-11-01', NOW, seed='same-rating-token')['question']['question_id'] for _ in range(12)]
    assert len(set(results)) == 1
    variants = {select_daily_question(bank, state, '2026-11-01', NOW, seed=str(i))['question']['question_id'] for i in range(40)}
    assert len(variants) > 1, 'weighted draw became a fixed global order'
    pool, _ = daily_candidates(bank, state, '2026-11-01', NOW)
    reserved = pool[-1]['question']['question_id']
    with patch('app.study_engine.ordering.random.Random', side_effect=AssertionError('must not redraw')):
        got = select_daily_question(bank, state, '2026-11-01', NOW + 300_000, seed='actual', prepared=((), reserved))
    assert got['question']['question_id'] == reserved
    suspended = copy.deepcopy(state)
    suspended['suspended_question_ids'] = [reserved]
    assert select_daily_question(bank, suspended, '2026-11-01', NOW, seed='s', prepared=((), reserved))['question']['question_id'] != reserved
    assert context([{**entries[0], 'state': suspended}], NOW) != fingerprint
    assert state == original
    print('PASS: stable weighted draw, preserved signed selection without redraw, varied seeds, stale/tampered/foreign tickets, suspension, read-only state')


if __name__ == '__main__':
    main()

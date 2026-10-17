"""Entry recall precedes details without mastery locks or learner-data rewrites."""
import copy
from types import SimpleNamespace
from unittest.mock import patch

from tests.test_question_order import make_bank, solve, NOW, EXAM
from app.study_engine import empty_state, record_review
from app.study_engine.connections import connection_order
from app.study_engine.daily_queue import select_daily_question, select_extra_question, lecture_goal
from app.study_engine.batch import select_batch_question
from app.study_engine.memory import DAY_MS


def main():
    bank = make_bank([('detail', 'A', 'mechanism', 2, []),
                      ('unrelated', 'B', 'direct', 3, []),
                      ('root', 'A', 'direct', 20, [])])
    bank['questions'][2].update(format='list', question='이 개념의 기본 분류는?')
    original = copy.deepcopy(bank)
    assert solve(bank)[0] == ['root', 'unrelated', 'detail']
    assert bank == original
    # Roots move only to the earliest related position, not ahead of all topics.
    bank['questions'].insert(0, {**copy.deepcopy(bank['questions'][1]), 'question_id': 'intro',
                                'concept_id': 'B', 'source_refs': [{'source_id': 'S1', 'locator': 'p.1'}]})
    assert solve(bank)[0] == ['intro', 'root', 'unrelated', 'detail']
    # Explicit ancestors take the same earliest position across concept boundaries.
    explicit = make_bank([('detail', 'D', 'integration', 1, ['parent']),
                          ('unrelated', 'U', 'direct', 2, []),
                          ('parent', 'P', 'mechanism', 40, ['root']),
                          ('root', 'R', 'direct', 50, [])])
    assert solve(explicit)[0] == ['root', 'parent', 'detail', 'unrelated']
    # Never infer the reverse of an authored mechanism-before-direct dependency.
    reverse = make_bank([('direct', 'A', 'direct', 1, ['mechanism']),
                         ('mechanism', 'A', 'mechanism', 2, [])])
    assert solve(reverse)[0] == ['mechanism', 'direct']
    # Cross-concept explicit links must not become an implicit cycle.
    crossing = make_bank([('a0', 'A', 'direct', 1, ['b1']), ('a1', 'A', 'mechanism', 1, []),
                          ('b0', 'B', 'direct', 2, ['a1']), ('b1', 'B', 'mechanism', 2, [])])
    assert len(solve(crossing)[0]) == 4
    # A failed root counts as checked; it does not repeat or gate on a Good grade.
    state = record_review(original, empty_state(), 'root', 'Again', NOW)
    saved = copy.deepcopy(state)
    assert select_daily_question(original, state, EXAM, NOW + 1)['question']['question_id'] == 'unrelated'
    assert state == saved
    sequence, final = solve(original, state)
    assert set(sequence) == {'detail', 'unrelated'} and 'root' not in sequence
    assert lecture_goal(original, final, 'test', NOW + 10)['met']
    assert all(h['rating'] == 'Again' for h in final['history'])
    # Already evaluated/legacy roots are not turned into new cards, even after days.
    legacy = empty_state()
    legacy['items']['root'] = {'reviews': 3, 'due_at': NOW + 10 * DAY_MS}
    before = copy.deepcopy(legacy)
    assert select_daily_question(original, legacy, EXAM, NOW)['question']['question_id'] == 'detail'
    assert legacy == before
    # Catalog views/served IDs alone do not unlock a previously ungraded root.
    viewed = empty_state()
    viewed.update(seen_question_ids=['root'], served={'question_id': 'root'})
    assert select_daily_question(original, viewed, EXAM, NOW)['question']['question_id'] == 'root'
    # Suspended and excluded (absent) roots cannot block the usable bank.
    suspended = empty_state(); suspended['suspended_question_ids'] = ['root']
    assert select_daily_question(original, suspended, EXAM, NOW)['question']['question_id'] == 'detail'
    absent = copy.deepcopy(original); absent['questions'] = absent['questions'][:2]
    assert select_daily_question(absent, empty_state(), EXAM, NOW)['question']['question_id'] == 'detail'
    # One shared policy in batch; a later lecture cannot infer links from duplicate concept IDs.
    other = make_bank([('other', 'A', 'direct', 1, [])])
    entries = [{'key': ('test', rid), 'bank': b, 'state': empty_state(), 'exam': EXAM,
                'row': SimpleNamespace(pages={}), 'goal': lecture_goal(b, empty_state(), rid, NOW)}
               for rid, b in [('one', original), ('two', other)]]
    chosen, result = select_batch_question(entries, NOW)
    assert chosen['key'][1] == 'one' and result['question']['question_id'] == 'root'
    # Completed cards stay in the established weighted extra-study pool.
    learned = final
    with patch('app.study_engine.ordering.random.choices', side_effect=lambda pool, **kw: [pool[-1]]) as draw:
        select_extra_question(original, learned, EXAM, NOW + 10)
        assert draw.called
    # No implicit prerequisite/state metadata is written into the authored bank.
    connection_order(original, {'root', 'detail', 'unrelated'})
    assert original['questions'][0]['prerequisites'] == []
    print('PASS: related roots first, slide anchors, explicit precedence, no cycles, Again progress, legacy/view distinction, batch and state preservation')


if __name__ == '__main__':
    main()

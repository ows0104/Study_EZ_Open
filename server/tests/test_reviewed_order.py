"""Semantic placement overrides background evidence without rewriting learning history."""
import copy
from types import SimpleNamespace
from tests.test_question_order import make_bank, solve, NOW, EXAM
from app.study_engine import empty_state, record_review
from app.study_engine.connections import connection_order
from app.study_engine.ordering import question_slide
from app.study_engine.daily_queue import select_daily_question, select_extra_question, lecture_goal
from app.study_engine.batch import select_batch_question
from app.bank_validation.schema import schema_errors, QUESTION


def main():
    # An introductory citation must not drag a comparison of later mechanisms
    # (or those mechanisms themselves) into the introduction.
    bank = make_bank([('comparison','overview','discrimination',5,['anticoag','lysis']),
                      ('intro','overview','direct',5,[]),
                      ('intermediate','other','direct',12,[]),
                      ('anticoag','heparin','mechanism',18,[]),
                      ('lysis','tpa','mechanism',26,[]),
                      ('late-detail','overview','direct',28,[])])
    for q in bank['questions']:
        q['learning_page'] = int(q['source_refs'][0]['locator'][2:])
    bank['questions'][0]['source_refs'].append({'source_id':'S1','locator':'p.26'})
    bank['questions'][0]['learning_page'] = 26
    original = copy.deepcopy(bank)
    assert question_slide(bank['questions'][0], {'comparison':[5,26,28]}) == 26
    order, state = solve(bank, pages={'comparison':[5,26,28]})
    # The established direction-spacing rule can interpose the remaining detail.
    assert order == ['intro','intermediate','anticoag','lysis','late-detail','comparison'], order
    assert bank == original
    dependencies, _ = connection_order(bank, set(order))
    assert dependencies['comparison'] == {'anticoag','lysis'}
    assert not dependencies['intro']
    assert len(order) == len(set(order)) == len(bank['questions'])
    # Previously rated roots, including Again, stay rated; reads never migrate state.
    learned = record_review(bank, empty_state(), 'anticoag', 'Again', NOW)
    before = copy.deepcopy(learned)
    select_daily_question(bank, learned, EXAM, NOW+1)
    assert learned == before
    assert select_extra_question(bank, empty_state(), EXAM, NOW)['question']['question_id'] == 'intro'
    entry = {'key':('test','lecture'),'bank':bank,'state':empty_state(),'exam':EXAM,
             'row':SimpleNamespace(pages={'comparison':[5,26,28]}),
             'goal':lecture_goal(bank,empty_state(),'test',NOW)}
    _, selected = select_batch_question([entry], NOW)
    assert selected['question']['question_id'] == 'intro'
    # Legacy banks retain their established fallback; malformed metadata is not used.
    legacy = copy.deepcopy(bank)
    for q in legacy['questions']:q.pop('learning_page')
    assert question_slide(legacy['questions'][0]) == 5
    for invalid in (True,0,-1,'26',2.5):
        question = {**bank['questions'][0],'learning_page':invalid}
        assert question_slide(question) == 5
    assert any('learning_page' in error for error in schema_errors(
        {**bank['questions'][0],'learning_page':'26'}, QUESTION))
    print('PASS: reviewed placement, explicit cross-concept dependencies, evidence retained, '
          'single/batch/extra, Again progress, learner state unchanged and legacy fallback')


if __name__ == '__main__':main()

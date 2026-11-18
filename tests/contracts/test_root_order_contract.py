import copy

import pytest

from studyez_contracts.roots import order as o


def pox():
    steps = ['세포 진입', '초기 전사', '추가 탈외피', 'DNA 복제', '후기 유전자 발현', '입자 조립', '방출']
    return {'question_id': 'Q174', 'format': 'list', 'question': '폭스바이러스의 복제주기 단계는?',
            'answer': '; '.join(steps), 'answer_units': steps, 'options': [], 'correct_option_ids': [], 'source_refs': []}


def document(*questions):
    return {'revision': 'rev-1', 'bank_snapshot': {'questions': list(questions)}}


def test_eligible_only_for_plain_lists_with_three_or_more_units():
    assert o.eligible(pox())
    two = {**pox(), 'answer_units': ['세포 진입', '방출'], 'answer': '세포 진입; 방출'}
    assert not o.eligible(two)
    assert not o.eligible({**pox(), 'format': 'basic'})
    assert not o.eligible({**pox(), 'options': [{'id': 'A', 'text': 'x'}]})
    dup = {**pox(), 'answer_units': ['방출', '방출', 'DNA 복제']}
    assert not o.eligible(dup)
    labeled = {**pox(), 'answer_units': ['1단계: 진입', '2단계: 전사', '3단계: 복제']}
    assert not o.eligible(labeled)   # 「항목: 값」 묶음 문항은 선지 묶음으로 푼다


def test_entry_round_trips_through_validate_and_attachable():
    q = pox()
    row = o.entry(q, list(range(7)), '복제주기는 진입부터 방출까지 차례로 일어난다')
    asset = {'schema': o.SCHEMA, 'revision': 'rev-1', 'questions': {'Q174': row}, 'not_ordered': {}}
    o.validate(asset, document(q))
    assert o.attachable(asset, 'rev-1', q) == row
    assert o.attachable(asset, 'rev-2', q) is None


@pytest.mark.parametrize('order', [[0, 1, 2], [0, 0, 1, 2, 3, 4, 5], [1, 2, 3, 4, 5, 6, 7], 'abc', [True, 1, 2, 3, 4, 5, 6]])
def test_order_must_be_a_permutation_of_the_units(order):
    with pytest.raises(ValueError):
        o.entry(pox(), order, '근거')


def test_changed_question_text_detaches_the_row():
    q = pox()
    row = o.entry(q, list(range(7)), '근거')
    edited = copy.deepcopy(q)
    edited['answer'] = '세포 진입; 방출; DNA 복제'
    assert o.attachable({'schema': o.SCHEMA, 'revision': 'r', 'questions': {'Q174': row}, 'not_ordered': {}}, 'r', edited) is None


def test_broken_asset_is_treated_as_missing():
    assert o.attachable({'schema': o.SCHEMA, 'revision': 'r', 'questions': []}, 'r', pox()) is None
    assert o.attachable(None, 'r', pox()) is None


def test_correct_follows_the_judged_order_not_the_stored_order():
    q = pox()
    row = o.entry(q, [0, 1, 3, 2, 4, 5, 6], '근거')
    assert [c['text'] for c in o.correct(q, row)][2:4] == ['DNA 복제', '추가 탈외피']


def test_shuffled_is_stable_per_seed_never_the_answer_and_hides_order_in_ids():
    q = pox()
    row = o.entry(q, list(range(7)), '근거')
    right = [c['id'] for c in o.correct(q, row)]
    seen = set()
    for day in range(30):
        a = o.shuffled(q, row, f'u|Q174|day{day}')
        assert a == o.shuffled(q, row, f'u|Q174|day{day}')
        ids = [c['id'] for c in a]
        assert sorted(ids) == sorted(right) and ids != right
        seen.add(tuple(ids))
    assert len(seen) > 20
    assert all(i.startswith('o') and len(i) == 9 for i in right)


def test_three_unit_shuffle_still_differs_from_answer():
    q = {**pox(), 'answer_units': ['A', 'B', 'C'], 'answer': 'A; B; C'}
    row = o.entry(q, [0, 1, 2], '근거')
    right = [c['id'] for c in o.correct(q, row)]
    for day in range(50):
        assert [c['id'] for c in o.shuffled(q, row, str(day))] != right

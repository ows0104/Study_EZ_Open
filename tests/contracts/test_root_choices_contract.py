import copy

import pytest

from studyez_contracts.roots import choices as c


def basic():
    return {'question_id': 'Q1', 'format': 'basic', 'question': '발진티푸스의 매개체는?', 'answer': '몸니',
            'answer_units': ['몸니'], 'options': [], 'correct_option_ids': [], 'source_refs': []}


def listed():
    return {'question_id': 'Q2', 'format': 'list', 'question': '숙주 측 인자를 열거하라.', 'answer': '연령; 영양; 기저질환',
            'answer_units': ['연령', '영양', '기저질환'], 'options': [], 'correct_option_ids': [], 'source_refs': []}


def wrong(*texts):
    return [{'text': t, 'why_wrong': f'{t}는 다른 질환의 매개체다'} for t in texts]


def document(*questions):
    return {'revision': 'rev-1', 'bank_snapshot': {'questions': list(questions)}}


def test_basic_entry_has_the_answer_exactly_once_and_hides_nothing_else():
    row = c.entry(basic(), wrong('털진드기', '쥐벼룩', '참진드기'))
    assert len(row['choices']) == 4 and len(row['correct_ids']) == 1
    right = next(ch for ch in row['choices'] if ch['id'] in row['correct_ids'])
    assert right['text'] == '몸니'
    assert set(row['wrong_reasons']) == {ch['id'] for ch in row['choices']} - set(row['correct_ids'])
    assert c.entry_errors(basic(), row) == []


def test_order_is_stable_and_does_not_follow_input_order():
    first = c.entry(basic(), wrong('털진드기', '쥐벼룩', '참진드기'))
    second = c.entry(basic(), wrong('참진드기', '털진드기', '쥐벼룩'))
    assert [ch['text'] for ch in first['choices']] == [ch['text'] for ch in second['choices']]


def test_list_entry_keeps_every_answer_unit():
    row = c.entry(listed(), wrong('성별', '직업'))
    texts = {ch['text'] for ch in row['choices'] if ch['id'] in row['correct_ids']}
    assert texts == {'연령', '영양', '기저질환'} and len(row['choices']) == 5


@pytest.mark.parametrize('bad,message', [
    (wrong('털진드기', '쥐벼룩'), '오답 3~4개'),
    (wrong('털진드기', '쥐벼룩', ' 몸 니 '), '정답과 같거나'),
    (wrong('털진드기', '쥐벼룩', '쥐 벼룩'), '정답과 같거나'),
    ([{'text': '털진드기', 'why_wrong': ''}, *wrong('쥐벼룩', '참진드기')], '오답 이유'),
])
def test_bad_wrong_choices_are_rejected(bad, message):
    assert any(message in e for e in c.wrong_errors(basic(), bad))
    with pytest.raises(ValueError):
        c.entry(basic(), bad)


def test_choice_that_only_repeats_the_question_is_rejected():
    q = basic()
    q['question'] = '쥐벼룩이 아닌, 발진티푸스의 매개체는?'
    assert any('질문에 그대로' in e for e in c.wrong_errors(q, wrong('털진드기', '쥐벼룩', '참진드기')))


def test_only_plain_recall_formats_are_eligible():
    assert c.eligible(basic()) and c.eligible(listed())
    for change in ({'format': 'cloze'}, {'format': 'mcq'}, {'options': [{'id': 'A', 'text': 'x'}]}, {'answer_units': [], 'answer': ''}):
        assert not c.eligible({**basic(), **change})
    assert not c.eligible({**listed(), 'answer_units': [str(i) for i in range(9)]})
    assert not c.eligible({**listed(), 'answer_units': ['연령']})


def test_validate_and_attachable_follow_revision_and_question_text():
    q = basic()
    asset = {'schema': c.SCHEMA, 'revision': 'rev-1', 'questions': {'Q1': c.entry(q, wrong('털진드기', '쥐벼룩', '참진드기'))}, 'skipped': {}}
    c.validate(asset, document(q))
    assert c.attachable(asset, 'rev-1', q) is asset['questions']['Q1']
    assert c.attachable(asset, 'rev-2', q) is None
    assert c.attachable(asset, 'rev-1', {**q, 'answer': '쥐벼룩', 'answer_units': ['쥐벼룩']}) is None
    assert c.attachable(asset, 'rev-1', listed()) is None
    assert c.attachable({'schema': c.SCHEMA, 'revision': 'rev-1', 'questions': 'broken'}, 'rev-1', q) is None
    with pytest.raises(ValueError):
        c.validate({**asset, 'revision': 'other'}, document(q))
    tampered = copy.deepcopy(asset)
    tampered['questions']['Q1']['correct_ids'] = [next(iter(tampered['questions']['Q1']['wrong_reasons']))]
    with pytest.raises(ValueError):
        c.validate(tampered, document(q))


def test_distractor_pool_uses_other_answers_only():
    other = {**basic(), 'question_id': 'Q3', 'answer': '털진드기', 'answer_units': ['털진드기', '몸니']}
    assert c.distractor_pool([basic(), other, listed()], basic()) == ['털진드기', '연령', '영양', '기저질환']

"""순서 맞추기 판정 생성기(quizbank/root_order.py). 모델은 가짜 호출로 대신한다."""
import json

from quizbank import root_order
from studyez_contracts.roots import order as contract

STEPS = ['세포 진입', '초기 전사', '추가 탈외피', 'DNA 복제', '후기 유전자 발현', '입자 조립', '방출']


def _q(qid, units, fmt='list', question='?'):
    return {'question_id': qid, 'format': fmt, 'question': question, 'answer': '; '.join(units), 'answer_units': list(units),
            'options': [], 'correct_option_ids': [], 'source_refs': []}


def _document():
    return {'revision': 'rev-1', 'bank_snapshot': {'questions': [
        _q('Q174', STEPS, question='폭스바이러스의 복제주기 단계는?'),
        _q('Q2', ['접촉', '비말', '공기'], question='전파 경로 세 가지는?'),
        _q('Q3', ['세포 진입', '방출'], question='두 단계'),          # 단위 2개: 대상 아님
        _q('Q4', ['몸니'], fmt='basic'),                              # 형식: 대상 아님
        _q('Q5', ['A', 'B', 'C'], question='차례는?'),
    ]}}


def _fake(judgments, seen=None):
    def call(prompt, schema, work, model, label):
        data = json.loads((work / 'input.json').read_text(encoding='utf-8'))
        if seen is not None:
            seen.append(data)
        return {'judgments': judgments}, {'seconds': 1, 'cost_usd': 0, 'input_tokens': 1, 'output_tokens': 1, 'models': ['fake']}
    return call


def test_only_eligible_lists_are_sent(tmp_path):
    seen = []
    root_order.build(_document(), tmp_path, call=_fake([], seen))
    sent = [q['question_id'] for q in seen[0]['questions']]
    assert sent == ['Q174', 'Q2', 'Q5']
    assert seen[0]['questions'][0]['units'][3] == {'index': 3, 'text': 'DNA 복제'}


def test_judgments_become_a_valid_asset(tmp_path):
    asset = root_order.build(_document(), tmp_path, call=_fake([
        {'question_id': 'Q174', 'ordered': True, 'order': list(range(7)), 'basis': '복제주기는 차례로 일어난다'},
        {'question_id': 'Q2', 'ordered': False, 'order': [], 'basis': '서로 독립된 경로'},
        {'question_id': 'Q5', 'ordered': True, 'order': [0, 0, 1], 'basis': '순열이 아님'},   # 코드가 버린다
        {'question_id': 'Q999', 'ordered': True, 'order': [0, 1, 2], 'basis': '판에 없는 문항'},
    ]))
    assert set(asset['questions']) == {'Q174'}
    assert asset['not_ordered'] == {'Q2': '서로 독립된 경로'}
    assert 'Q5' in asset['dropped']
    assert asset['counts'] == {'eligible': 3, 'ordered': 1, 'notOrdered': 1, 'dropped': 1, 'failedBatches': 0}
    saved = json.loads((tmp_path / 'order.json').read_text(encoding='utf-8'))
    contract.validate(saved, _document())


def test_missing_judgment_is_recorded_not_guessed(tmp_path):
    asset = root_order.build(_document(), tmp_path, call=_fake([
        {'question_id': 'Q174', 'ordered': True, 'order': list(range(7)), 'basis': '근거'}]))
    assert asset['dropped'] == {'Q2': '판정 없음', 'Q5': '판정 없음'}


def test_failed_call_keeps_everything_out(tmp_path):
    def broken(*args, **kwargs):
        raise RuntimeError('세션 한도')
    asset = root_order.build(_document(), tmp_path, call=broken)
    assert asset['questions'] == {} and asset['counts']['failedBatches'] == 1
    assert '세션 한도' in asset['dropped']['Q174']


def test_same_input_is_not_called_twice(tmp_path):
    calls = []

    def call(prompt, schema, work, model, label):
        calls.append(1)
        return {'judgments': []}, {'seconds': 1, 'cost_usd': 0, 'input_tokens': 1, 'output_tokens': 1, 'models': ['fake']}
    root_order.build(_document(), tmp_path, call=call)
    root_order.build(_document(), tmp_path, call=call)
    assert len(calls) == 1

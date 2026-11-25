"""긴 나열 답 판정(quizbank/root_long_list.py, studyez_contracts/roots/long_list.py). 모델은 가짜 호출로 대신한다."""
import json

import fitz
import pytest

from quizbank import root_long_list
from studyez_contracts.roots import long_list as contract

LUPUS = ['항-dsDNA 항체', '항-Sm 항체', '항핵항체(ANA)', '보체 C3/C4', '항-Ro/SS-A 항체', '직접 Coombs 검사',
         '매독혈청검사(VDRL)', 'aPTT', 'ESR', '혈색소', '백혈구', '혈소판', '소변검사', '혈청 크레아티닌']
DIPHTHERIA = ['고열', '오한', '피로감', '두통', '인후통', '발성장애', '기침', '호흡곤란', '청색증', '임파선염', '림프절 비대']


def _q(qid, units, page, fmt='list', question='?'):
    return {'question_id': qid, 'format': fmt, 'question': question, 'answer': '; '.join(units), 'answer_units': list(units),
            'source_refs': [{'source_id': 'S1', 'locator': f'physical PDF page {page}'}]}


def _document():
    return {'revision': 'auto-abc', 'title': '시험', 'bank_snapshot': {'questions': [
        _q('Q090', LUPUS, 2, question='SLE의 검사 항목은?'),
        _q('Q122', DIPHTHERIA, 1, question='디프테리아의 증상은?'),
        _q('Q3', ['A', 'B', 'C'], 1),                      # 5개 이하: 대상 아님
        _q('Q4', DIPHTHERIA, 1, fmt='cloze'),             # 형식: 대상 아님
    ]}}


def _generation(tmp_path):
    gen = tmp_path / 'gen'
    gen.mkdir()
    doc = fitz.open()
    for n in range(3):
        doc.new_page().insert_text((72, 72), f'page {n + 1}')
    doc.save(gen / 'source-0.pdf')
    (gen / 'packet.json').write_text(json.dumps({'sources': [{'id': 'S1'}]}), encoding='utf-8')
    return gen


def _grouped(**over):
    row = {'question_id': 'Q090', 'kind': 'grouped', 'keep_group': 1, 'representatives': [], 'representative_basis': '',
           'branches': [], 'note': '', 'basis': '31쪽 두 열 표',
           'groups': [{'name': '진단이나 중증도 판단에 도움', 'unit_indices': list(range(14)), 'page': 2},
                      {'name': '질병활성도 판단에 도움', 'unit_indices': [0, 3, 8, 9, 10, 11, 12, 13], 'page': 2}]}
    return {**row, **over}


def _ungrouped(**over):
    row = {'question_id': 'Q122', 'kind': 'ungrouped', 'groups': [], 'keep_group': -1, 'representatives': [4, 0],
           'representative_basis': '「주로 인후통과 열로 증상이 시작됨」 밑줄', 'note': '', 'basis': '한 줄 나열',
           'branches': [{'axis': '전신', 'unit_indices': [0, 1, 2, 3]},
                        {'axis': '인후·기도', 'unit_indices': [4, 5, 6, 7, 8]},
                        {'axis': '림프절', 'unit_indices': [9, 10]}]}
    return {**row, **over}


def _fake(judgments, seen=None):
    def call(prompt, schema, work, model, label, images=None):
        data = json.loads((work / 'input.json').read_text(encoding='utf-8'))
        if seen is not None:
            seen.append((data, [p.name for p in images or []]))
        return {'judgments': judgments}, {'seconds': 1, 'cost_usd': 0, 'input_tokens': 1, 'output_tokens': 1, 'models': ['fake']}
    return call


def test_only_long_lists_are_sent_with_their_pages(tmp_path):
    seen = []
    root_long_list.build(_document(), tmp_path / 'out', generation_dir=_generation(tmp_path), call=_fake([], seen))
    data, images = seen[0]
    assert [q['question_id'] for q in data['questions']] == ['Q090', 'Q122']
    assert data['questions'][0]['units'][13] == {'index': 13, 'text': '혈청 크레아티닌'}
    assert data['questions'][0]['pages'][0]['page'] == 2
    assert len(images) == 2 and all(name.endswith('.png') for name in images)


def test_judgments_are_checked_and_previewed(tmp_path):
    result = root_long_list.build(_document(), tmp_path / 'out', generation_dir=_generation(tmp_path),
                                  call=_fake([_grouped(), _ungrouped()]))
    assert result['counts'] == {'eligible': 2, 'grouped': 1, 'ungrouped': 1, 'unfixable': 0, 'dropped': 0, 'failedBatches': 0}
    assert result['judgments']['Q090']['keep_group'] == 1
    assert result['previews']['Q122'].splitlines() == [
        '**대표: 인후통, 고열**', '갈래:', '  전신 — 고열, 오한, 피로감, 두통',
        '  인후·기도 — 인후통, 발성장애, 기침, 호흡곤란, 청색증', '  림프절 — 임파선염, 림프절 비대']
    saved = json.loads((tmp_path / 'out' / 'long-list.json').read_text(encoding='utf-8'))
    assert saved['schema'] == contract.SCHEMA


def test_missing_judgment_is_recorded_not_guessed(tmp_path):
    result = root_long_list.build(_document(), tmp_path / 'out', generation_dir=_generation(tmp_path), call=_fake([_grouped()]))
    assert result['dropped'] == {'Q122': '판정 없음'}


Q090 = _q('Q090', LUPUS, 2)
Q122 = _q('Q122', DIPHTHERIA, 1)


@pytest.mark.parametrize('bad, reason', [
    (_grouped(groups=[_grouped()['groups'][0]]), '둘 미만'),
    (_grouped(groups=[{'name': 'a', 'unit_indices': [0, 1], 'page': 2}, {'name': 'b', 'unit_indices': [2], 'page': 2}]), '다 덮지'),
    (_grouped(groups=[{'name': 'a', 'unit_indices': list(range(14)), 'page': 9}, {'name': 'b', 'unit_indices': [2], 'page': 2}]), '근거 쪽 밖'),
    (_grouped(keep_group=5), 'keep_group'),
    (_grouped(representatives=[0]), '대표·갈래'),
    (_grouped(groups=[{'name': 'a', 'unit_indices': [0, 14], 'page': 2}, {'name': 'b', 'unit_indices': [1], 'page': 2}]), '없는 단위'),
])
def test_grouped_checks(bad, reason):
    with pytest.raises(ValueError, match=reason):
        contract.check(Q090, bad)


@pytest.mark.parametrize('bad, reason', [
    (_ungrouped(representative_basis=''), '강조 근거'),
    (_ungrouped(representatives=list(range(11))), '답 전체'),
    (_ungrouped(branches=[{'axis': '전신', 'unit_indices': list(range(11))}]), '하나뿐'),
    (_ungrouped(branches=[{'axis': '전신', 'unit_indices': [0, 1, 2, 3]}, {'axis': '나머지 증상', 'unit_indices': list(range(4, 11))}]), '쓸 수 없는 이름'),
    (_ungrouped(branches=[{'axis': '전신', 'unit_indices': [0, 1, 2, 3, 4]}, {'axis': '인후', 'unit_indices': list(range(4, 11))}]), '정확히 한 번'),
    (_ungrouped(groups=[{'name': 'x', 'unit_indices': [0], 'page': 1}]), '원본 묶음'),
    (_ungrouped(kind='other'), 'kind'),
    (_ungrouped(basis=''), '근거가 비었음'),
])
def test_ungrouped_checks(bad, reason):
    with pytest.raises(ValueError, match=reason):
        contract.check(Q122, bad)


def test_ungrouped_without_representatives_or_branches_is_kept_as_unfixable():
    row = contract.check(Q122, _ungrouped(representatives=[], representative_basis='', branches=[]))
    assert row['fixable'] is False


def test_representatives_without_branches_show_the_rest_on_one_line():
    row = contract.check(Q122, _ungrouped(branches=[]))
    assert contract.answer_preview(Q122, row).splitlines() == [
        '**대표: 인후통, 고열**', '그 밖에: 오한, 피로감, 두통, 발성장애, 기침, 호흡곤란, 청색증, 임파선염, 림프절 비대']

import copy
import json
from pathlib import Path

import fitz
import pytest

from quizbank import explain, run, web_audit
from quizbank.schema import without_retired
from quizbank.validate import validate_dropping
from quizbank.session import SessionError


@pytest.fixture
def bank():
    raw=json.loads((Path(__file__).parent/'fixtures/bank_261002_02.json').read_text(encoding='utf-8'))
    return without_retired(validate_dropping(raw,['S1','S2'])[0])


def annotations(bank):
    return {'annotations':[{'question_id':q['question_id'],'verdict':'ok','note':'',
        'option_explanations':[{'option_id':o['id'],'text':f'{o["id"]} 판정 근거'} for o in q['options']],
        'ox_explanation':'판정의 근거와 올바른 내용' if q['format']=='ox' else '',
        'pool_explanations':[{'pool_id':p['pool_id'],'candidate_id':c['candidate_id'],
            'true_explanation':'참인 근거','false_explanation':'거짓인 부분과 정정'}
            for p in q['option_pools'] for c in p['candidates']]}
        for q in explain.targets(bank)]}


def test_annotations_preserve_authored_content_and_original_bank(bank):
    original=copy.deepcopy(bank)
    result, report=explain.apply(bank,annotations(bank))
    assert bank==original
    for before,after in zip(bank['questions'],result['questions']):
        for key in before:
            if key not in ('option_explanations','answer_units','option_pools'):
                assert after[key]==before[key],key
        assert after['answer_units'][:len(before['answer_units'])]==before['answer_units']
    assert len(result['questions'])==len(bank['questions'])
    assert not report['requiresRevision']
    assert explain.enabled('1.32') and not explain.enabled('1.31')


@pytest.mark.parametrize('change',['missing_question','duplicate_question','missing_option','unknown_option','missing_ox'])
def test_incomplete_or_wrongly_linked_annotations_are_rejected(bank,change):
    data=annotations(bank)
    if change=='missing_question':data['annotations'].pop()
    elif change=='duplicate_question':data['annotations'].append(data['annotations'][0])
    elif change=='missing_ox':next(r for r in data['annotations'] if r['ox_explanation'])['ox_explanation']=''
    else:
        row=next(r for r in data['annotations'] if r['option_explanations'])
        if change=='missing_option':row['option_explanations'].pop()
        else:row['option_explanations'][0]['option_id']='UNKNOWN'
    with pytest.raises(SessionError):explain.apply(bank,data)


def test_wrong_answer_is_reported_and_not_changed(bank):
    data=annotations(bank)
    data['annotations'][0].update(verdict='wrong',note='정답에 오류가 있음')
    updated, report=explain.apply(bank,data)
    assert report['requiresRevision']
    assert [q['answer'] for q in updated['questions']]==[q['answer'] for q in bank['questions']]


def test_ox_authored_reasons_are_preserved_and_reworded_explanations_do_not_accumulate(bank):
    q = next(q for q in bank['questions'] if q['format'] == 'ox')
    q['answer_units'] = ['기존의 핵심 정정 근거']
    data = annotations(bank)
    updated, _ = explain.apply(bank, data)
    row = next(r for r in data['annotations'] if r['question_id'] == q['question_id'])
    row['ox_explanation'] = '표현을 바꾼 동일 해설'
    repeated, _ = explain.apply(updated, data)
    assert next(q2 for q2 in repeated['questions'] if q2['question_id'] == q['question_id'])['answer_units'] == q['answer_units']


def test_ox_without_a_reason_gets_it_once(bank):
    q = next(q for q in bank['questions'] if q['format'] == 'ox')
    q['answer_units'] = [q['answer']]
    data = annotations(bank)
    updated, _ = explain.apply(bank, data)
    row = next(r for r in data['annotations'] if r['question_id'] == q['question_id'])
    row['ox_explanation'] = '새 표현의 판단 근거'
    repeated, _ = explain.apply(updated, data)
    assert next(q2 for q2 in repeated['questions'] if q2['question_id'] == q['question_id'])['answer_units'] == [q['answer'], '판정의 근거와 올바른 내용']


def test_pool_texts_and_answers_are_immutable_while_explanations_are_added(bank):
    q=next(q for q in bank['questions'] if q['format']=='mcq')
    q['option_pools']=[{'pool_id':'P1','select_count':2,'correct_when':'true','candidates':[
        {'candidate_id':'C1','true_text':'참 문장','false_text':'거짓 문장','true_explanation':'',
         'false_explanation':'','source_refs':[{'source_id':'S1','locator':'p1'}]}]}]
    updated,_=explain.apply(bank,annotations(bank))
    changed=next(x for x in updated['questions'] if x['question_id']==q['question_id'])['option_pools'][0]['candidates'][0]
    assert changed['true_text']=='참 문장' and changed['false_text']=='거짓 문장'
    assert changed['true_explanation']=='참인 근거' and changed['false_explanation']=='거짓인 부분과 정정'


@pytest.mark.parametrize('verdict,do_review,blocked',[('ok',True,False),('wrong',True,True),('ok',False,True),('pool_missing',True,True)])
def test_pipeline_adds_explanations_before_auditing_and_keeps_a_revision_block(bank,tmp_path,monkeypatch,verdict,do_review,blocked):
    from tests.quizbank.test_web_audit import RAW,report
    pdf=tmp_path/'a.pdf'
    with fitz.open() as doc:
        doc.new_page().insert_text((40,40),'Source fact');doc.save(pdf)
    raw=tmp_path/'raw.md';raw.write_text(RAW,encoding='utf-8')
    monkeypatch.setattr(run.organize,'organize',lambda *a,**k:(copy.deepcopy(bank),{}))
    monkeypatch.setattr(run.slides,'render',lambda *a,**k:([],[]))
    def unavailable(*a,**k):
        raise run.repair.RepairError('미해결 정답')
    monkeypatch.setattr(run.repair,'repair',unavailable)
    data=annotations(bank);data['annotations'][0].update(verdict='ok' if verdict=='pool_missing' else verdict,note='오류 확인' if verdict=='wrong' else '')
    def author(original,*a,**k):
        updated,checked=explain.apply(original,data)
        return updated,checked,{}
    monkeypatch.setattr(explain,'write',author)
    def audit(updated,*a,**k):
        assert any(q['option_explanations'] for q in updated['questions'])
        return web_audit.shape_report(report(updated),updated,web_audit.parse_points(RAW),1),[]
    monkeypatch.setattr(web_audit,'inspect',audit)
    monkeypatch.setattr(run.review,'review',lambda *a,**k:({'counts':{'ok':len(bank['questions']),'doubt':0,'wrong':0},'missing':[],
        'requiresRevision':verdict=='pool_missing'},{}))
    result=run.run(raw,pdf,'강의','lecture',[{'id':'S1'},{'id':'S2'}],tmp_path/'out',prompt_version='1.32',do_review=do_review)
    assert result['coverage']['status']=='verified' and result['requiresRevision']==blocked

import copy
import hashlib
from pathlib import Path
import fitz
import pytest
from quizbank import exam_focus
from quizbank.session import SessionError
from server.app.bank_validation.slide_focus import question_hash
from server.app.bank_validation.evidence_resolution import primary_references, status

def targets():
    return [{'question_id': 'Q1', 'question': {'question': 'A?', 'answer': 'B'}, 'candidates': [
        {'id': 'earlier', 'filename': 'a.png', 'page': 2, 'pdfFilename': 'exam.pdf', 'references': ['2020 1번']},
        {'id': 'proof', 'filename': 'b.png', 'page': 9, 'pdfFilename': 'exam.pdf', 'references': ['2022 4번']}]}]

def test_core_is_the_cli_selected_evidence_page_and_never_the_first_reference():
    original = targets()
    before = copy.deepcopy(original)
    raw = {'selections': [{'question_id': 'Q1', 'mode': 'single', 'reason': '실제 정답 지면',
                          'pages': [{'id': 'proof', 'evidence': '표에서 A→B를 확인'}]}]}
    result = exam_focus.shape(raw, original)
    assert result['Q1']['pages'][0]['filename'] == 'b.png'
    assert result['Q1']['pages'][0]['page'] == 9
    assert original == before
    for bad in [[], raw['selections'] * 2, [{**raw['selections'][0], 'pages': [{'id':'missing','evidence':'x'}]}],
                [{**raw['selections'][0], 'mode':'linked'}]]:
        with pytest.raises(SessionError):
            exam_focus.shape({'selections': bad}, original)

def test_embedded_exam_is_rendered_as_exam_media_with_visible_issue_metadata(tmp_path, monkeypatch):
    pdf = tmp_path / 'notes.pdf'
    with fitz.open() as doc:
        doc.new_page().insert_text((30, 30), '2022 Q4 Answer B')
        doc.save(pdf)
    q = {'question_id':'Q1', 'question':'A?', 'answer':'B', 'source_refs':[]}
    digest = hashlib.sha256(pdf.read_bytes()).hexdigest()
    focus = {'sourceSha256': digest, 'questions': {'Q1': {'questionHash': question_hash(q), 'base': {
        'mode':'unresolved', 'unresolved_cause':'exam_only', 'reason':'첨부 기출에서만 확인',
        'exam_pages':[{'source_id':'self','page':1,'evidence':'A→B'}]}}}}
    def select(rows, out, model):
        assert Path(rows[0]['candidates'][0]['image']).is_file()
        raw = {'selections':[{'question_id':'Q1','mode':'single','reason':'실제 기출 한 장',
                            'pages':[{'id': rows[0]['candidates'][0]['id'], 'evidence':'정답 B'}]}]}
        return exam_focus.shape(raw, rows), []
    monkeypatch.setattr(exam_focus, 'select', select)
    before = copy.deepcopy(q)
    resolution, _ = exam_focus.resolve({'questions':[q]}, focus, {}, {'self':pdf}, tmp_path, 'demo')
    refs = primary_references(resolution, q)
    assert len(refs)==1 and refs[0]['embedded'] and refs[0]['pdfFilename']=='notes.pdf'
    assert '_jbembedded' in refs[0]['filename']
    assert status(resolution,q)['category']=='exam_only'
    assert q==before

def test_source_issue_notices_do_not_need_or_promote_an_image(tmp_path):
    q={'question_id':'Q1','question':'A?','answer':'B'}
    focus={'questions':{'Q1':{'questionHash':question_hash(q),'base':{
        'mode':'unresolved','unresolved_cause':'source_conflict','reason':'원문은 A, 답은 B'}}}}
    resolution,_=exam_focus.resolve({'questions':[q]},focus,{}, {},tmp_path,'demo')
    assert status(resolution,q)['category']=='source_conflict'
    assert primary_references(resolution,q)==[]
    assert status(resolution,{**q,'answer':'C'}) is None

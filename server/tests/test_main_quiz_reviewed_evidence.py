"""Main-Quiz evidence at Quiz Bank level: core slides, exam pages, exam core, status — bound to revision and source hashes."""
import json
import uuid
from types import SimpleNamespace
from unittest.mock import patch
from tests.root_support import setup
client, user, SessionLocal = setup()
from app.models import Asset
from app.root_learning import evidence as ev
from app.routes.root_learning import revealed_answer
from studyez_contracts.bank.slide_focus import question_hash

NOTES, EXAM = 'a' * 64, 'b' * 64


def q(qid, refs, **extra):
    return {'question_id': qid, 'question': qid + '?', 'answer': 'A', 'answer_units': ['A'], 'format': 'basic',
            'source_refs': refs, 'options': [], 'correct_option_ids': [], 'conflict_id': '', **extra}


Q1 = q('Q1', [{'source_id': 'S1', 'locator': 'physical PDF page 2, 3'}, {'source_id': 'S2', 'locator': '2023 김지은 79번 ④'}])
Q2 = q('Q2', [{'source_id': 'S1', 'locator': 'physical PDF page 4'}, {'source_id': 'S2', 'locator': 'physical PDF page 3'}],
       conflict_id='CF1')
Q3 = q('Q3', [{'source_id': 'S1', 'locator': 'p.5'}, {'source_id': 'EXT', 'locator': 'textbook'}])
Q4 = q('Q4', [{'source_id': 'S1', 'locator': 'physical PDF page 6'}])
document = {'bank_source': 'standalone', 'bank_snapshot': {'questions': [Q1, Q2, Q3, Q4],
            'source_conflicts': [{'conflict_id': 'CF1', 'description': 'S1과 S2가 다르다.'}]},
            'review': {'sources': [{'source_id': 'S1', 'sha256': NOTES, 'kind': 'notes', 'page_count': 10},
                                   {'source_id': 'S2', 'sha256': EXAM, 'kind': 'exam', 'page_count': 6}]}}
doc = SimpleNamespace(document=document, subject='test', run_id='demo', revision='rev-1')
generation = SimpleNamespace(web_dispatch=None, result={}, packet={'sources': [
    {'id': 'S1', 'sha256': NOTES, 'filename': 'notes.pdf', 'snapshotKey': 'frozen/notes.pdf', 'contentType': 'application/pdf'},
    {'id': 'S2', 'sha256': EXAM, 'filename': 'exam.pdf (감염성 질환의 병리 1·2, 2020–2025)', 'snapshotKey': 'frozen/exam.pdf'}]})
exam_ref = lambda page, year, no: {'year': year, 'number': no, 'page': page, 'filename': f'x_p{page}.png',  # noqa: E731
                                   'pdfFilename': 'exam.pdf', 'sourceSha256': EXAM}
evidence = {
    'schema': 'root-evidence/1', 'revision': 'rev-1', 'sources': {'S1': NOTES, 'S2': EXAM}, 'notesSource': 'S1',
    'slideFocus': {'version': 2, 'questions': {
        'Q1': {'questionHash': question_hash(Q1), 'base': {'mode': 'single', 'reason': 'r', 'slides': [{'page': 3, 'evidence': 'e'}]}},
        'Q2': {'questionHash': question_hash(Q2), 'base': {'mode': 'unresolved', 'reason': '족보에만 있다',
               'unresolved_cause': 'exam_only', 'slides': []}},
        'Q3': {'questionHash': 'stale', 'base': {'mode': 'single', 'reason': 'r', 'slides': [{'page': 9, 'evidence': 'e'}]}}}},
    'jokboPages': {'version': 1, 'questions': {
        'Q1': {'questionHash': question_hash(Q1), 'locators': {'2023 김지은 79번 ④': [exam_ref(2, '2023', '79')]}, 'unresolved': []},
        'Q2': {'questionHash': question_hash(Q2), 'locators': {'physical PDF page 3': [
            {**exam_ref(3, '2021', '16'), 'references': ['2021 16번']}]}, 'unresolved': []}}},
    'evidenceResolution': {'version': 1, 'questions': {
        'Q2': {'questionHash': question_hash(Q2), 'base': {'category': 'exam_only', 'reason': '족보에만 있다', 'missingClaim': '',
               'examCore': {'mode': 'single', 'reason': 'r', 'pages': [{**exam_ref(3, '2021', '16'), 'evidence': 'e'}]}}},
        # 강의록에 첨부된 기출(같은 강의 PDF 9쪽)이 족보 핵심인 경우
        'Q4': {'questionHash': question_hash(Q4), 'base': {'category': 'exam_only', 'reason': '첨부 기출에만', 'missingClaim': '',
               'examCore': {'mode': 'single', 'reason': 'r', 'pages': [{'page': 9, 'filename': 'x_emb.png', 'pdfFilename': 'notes.pdf',
                            'sourceSha256': NOTES, 'references': ['첨부 기출'], 'embedded': True, 'evidence': 'e'}]}}}}},
}
storage = {'body': json.dumps(evidence).encode()}


def answer_for(question):
    with patch('app.root_learning.evidence.ObjectStorage') as cls:
        cls.return_value.presign_download.return_value = 'https://example.invalid/signed.pdf'
        cls.return_value.get_bytes.side_effect = lambda key: storage['body']
        with SessionLocal() as db:
            out = {}
            ev.attach_evidence(db, doc, question, generation, out)
            return out


# 근거 파일이 없으면 지금처럼 인용 쪽만, S2는 족보 칸으로 간다.
plain = answer_for(Q1)
assert [(s['sourceId'], s['page']) for s in plain['pdfSlides']] == [('S1', 2), ('S1', 3)]
assert [(s['page'], s['references']) for s in plain['jokboPdfSlides']] == [] and 'slideFocusKnown' not in plain
plain2 = answer_for(Q2)
assert [(s['sourceId'], s['page']) for s in plain2['jokboPdfSlides']] == [('S2', 3)] and 'evidenceStatus' not in plain2

with SessionLocal() as db:
    db.add(Asset(id=str(uuid.uuid4()), subject='test', run_id='demo', kind='root_evidence', filename='rev-1.json',
                 object_key='lectures/test/demo/root_evidence/rev-1.json', size_bytes=1)); db.commit()

a1 = answer_for(Q1)
assert a1['slideFocusKnown'] is True
assert [(s['page'], s['primary']) for s in a1['pdfSlides']] == [(3, True), (2, False)]  # 핵심 먼저
assert [(s['page'], s['references'], s['primary']) for s in a1['jokboPdfSlides']] == [(2, ['2023 79번'], False)]
assert all(s['proxyPath'].endswith('/sources/S2?sha=' + EXAM) for s in a1['jokboPdfSlides'])
assert 'evidenceStatus' not in a1

a2 = answer_for(Q2)
assert [(s['page'], s['references'], s['primary']) for s in a2['jokboPdfSlides']] == [(3, ['2021 16번'], True)]
assert a2['evidenceStatus'] == {'category': 'exam_only', 'reason': '족보에만 있다', 'missingClaim': '', 'primaryAvailable': True}

a4 = answer_for(Q4)
assert [(s['sourceId'], s['page']) for s in a4['pdfSlides']] == [('S1', 6)]
assert [(s['sourceId'], s['page'], s['references'], s['primary']) for s in a4['jokboPdfSlides']] == [('S1', 9, ['첨부 기출'], True)]

# 문항 hash가 다른 선택(Q3)은 쓰지 않는다 — 9쪽을 끌어오지 않는다.
a3 = answer_for(Q3)
assert [(s['page'], s['primary']) for s in a3['pdfSlides']] == [(5, False)]

# 개인 수정본은 원본 선택을 핵심으로 표시하지 않는다.
edited = {**Q1, 'question': '바꾼 발문', 'personalEdited': True}
assert not any(s['primary'] for s in answer_for(edited)['pdfSlides'])

# 다른 판·다른 원본 지문의 근거는 버린다.
for broken in ({**evidence, 'revision': 'rev-0'}, {**evidence, 'sources': {'S1': '0' * 64}}, {'schema': 'other'}):
    ev._EVIDENCE.clear(); storage['body'] = json.dumps(broken).encode()
    stale = answer_for(Q2)
    assert 'slideFocusKnown' not in stale and 'evidenceStatus' not in stale
    assert [s['primary'] for s in stale['jokboPdfSlides']] == [False]
ev._EVIDENCE.clear(); storage['body'] = b'not json'
assert 'slideFocusKnown' not in answer_for(Q1)

# 자료 충돌·EXT는 판 문서에서 읽는다.
with patch('app.root_learning.evidence.ObjectStorage'), SessionLocal() as db:
    with patch('app.routes.root_learning.active_generation', return_value=None):
        assert revealed_answer(db, doc, Q2)['conflict'] == 'S1과 S2가 다르다.'
        assert revealed_answer(db, doc, Q3)['external'] is True
        assert revealed_answer(db, doc, Q1)['conflict'] == '' and revealed_answer(db, doc, Q1)['external'] is False
print('PASS: reviewed core slides, exam pages and core, evidence status, hash/revision binding, conflict and EXT')

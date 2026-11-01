"""의미에 따른 핵심 근거 한 장·연계 근거·실제 인용한 족보 지면을 확인한다."""
import copy
from unittest.mock import patch

from tests.test_bank import example_bank
from app.bank_validation.slide_focus import question_hash, selected_pages, external_filename
from app.bank_validation.jokbo_pages import references
from app.bank_validation.evidence_resolution import status as evidence_status, primary_references
from app.database import Base, SessionLocal, engine
from app.models import Asset, QuizBank, SLIDE_KINDS
from app.routes.bank import _slides, _jokbo_slides, _answer


def main():
    bank = example_bank()
    q = bank['questions'][0]
    q['source_refs'] = [{'source_id': 'S1', 'locator': 'p1–3'}, {'source_id': 'S2', 'locator': '2023 52'}]
    report = {'version': 2, 'questions': {'Q1': {'questionHash': question_hash(q), 'candidates': {},
        'base': {'mode': 'single', 'reason': '직접 정답 근거', 'slides': [{'page': 8, 'evidence': '답의 핵심 설명'}]}}}}
    assert selected_pages(report, q, [1, 2, 3, 8]) == {8}
    assert selected_pages({}, q, [1, 2]) == set()
    assert selected_pages(report, {**q, 'answer': 'changed'}, [8]) == set()
    assert selected_pages(report, q, [1, 2, 3]) == set()
    assert selected_pages(report, q, [8], {**q, 'personalEdited': True, 'answer': 'private'}) == set()
    linked = copy.deepcopy(report)
    linked['questions']['Q1']['base'].update(mode='linked', slides=[{'page': 3, 'evidence': '한쪽'}, {'page': 8, 'evidence': '다른쪽'}])
    assert selected_pages(linked, q, [3, 8]) == {3, 8}
    assert selected_pages(linked, q, [3]) == set()
    jokbo = {'version': 1, 'questions': {'Q1': {'questionHash': question_hash(q), 'locators': {
        '2023 52': [{'year': '2023', 'number': '52', 'page': 63, 'filename': 'jokbo.png', 'pdfFilename': 'exam.pdf',
                    'question': {'reference': '2023 52번', 'stem': 'Original question?', 'options': ['First', 'Second']}}]}}}}
    assert len(references(jokbo, q)) == 1
    assert references(jokbo, {**q, 'answer': 'changed'}) == []
    assert references(jokbo, q, {**q, 'source_refs': []}) == []
    row = QuizBank(subject='slides', run_id='demo', build_id='slides-test', bank=bank,
                   pages={'Q1': [1, 2, 3]}, validation={'pass': True, 'slideFocus': report, 'jokboPages': jokbo})
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        for page in [1, 2, 3, 8]:
            db.add(Asset(id=f'slide-{page}', subject='slides', run_id='demo', kind=SLIDE_KINDS['bank'],
                         slide_no=page, filename=f'{page}.png', object_key=f'slides/{page}.png'))
        db.add(Asset(id='jokbo', subject='slides', run_id='demo', kind=SLIDE_KINDS['bank'],
                     filename='jokbo.png', object_key='slides/jokbo.png'))
        db.add(Asset(id='other', subject='other', run_id='demo', kind=SLIDE_KINDS['bank'],
                     filename='jokbo.png', object_key='other/jokbo.png'))
        db.commit()
        with patch('app.routes.bank_api.presentation.ObjectStorage') as storage:
            storage.return_value.presign_download.side_effect = lambda key: f'https://example.test/{key}'
            slides = _slides(db, row, 'Q1')
            actual = _jokbo_slides(db, row, q)
            answer = _answer(db, row, q)
        assert [s['page'] for s in slides] == [1, 2, 3, 8]
        assert [s['page'] for s in slides if s['primary']] == [8]
        assert actual == answer['jokboSlides']
        assert actual[0]['references'] == ['2023 52번'] and actual[0]['page'] == 63
        assert actual[0]['url'].endswith('/slides/jokbo.png')
        assert actual[0]['questions'][0]['stem'] == 'Original question?'
        assert actual[0]['questions'][0]['options'] == ['First', 'Second']
        # Same physical page number in two different PDFs must never collide.
        foreign = external_filename('demo', 'other', 'a' * 64, 8)
        row.validation = {**row.validation, 'slideFocus': {'version': 3, 'sourceFilename': 'own.pdf',
            'sources': {'other': {'runId': 'other', 'sourceFilename': 'other.pdf', 'sourceSha256': 'a' * 64, 'pageCount': 9}},
            'questions': {'Q1': {'questionHash': question_hash(q), 'candidates': {}, 'base': {
                'mode': 'linked', 'reason': '각 강의에 필수 근거가 분산', 'slides': [
                    {'page': 8, 'evidence': '첫 관계'}, {'source_id': 'other', 'page': 8, 'evidence': '둘째 관계'}]}}}}}
        db.add(Asset(id='foreign-wrong-scope', subject='other', run_id='demo', kind=SLIDE_KINDS['bank'],
                     filename=foreign, object_key='private/foreign.png'))
        db.commit()
        with patch('app.routes.bank_api.presentation.ObjectStorage') as storage:
            storage.return_value.presign_download.side_effect = lambda key: f'https://example.test/{key}'
            absent = _slides(db, row, 'Q1')
            assert not any(s['primary'] for s in absent), 'Incomplete linked proof must stay unconfirmed'
            assert all('private/' not in s['url'] for s in absent)
            db.add(Asset(id='foreign-copied', subject='slides', run_id='demo', kind=SLIDE_KINDS['bank'],
                         filename=foreign, object_key='slides/copied-foreign.png'))
            db.commit()
            found = _slides(db, row, 'Q1')
            core = [s for s in found if s['primary']]
            assert [(s['sourceId'], s['page']) for s in core] == [('self', 8), ('other', 8)]
            assert core[-1]['sourceFilename'] == 'other.pdf' and core[-1]['url'].endswith('copied-foreign.png')
            private = _slides(db, row, 'Q1', {**q, 'personalEdited': True, 'answer': 'mine'})
            assert not any(s['primary'] for s in private)
            core_ref = {'filename': 'core-exam.png', 'pdfFilename': 'exam.pdf', 'page': 47,
                        'references': ['2022 4번'], 'evidence': '실제 정답이 있는 지면', 'embedded': True}
            resolution = {'version': 1, 'questions': {'Q1': {'questionHash': question_hash(q), 'base': {
                'category': 'exam_only', 'reason': '강의 본문에 없고 기출에서 정답을 확인',
                'examCore': {'mode': 'single', 'reason': '이 한 지면에 핵심 답이 있음', 'pages': [core_ref]}}}}}
            row.validation = {**row.validation, 'evidenceResolution': resolution}
            db.add(Asset(id='exam-core-copy', subject='slides', run_id='demo', kind=SLIDE_KINDS['bank'],
                         filename='core-exam.png', object_key='slides/core-exam.png'))
            db.commit()
            actual = _answer(db, row, q)
            assert actual['evidenceStatus']['category'] == 'exam_only' and actual['evidenceStatus']['primaryAvailable']
            assert [s['page'] for s in actual['jokboSlides'] if s['primary']] == [47]
            assert len(actual['jokboSlides']) == 2, 'Normal references remain available without being promoted'
            assert next(s for s in actual['jokboSlides'] if s['primary'])['embedded']
            assert primary_references(resolution, {**q, 'answer': 'changed'}) == []
            assert evidence_status(resolution, q, {**q, 'personalEdited': True}) is None
            assert evidence_status(resolution, q, {**q, 'choice_variant': {'poolId': 'P'}}) is None
            base = resolution['questions']['Q1']['base']
            base['examCore'].update(mode='linked', pages=[core_ref, {**core_ref, 'filename': 'missing.png', 'page': 48}])
            assert not any(s['primary'] for s in _jokbo_slides(db, row, q)), 'Missing part of an exam proof is never a complete core'
            assert not _answer(db, row, q)['evidenceStatus']['primaryAvailable']
            for category in ('partial_support', 'source_conflict', 'unsupported', 'uncertain'):
                base.update(category=category, reason='자료 내 판단 이유', missingClaim='빠진 핵심')
                actual = _answer(db, row, q)
                assert actual['evidenceStatus'] == {'category': category, 'reason': '자료 내 판단 이유', 'missingClaim': '빠진 핵심'}
                assert not any(s['primary'] for s in actual['jokboSlides'])
    print('PASS: semantic single and linked evidence, no arbitrary fallback, stale and private edits, selected page outside old citations, exact exam page, lecture isolation')


if __name__ == '__main__':
    main()

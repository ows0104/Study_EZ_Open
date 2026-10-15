"""의미에 따른 핵심 근거 한 장·연계 근거·실제 인용한 족보 지면을 확인한다."""
import copy
from unittest.mock import patch

from tests.test_bank import example_bank
from app.bank_validation.slide_focus import question_hash, selected_pages
from app.bank_validation.jokbo_pages import references
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
        '2023 52': [{'year': '2023', 'number': '52', 'page': 63, 'filename': 'jokbo.png', 'pdfFilename': 'exam.pdf'}]}}}}
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
        with patch('app.routes.bank.ObjectStorage') as storage:
            storage.return_value.presign_download.side_effect = lambda key: f'https://example.test/{key}'
            slides = _slides(db, row, 'Q1')
            actual = _jokbo_slides(db, row, q)
            answer = _answer(db, row, q)
        assert [s['page'] for s in slides] == [1, 2, 3, 8]
        assert [s['page'] for s in slides if s['primary']] == [8]
        assert actual == answer['jokboSlides']
        assert actual[0]['references'] == ['2023 52번'] and actual[0]['page'] == 63
        assert actual[0]['url'].endswith('/slides/jokbo.png')
    print('PASS: semantic single and linked evidence, no arbitrary fallback, stale and private edits, selected page outside old citations, exact exam page, lecture isolation')


if __name__ == '__main__':
    main()

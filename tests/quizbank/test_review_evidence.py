"""review-evidence/1: the /4 item review names the notes pages of each answer and the notes citations follow them
in code, with no model call (docs/changes/2026-11-11-evidence-from-citations)."""
import copy
import hashlib
import json

import fitz
import pytest

from quizbank import connection_generate as g
from studyez_contracts.roots import generation_v4 as v4
from studyez_contracts.roots.automation import packet_hash, validate_result as consume
from tests.quizbank.test_root_generation_v4 import Model, packet as base_packet

PAGES = 3


def notes_pdf(path):
    doc = fitz.open()
    for i in range(PAGES):
        doc.new_page().insert_text((72, 72), f'Synthetic notes page {i + 1}')
    doc.save(path)
    doc.close()
    return path


def packet(tmp_path, cited='PDF 물리 2쪽'):
    """The /4 synthetic packet with a three-page notes PDF; every intake question cites `cited`."""
    p = base_packet(tmp_path)
    pdf = notes_pdf(tmp_path / 'notes.pdf')
    body = pdf.read_bytes()
    p['sources'][0].update(filename='notes.pdf', localPath=str(pdf.resolve()), sizeBytes=len(body),
                           sha256=hashlib.sha256(body).hexdigest(), originalKey='notes.pdf', snapshotKey='frozen/notes.pdf')
    for q in p['intakeBank']['bank']['questions']:
        q['source_refs'] = [{'source_id': 'S1', 'locator': cited}]
    p['inputHash'] = packet_hash(p)
    return p


class EvidenceModel(Model):
    """Reviews name page 1 for Q1 (its citation says 2) and page 2 for the rest; `bad` breaks one review's evidence."""

    def __init__(self, pages=None, bad=None, **kw):
        super().__init__(**kw)
        self.pages, self.bad = pages or {'Q1': [1]}, bad

    def __call__(self, stage, ctx, material, model):
        value, info = super().__call__(stage, ctx, material, model)
        if stage.startswith('v4-review'):
            for r in value['reviews']:
                if 'evidence_source' not in ctx:
                    continue
                pages = self.pages.get(r['question_id'], [2])
                r['evidence'] = {'mode': 'single' if len(pages) == 1 else 'linked', 'reason': 'Synthetic proof',
                                 'slides': [{'page': p, 'evidence': f'Synthetic line on page {p}'} for p in pages]}
            if self.bad:
                value['reviews'][0]['evidence'] = self.bad
        return value, info


def run(tmp_path, model=None, **kw):
    tmp_path.mkdir(exist_ok=True)
    p = packet(tmp_path, **kw)
    model = model or EvidenceModel()
    return p, model, g.run(p, tmp_path / 'out', invoke=model)


def notes_refs(q):
    return [r['locator'] for r in q['source_refs'] if r['source_id'] == 'S1']


def test_a_new_run_reviews_with_notes_pages_and_aligns_the_wrong_citation(tmp_path):
    p, model, result = run(tmp_path)
    assert consume(result, p) == result['document']
    review_inputs = [ctx for stage, ctx in model.inputs.items() if stage.startswith('v4-review')]
    assert review_inputs and all(ctx['evidence_source'] == {'source_id': 'S1', 'page_count': PAGES} for ctx in review_inputs)
    meta = result['manifest']
    assert meta['reviewEvidence'] == {'policy': v4.REVIEW_EVIDENCE, 'sourceId': 'S1'}
    # Q1 cited page 2 but is proved on page 1; Q003 (added) cited a paragraph and is proved on page 2.
    assert [r['question_id'] for r in meta['citationAlignments']] == ['Q1', 'Q003']
    assert meta['citationAlignments'][0]['before'] == [{'source_id': 'S1', 'locator': 'PDF 물리 2쪽'}]
    final = {q['question_id']: q for q in result['document']['bank_snapshot']['questions']}
    assert notes_refs(final['Q1']) == ['PDF 물리 1쪽'] and notes_refs(final['Q2']) == ['PDF 물리 2쪽']
    assert all('evidence' in r for r in meta['itemReviews'])
    # No model stage was added for the alignment.
    assert not any('align' in c for c in model.calls)


def test_the_medical_review_reads_the_aligned_bank(tmp_path):
    p, model, result = run(tmp_path)
    q1 = next(q for q in model.inputs['medical-0']['bank']['questions'] if q['question_id'] == 'Q1')
    assert notes_refs(q1) == ['PDF 물리 1쪽']


def test_linked_evidence_cites_each_page_and_keeps_other_sources(tmp_path):
    tmp_path.mkdir(exist_ok=True)
    p = packet(tmp_path)
    q1 = p['intakeBank']['bank']['questions'][0]
    q1['source_refs'] = [{'source_id': 'S2', 'locator': 'exam 3'}, {'source_id': 'S1', 'locator': 'PDF 물리 2쪽'}]
    bank, records = v4.align_citations(p['intakeBank']['bank'], [
        {'question_id': 'Q1', 'evidence': {'mode': 'linked', 'reason': 'x', 'slides': [{'page': 1, 'evidence': 'a'}, {'page': 3, 'evidence': 'b'}]}},
        {'question_id': 'Q2', 'evidence': {'mode': 'unresolved', 'reason': 'x', 'slides': []}}], 'S1')
    assert bank['questions'][0]['source_refs'] == [{'source_id': 'S2', 'locator': 'exam 3'},
                                                   {'source_id': 'S1', 'locator': 'PDF 물리 1쪽'},
                                                   {'source_id': 'S1', 'locator': 'PDF 물리 3쪽'}]
    # Unresolved evidence changes nothing.
    assert [r['question_id'] for r in records] == ['Q1'] and bank['questions'][1] == p['intakeBank']['bank']['questions'][1]


def test_a_text_notes_source_reviews_without_pages(tmp_path):
    from tests.quizbank.test_root_generation_v4 import run as plain_run
    p, model, result = plain_run(tmp_path)
    assert 'reviewEvidence' not in result['manifest'] and 'citationAlignments' not in result['manifest']
    assert not any('evidence_source' in ctx for stage, ctx in model.inputs.items() if stage.startswith('v4-review'))


@pytest.mark.parametrize('bad, message', [
    ({'mode': 'single', 'reason': 'x', 'slides': [{'page': 1, 'evidence': 'a'}, {'page': 2, 'evidence': 'b'}]}, 'do not fit mode single'),
    ({'mode': 'single', 'reason': 'x', 'slides': [{'page': PAGES + 1, 'evidence': 'a'}]}, 'outside the notes'),
    ({'mode': 'unresolved', 'reason': 'x', 'slides': [{'page': 1, 'evidence': 'a'}]}, 'do not fit mode unresolved'),
])
def test_review_evidence_that_does_not_fit_stops_the_stage(tmp_path, bad, message):
    with pytest.raises(ValueError, match=message):
        run(tmp_path, EvidenceModel(bad=bad))


class NoEvidence(EvidenceModel):
    def __call__(self, stage, ctx, material, model):
        value, info = super().__call__(stage, ctx, material, model)
        if stage.startswith('v4-review'):
            for r in value['reviews']:
                r.pop('evidence', None)
        return value, info


def test_a_review_without_evidence_is_refused_when_the_input_asks_for_it(tmp_path):
    with pytest.raises(ValueError, match='missing or unknown fields'):
        run(tmp_path, NoEvidence())


def tamper(result, edit):
    result = copy.deepcopy(result)
    edit(result)
    return result


def test_the_consumer_refuses_a_citation_change_outside_the_alignment(tmp_path):
    # Nothing is fixed, so Q1 is an intake question whose only change is the recorded alignment.
    p, model, result = run(tmp_path, EvidenceModel(design_doubt=()))
    assert not result['manifest']['fixes'] and result['manifest']['citationAlignments'][0]['question_id'] == 'Q1'

    def other_page(r):
        r['document']['bank_snapshot']['questions'][1]['source_refs'] = [{'source_id': 'S1', 'locator': 'PDF 물리 3쪽'}]
    def drop_record(r):
        r['manifest']['citationAlignments'] = []
    def wrong_after(r):
        r['manifest']['citationAlignments'][0]['after'] = [{'source_id': 'S1', 'locator': 'PDF 물리 3쪽'}]
    def text_change(r):
        r['manifest']['citationAlignments'][0]['before'] = [{'source_id': 'S1', 'locator': 'PDF 물리 2쪽'}, {'source_id': 'S2', 'locator': 'x'}]
    def records_without_policy(r):
        r['manifest'].pop('reviewEvidence')
    for edit in (other_page, drop_record, wrong_after, text_change, records_without_policy):
        with pytest.raises(ValueError):
            consume(tamper(result, edit), p)


def test_an_older_v4_result_still_validates_without_review_evidence(tmp_path):
    from tests.quizbank.test_root_generation_v4 import run as plain_run
    p, model, result = plain_run(tmp_path)
    assert consume(result, p) == result['document']
    with pytest.raises(ValueError, match='citation alignments without review evidence'):
        consume(tamper(result, lambda r: r['manifest'].__setitem__('citationAlignments', [])), p)


class ContextRepair(EvidenceModel):
    """The clinical-context step sends Q2 back once; its re-review must still name notes pages (review 2026-11-11:
    the evidence source was overwritten by the repair notes)."""

    def __call__(self, stage, ctx, material, model):
        if stage == 'v4-context-0':
            self.calls.append(stage)
            self.inputs[stage] = ctx
            return {'conflicts': [{'conflict_id': c['conflict_id'], 'status': 'consistent', 'reason': 'Synthetic'} for c in ctx['conflicts']],
                    'questions': [{'question_id': 'Q2', 'reason': 'Synthetic history line'}], 'unrecorded': []}, {}
        return super().__call__(stage, ctx, material, model)


def test_a_context_repair_re_review_keeps_the_notes_pages(tmp_path):
    model = ContextRepair(pages={'Q1': [1], 'Q2': [3]}, design_doubt=())
    p, model, result = run(tmp_path, model)
    assert 'v4-review-context-1' in model.calls
    assert model.inputs['v4-review-context-1']['evidence_source'] == {'source_id': 'S1', 'page_count': PAGES}
    assert consume(result, p) == result['document']
    final = {q['question_id']: q for q in result['document']['bank_snapshot']['questions']}
    assert notes_refs(final['Q2']) == ['PDF 물리 3쪽']


def test_the_consumer_refuses_review_evidence_that_is_not_a_recorded_judgment(tmp_path):
    p, model, result = run(tmp_path, EvidenceModel(design_doubt=()))

    def forge(r):
        row = next(x for x in r['manifest']['itemReviews'] if x['question_id'] == 'Q2')
        row['evidence'] = {'mode': 'single', 'reason': 'x', 'slides': [{'page': 3, 'evidence': 'forged'}]}
    with pytest.raises(ValueError, match='not a recorded judgment'):
        consume(tamper(result, forge), p)

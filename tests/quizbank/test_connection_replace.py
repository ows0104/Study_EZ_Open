"""unplaced-only/1 (docs/changes/2026-11-15-unplaced-replace): a published review-relations/1 run whose question Q2
no goal took is placed again, through the synthetic /4 model of test_map_relation_guard."""
import copy
import json

import pytest

from quizbank import connection_generate as g
from studyez_contracts.roots import generation_v4 as v4
from studyez_contracts.roots import task_fingerprints
from studyez_contracts.roots.automation import packet_hash, validate_result as consume
from tests.quizbank.test_map_relation_guard import LateModel, DuplicateLateModel
from tests.quizbank.test_place_by_review import run_v1
from tests.quizbank.test_root_generation_v4 import tasks

LATE = ['v4-supplement-late', 'v4-supplement-normalize-late', 'v4-coverage-supplement-late', 'v4-map-check-late']


def published(tmp_path, model=None):
    old_packet, _, old = run_v1(tmp_path / 'old', model or LateModel())
    previous = tmp_path / 'old' / 'out'
    (previous / 'packet.json').write_text(json.dumps(old_packet, ensure_ascii=False), encoding='utf-8')
    packet = copy.deepcopy(old_packet)
    packet.update(revision='auto-new', generationId='new', restartOf='old', replacePublished=True, unplacedOnly=True,
                  restartReason='못 붙은 문항 재배치', carrySources=carry_sources(old))
    packet['inputHash'] = packet_hash(packet)
    return previous, old, packet


def carry_sources(old):
    """The server's packet field (2026-11-15-replace-carry-records R2): an older revision whose first task's question
    differed, then the published one."""
    doc = old['document']
    prints = task_fingerprints(doc)
    tasks_ = [{'direction_id': t['direction_id'], 'fingerprint': prints[t['task_id']]} for t in doc['tasks']]
    older = copy.deepcopy(tasks_); older[0]['fingerprint'] = '0' * 64
    return [{'revision': 'auto-older', 'tasks': older}, {'revision': doc['revision'], 'tasks': tasks_}]


def test_an_unplaced_question_gets_a_late_goal_and_nothing_else_changes(tmp_path):
    previous, old, packet = published(tmp_path)
    assert [u['question_id'] for u in old['manifest']['unplacedQuestions']] == ['Q2'] and 'Q2' not in dict(tasks(old))
    model = LateModel()
    result = g.run(packet, tmp_path / 'new', invoke=model, unplaced_of=previous)
    assert consume(result, packet) == result['document']
    # Only the late stages call the model; the late supplement is offered no existing point.
    assert model.calls == LATE
    assert model.inputs['v4-supplement-late']['points'] == []
    placed = dict(tasks(result))
    assert placed['Q2'].startswith('DQ') and set(tasks(old)) <= set(tasks(result))
    meta = result['manifest']
    assert meta['unplacedQuestions'] == [] and meta['placement'] == {'policy': v4.REVIEW_PLACEMENT2}
    record = meta['unplacedOnly']
    assert record['policy'] == 'unplaced-only/1' and record['previousRevision'] == old['document']['revision']
    assert (record['unplacedBefore'], record['unplacedAfter'], record['lateQuestions']) == (1, 0, ['Q2'])
    # Questions, the medical review and the item reviews are the old ones; the map only grows.
    assert result['document']['bank_snapshot']['questions'] == old['document']['bank_snapshot']['questions']
    assert result['medical'] == old['medical'] and meta['itemReviews'] == old['manifest']['itemReviews']
    assert {t['target_id'] for t in old['brief']['targets']} < {t['target_id'] for t in result['brief']['targets']}
    names = [s['name'] for s in meta['stages']]
    assert names[:len(old['manifest']['stages'])] == [s['name'] for s in old['manifest']['stages']] and names[-4:] == LATE
    assert json.loads((previous / 'result.json').read_text(encoding='utf-8')) == old
    # 2026-11-15-replace-carry-records R1: every direction of the published revision continues its history; the older
    # revision only where an unchanged question remains.
    links = result['document']['equivalences']
    old_dirs = sorted({t['direction_id'] for t in old['document']['tasks']})
    assert [l['from_direction'] for l in links if l['revision'] == old['document']['revision']] == old_dirs
    assert all(l['from_direction'] == l['to_direction'] for l in links)
    n = len(old['document']['tasks'])
    assert [(r['revision'], r['tasks'], r['of']) for r in record['carry']] == [('auto-older', n - 1, n), (old['document']['revision'], n, n)]


def test_without_earlier_fingerprints_nothing_runs(tmp_path):
    previous, _, packet = published(tmp_path)
    del packet['carrySources']
    packet['inputHash'] = packet_hash(packet)
    model = LateModel()
    with pytest.raises(Exception, match='carrySources'):
        g.run(packet, tmp_path / 'new', invoke=model, unplaced_of=previous)
    assert model.calls == []


def test_a_second_run_reuses_the_late_stages(tmp_path):
    previous, _, packet = published(tmp_path)
    first = g.run(packet, tmp_path / 'new', invoke=LateModel(), unplaced_of=previous)
    (tmp_path / 'new' / 'result.json').unlink()
    model = LateModel()
    again = g.run(packet, tmp_path / 'new', invoke=model, unplaced_of=previous)
    assert model.calls == [] and again['document'] == first['document']


def test_a_question_still_off_the_map_is_reported_not_dropped(tmp_path):
    previous, old, packet = published(tmp_path)
    result = g.run(packet, tmp_path / 'new', invoke=LateModel(keep_off=True), unplaced_of=previous)
    assert consume(result, packet) == result['document']
    assert [u['question_id'] for u in result['manifest']['unplacedQuestions']] == ['Q2']
    assert result['document']['bank_snapshot']['questions'] == old['document']['bank_snapshot']['questions']


def test_a_late_duplicate_of_answer_is_refused(tmp_path):
    previous, _, packet = published(tmp_path)
    with pytest.raises(ValueError, match='late supplement: input.points is empty'):
        g.run(packet, tmp_path / 'new', invoke=DuplicateLateModel(), unplaced_of=previous)


def test_another_lecture_input_is_refused(tmp_path):
    previous, _, packet = published(tmp_path)
    packet['title'] = 'Another lecture'
    packet['inputHash'] = packet_hash(packet)
    with pytest.raises(ValueError, match='강의 입력'):
        g.run(packet, tmp_path / 'new', invoke=LateModel(), unplaced_of=previous)


# ---------------------------------------------------------------- R4: unsupported relations are repaired
from tests.quizbank.test_root_generation_v4 import Model  # noqa: E402


class UnknownR1Model(Model):
    """The first map check leaves R1 unknown (its condition misses the subject), so neither D1 question is a task;
    the repair rewrites R1's condition and the re-check supports it. `bad_fix`: the repair also edits a goal."""

    def __init__(self, bad_fix=False, condition='Synthetic subject named'):
        self.condition = condition
        # The item reviews name no relation for Q1/Q2 (R1 is not a supported relation they may name).
        super().__init__(relations={'Q1': [], 'Q2': [], 'Q003': [('R2', 'whole')]})
        self.bad_fix = bad_fix

    def __call__(self, stage, ctx, material, model):
        if stage == 'v4-brief-fix-late':
            self.calls.append(stage)
            self.inputs[stage] = ctx
            fixed = copy.deepcopy(ctx['brief'])
            fixed['provenance']['independent_points'] = 'derived'
            next(r for r in fixed['relations'] if r['relation_id'] == 'R1')['condition'] = self.condition
            if self.bad_fix:
                t = fixed['targets'][0]
                key = next(k for k, v in t.items() if type(v) is str and k != 'target_id')
                t[key] += ' (changed goal)'
            return {'brief': fixed, 'map_change_reason': 'Synthetic relation repair'}, {}
        value, info = super().__call__(stage, ctx, material, model)
        if stage == 'v4-map-check-0':
            for r in value['relation_checks']:
                if r['relation_id'] == 'R1':
                    r.update(status='unknown', reason='Synthetic: the subject is missing')
        return value, info


def test_a_question_on_an_unknown_relation_is_placed_after_the_repair(tmp_path):
    previous, old, packet = published(tmp_path, UnknownR1Model())
    assert {'Q1', 'Q2'} & set(dict(tasks(old))) == set()
    model = UnknownR1Model()
    result = g.run(packet, tmp_path / 'new', invoke=model, unplaced_of=previous)
    assert consume(result, packet) == result['document']
    assert model.calls == ['v4-brief-fix-late', 'v4-map-check-fix-late']
    assert [e.split(':')[0] for e in model.inputs['v4-brief-fix-late']['errors']] == ['R1']
    assert {'Q1', 'Q2'} <= set(dict(tasks(result))) and result['manifest']['unplacedQuestions'] == []
    repair = result['manifest']['unplacedOnly']['relationRepair']
    assert repair == {'relations': ['R1'], 'changed': ['R1'], 'supported': ['R1']}
    assert next(r for r in result['brief']['relations'] if r['relation_id'] == 'R1')['condition'] == 'Synthetic subject named'
    assert result['brief']['targets'] == old['brief']['targets']
    assert result['document']['bank_snapshot']['questions'] == old['document']['bank_snapshot']['questions']


def test_a_repair_that_changes_a_goal_is_refused(tmp_path):
    previous, _, packet = published(tmp_path, UnknownR1Model())
    with pytest.raises(ValueError, match='관계 수선: targets'):
        g.run(packet, tmp_path / 'new', invoke=UnknownR1Model(bad_fix=True), unplaced_of=previous)


def test_a_repair_that_drops_the_korean_of_a_relation_is_refused(tmp_path):
    previous, old, packet = published(tmp_path, UnknownR1Model())
    rel = next(r for r in old['brief']['relations'] if r['relation_id'] == 'R1')
    if not any('가' <= ch <= '힣' for ch in str(rel.get('condition') or '')):
        pytest.skip('the synthetic R1 condition has no Korean')
    with pytest.raises(ValueError, match='한국어'):
        g.run(packet, tmp_path / 'new', invoke=UnknownR1Model(condition='English only'), unplaced_of=previous)


def test_korean_check():
    from quizbank.connection_replace import _check_repair
    before = {'relations': [{'relation_id': 'R1', 'from_id': 'C1', 'to_id': 'C2', 'condition': '리노바이러스 수용체'}],
              'concepts': [{'concept_id': 'C1', 'label': '수용체', 'parent_ids': []}, {'concept_id': 'C2', 'label': 'ICAM-1 이용', 'parent_ids': []}]}
    after = copy.deepcopy(before)
    after['relations'][0]['condition'] = 'Rhinovirus binds ICAM-1.'
    with pytest.raises(ValueError, match='한국어'):
        _check_repair(before, {'brief': after}, {'R1'})
    after['relations'][0]['condition'] = 'Rhinovirus의 80% 초과가 ICAM-1에 결합'
    assert _check_repair(before, {'brief': after}, {'R1'})['brief'] == after


def test_a_list_of_names_and_numbers_needs_no_korean():
    """261106_06 PR014 (2026-11-15): the repaired chart row is organism names and percentages."""
    from quizbank.connection_replace import _check_repair, _english
    assert not _english('B. fragilis 25%, Cutibacterium acnes 19%, C. perfringens 6%')
    assert _english('More than 80% of Rhinovirus, and several Coxsackieviruses, bind ICAM-1.')
    before = {'relations': [{'relation_id': 'R1', 'from_id': 'C1', 'to_id': 'C2', 'condition': 'B. fragilis가 최다'}],
              'concepts': [{'concept_id': 'C1', 'label': '분리 빈도', 'parent_ids': []}, {'concept_id': 'C2', 'label': 'B. fragilis가 최다', 'parent_ids': []}]}
    after = copy.deepcopy(before)
    after['relations'][0]['condition'] = after['concepts'][1]['label'] = 'B. fragilis 25%, Cutibacterium acnes 19%'
    assert _check_repair(before, {'brief': after}, {'R1'})['brief'] == after


def test_the_repair_check_runs_inside_the_model_session():
    from runner.root_native_json import v3_check
    before = {'relations': [{'relation_id': 'R1', 'from_id': 'C1', 'to_id': 'C2', 'condition': '리노바이러스 수용체'}],
              'concepts': [{'concept_id': 'C1', 'label': '수용체', 'parent_ids': []}, {'concept_id': 'C2', 'label': 'ICAM-1', 'parent_ids': []}]}
    after = copy.deepcopy(before)
    after['relations'][0]['condition'] = 'Rhinovirus binds ICAM-1.'
    import runner.root_native_json as native
    from studyez_contracts.roots import generation_v3 as v3
    real = v3.check_brief_fix
    v3.check_brief_fix = lambda value, ctx: value   # the shape check is the contract's own; this test is about the repair
    try:
        with pytest.raises(ValueError, match='한국어'):
            v3_check('v4-brief-fix-late', {'brief': before}, {'brief': after}, {'repair': ['R1']})
        assert v3_check('v4-brief-fix-late', {'brief': before}, {'brief': after}, None) == {'brief': after}
    finally:
        v3.check_brief_fix = real


def test_a_supplement_duplicate_must_name_a_point_it_was_shown():
    from quizbank.connection_generate_v4 import check_stage
    value = {'rows': [{'question_id': 'Q1', 'decision': 'duplicate_of', 'duplicate_of': 'P1', 'point': None, 'reason': 'x'}]}
    with pytest.raises(ValueError, match='input.points is empty'):
        check_stage('supplement', value, {'points': []}, {'points_doc': {}}, None)


# ---------------------------------------------------------------- notes-update/1 (docs/changes/2026-11-16-replace-updated-notes)
import hashlib  # noqa: E402

import fitz  # noqa: E402

from quizbank import source_update  # noqa: E402


def notes_pdf(path, lines):
    doc = fitz.open()
    for line in lines:
        doc.new_page().insert_text((72, 72), line)
    doc.save(path)
    doc.close()
    return path


def use_notes(source, path, version):
    body = path.read_bytes()
    source.update(filename=path.name, localPath=str(path.resolve()), sizeBytes=len(body), assetId=version,
                  sha256=hashlib.sha256(body).hexdigest(), originalKey=f'notes/{path.name}', uploadedAt=f'2026-11-1{version}T00:00:00')


class PdfLateModel(LateModel):
    """LateModel whose item reviews name page 2 of the notes PDF (review-evidence/1, as test_review_evidence)."""

    def __call__(self, stage, ctx, material, model):
        value, info = super().__call__(stage, ctx, material, model)
        if stage.startswith('v4-review') and 'evidence_source' in ctx:
            for r in value['reviews']:
                r['evidence'] = {'mode': 'single', 'reason': 'Synthetic proof',
                                 'slides': [{'page': 2, 'evidence': 'Synthetic line on page 2'}]}
        return value, info


def published_pdf(tmp_path, monkeypatch):
    """The published run of a three-page notes PDF whose questions all cite page 2."""
    import tests.quizbank.test_root_generation_v4 as gen_v4
    base = gen_v4.packet

    def with_pdf(path):
        p = base(path)
        use_notes(p['sources'][0], notes_pdf(path / 'notes-v1.pdf', [f'Synthetic notes page {i}' for i in (1, 2, 3)]), 1)
        for q in p['intakeBank']['bank']['questions']:
            q['source_refs'] = [{'source_id': 'S1', 'locator': 'PDF 물리 2쪽'}]
        p['inputHash'] = packet_hash(p)
        return p
    monkeypatch.setattr(gen_v4, 'packet', with_pdf)
    return published(tmp_path, PdfLateModel())


def corrected(tmp_path, packet, lines):
    packet = copy.deepcopy(packet)
    use_notes(packet['sources'][0], notes_pdf(tmp_path / 'notes-v4.pdf', lines), 4)
    packet['inputHash'] = packet_hash(packet)
    return packet


def test_corrected_notes_of_the_same_pages_replace_the_source_and_nothing_else(tmp_path, monkeypatch):
    previous, old, packet = published_pdf(tmp_path, monkeypatch)
    old_page = (previous / 'material' / 'S1-0002.png').read_bytes()
    packet = corrected(tmp_path, packet, ['Synthetic notes page 1', 'Synthetic notes page 2 (corrected)', 'Synthetic notes page 3'])
    result = g.run(packet, tmp_path / 'new', invoke=PdfLateModel(), unplaced_of=previous)
    assert consume(result, packet) == result['document']
    sources = {s['source_id']: s for s in result['document']['review']['sources']}
    assert sources['S1']['sha256'] == packet['sources'][0]['sha256'] and sources['S1']['label'] == 'notes-v4.pdf'
    assert sources['S1']['page_count'] == 3
    v1 = old['brief']['sources'][0]['sha256']
    assert result['document']['replaced_sources'] == [{'source_id': 'S1', 'sha256': v1}]
    # The brief and every judgment stay those of the earlier file (the stage receipts are checked against them).
    assert result['brief']['sources'] == old['brief']['sources']
    update = result['manifest']['unplacedOnly']['sourceUpdate']
    assert update['policy'] == 'notes-update/1'
    assert [(r['source_id'], r['fromFilename'], r['toFilename'], r['changedPages']) for r in update['sources']] == \
        [('S1', 'notes-v1.pdf', 'notes-v4.pdf', [2])]
    cited = {q['question_id'] for q in old['document']['bank_snapshot']['questions']}
    assert {q['question_id'] for q in update['questionsOnChangedPages']} == cited
    assert all(q['pages'] == [2] for q in update['questionsOnChangedPages'])
    # Questions, reviews and the medical review are the previous run's; every task continues its history.
    assert result['document']['bank_snapshot']['questions'] == old['document']['bank_snapshot']['questions']
    assert result['medical'] == old['medical'] and result['manifest']['itemReviews'] == old['manifest']['itemReviews']
    n = len(old['document']['tasks'])
    assert (old['document']['revision'], n, n) in [(r['revision'], r['tasks'], r['of']) for r in result['manifest']['unplacedOnly']['carry']]
    # The material the receipts were made from is not rewritten, here or in the previous run.
    assert (tmp_path / 'new' / 'material' / 'S1-0002.png').read_bytes() == old_page
    assert (previous / 'material' / 'S1-0002.png').read_bytes() == old_page
    # The record must name the files the brief and the packet name.
    bad = copy.deepcopy(result)
    bad['manifest']['unplacedOnly']['sourceUpdate']['sources'][0]['fromSha256'] = '0' * 64
    with pytest.raises(Exception, match='notes update'):
        consume(bad, packet)
    assert json.loads((previous / 'result.json').read_text(encoding='utf-8')) == old


def test_the_same_file_again_is_no_update(tmp_path, monkeypatch):
    previous, _, packet = published_pdf(tmp_path, monkeypatch)
    result = g.run(packet, tmp_path / 'new', invoke=PdfLateModel(), unplaced_of=previous)
    assert 'sourceUpdate' not in result['manifest']['unplacedOnly'] and 'replaced_sources' not in result['document']


def test_notes_with_another_page_count_are_refused(tmp_path, monkeypatch):
    previous, _, packet = published_pdf(tmp_path, monkeypatch)
    packet = corrected(tmp_path, packet, ['Synthetic notes page 1', 'Synthetic notes page 2'])
    model = PdfLateModel()
    with pytest.raises(ValueError, match='쪽 수'):
        g.run(packet, tmp_path / 'new', invoke=model, unplaced_of=previous)
    assert model.calls == []


def test_only_source_files_may_differ():
    notes = {'id': 'S1', 'kind': 'notes_current', 'filename': 'a.pdf', 'sha256': 'a', 'sizeBytes': 1}
    jokbo = {'id': 'S2', 'kind': 'jokbo', 'filename': 'j.pdf', 'sha256': 'j', 'sizeBytes': 1}
    old = {'title': 'T', 'sources': [notes, jokbo]}
    assert source_update.changed_sources(old, copy.deepcopy(old), 'x') == []
    assert source_update.changed_sources(old, {**old, 'sources': [{**notes, 'sha256': 'b', 'filename': 'b.pdf'}, jokbo]}, 'x') == [0]
    with pytest.raises(ValueError, match='강의 입력'):
        source_update.changed_sources(old, {'title': 'U', 'sources': [{**notes, 'sha256': 'b'}, jokbo]}, 'x')
    with pytest.raises(ValueError, match='원본 구성'):
        source_update.changed_sources(old, {**old, 'sources': [notes]}, 'x')
    with pytest.raises(ValueError, match='원본 구성'):
        source_update.changed_sources(old, {**old, 'sources': [{**notes, 'kind': 'notes_prev'}, jokbo]}, 'x')
    with pytest.raises(ValueError, match='족보'):
        source_update.changed_sources(old, {**old, 'sources': [notes, {**jokbo, 'sha256': 'k'}]}, 'x')


def test_a_figure_cropped_from_the_replaced_file_is_accepted():
    """Figures keep the crop and the hash of the file they came from (their content carries the learning history)."""
    import base64
    from studyez_contracts.roots.media import validate_images
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 4, 4), False)
    body = pix.tobytes('png')
    figure = {'source_id': 'S1', 'source_sha256': 'a' * 64, 'page': 2, 'crop': [0, 0, 1, 1], 'width': 4, 'height': 4,
              'sha256': hashlib.sha256(body).hexdigest(), 'png_base64': base64.b64encode(body).decode()}
    bank = {'questions': [{'question_id': 'Q1', 'stimuli': [figure]}]}
    source = {'source_id': 'S1', 'sha256': 'b' * 64, 'page_count': 3}
    with pytest.raises(Exception, match='source/page mismatch'):
        validate_images(bank, [source])
    assert validate_images(bank, [source], replaced={'S1': ['a' * 64]}) == bank
    with pytest.raises(Exception, match='source/page mismatch'):
        validate_images(bank, [source], replaced={'S2': ['a' * 64]})

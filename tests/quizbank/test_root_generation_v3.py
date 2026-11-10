"""root-generation/3 end to end with a synthetic model (docs/changes/2026-11-10-root-generation-3/spec.md)."""
import copy
import json
import re
import sys
from pathlib import Path

import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'contracts'))
import generation_v2_fixture as f
from quizbank import connection_generate as g
from quizbank import connection_generate_v3 as g3
from studyez_contracts.roots import generation_v3 as v3
from studyez_contracts.roots.automation import packet_hash, validate_result as consume

ROOT = Path(__file__).resolve().parents[2]
BASIS = [{'kind': 'learning_objective', 'refs': [{'source_id': 'S1', 'pages': [1]}], 'quote': '', 'reason': 'Objective', 'year': None}]
POINTS = {'schema_version': 'exam-point-extract/3', 'title': 'Synthetic lecture', 'notes': [],
          'notebook_profile': {'legend': '', 'emphasis_style': 'slide', 'reason': 'Synthetic'},
          'points': [{'point_id': 'P1', 'point': 'Synthetic A/B point', 'source_refs': [{'source_id': 'S1', 'pages': [], 'locator': 'synthetic paragraph'}],
                      'importance_basis': BASIS}]}
# Which question answers which goal in this synthetic lecture.
COVERS = {'D1': ('Q1', 'R1'), 'D2': ('Q003', 'R2'), 'DQ001': ('Q2', 'R2')}


def packet(tmp_path):
    p = f.old.packet(tmp_path / 'synthetic.txt')
    bank = f.old.bank()
    for q in bank['questions']:
        q.pop('stimuli', None)
        q['point_ids'] = []
    p.update(points=json.dumps(POINTS, ensure_ascii=False), generationPolicy=v3.POLICY,
             intakeBank={'bank': bank, 'visual_stimuli': [], 'clinical_conflicts': []})
    p['inputHash'] = packet_hash(p)
    return p


def authored(q):
    """A review/fix input question back in authored form."""
    value = {k: copy.deepcopy(v) for k, v in q.items() if k != 'stimuli'}
    return value


class Model:
    def __init__(self, design_doubt=('Q1',), supplement='point'):
        self.calls, self.inputs, self.states = [], {}, {}
        self.design_doubt, self.supplement = set(design_doubt), supplement

    def __call__(self, stage, ctx, material, model):
        self.calls.append(stage)
        if '_check' in ctx:
            self.states[stage] = ctx['_check']
            ctx = {k: v for k, v in ctx.items() if k != '_check'}
        self.inputs[stage] = ctx
        if stage == 'normalize':
            b = f.brief(ctx['sources'])
            b['lecture_id'] = ctx['lecture_id']
            b['points'][0]['point_id'] = 'P1'
            return b, {}
        kind = stage.split('-')[1] if stage.startswith('v3-') else stage
        if stage.startswith('v3-coverage'):
            qids = {q['question_id'] for q in ctx['questions']}
            rows = []
            for goal in ctx['goals']:
                qid, rid = COVERS.get(goal['direction_id'], (None, None))
                if qid in qids:
                    rows.append({'direction_id': goal['direction_id'], 'status': 'covered', 'reason': 'Synthetic whole goal', 'evidence': [{
                        'question_id': qid, 'tested_relation_ids': [rid],
                        'components': [{'component_id': c['component_id'], 'location': 'answer', 'answer_unit_indices': [0], 'reason': 'x'}
                                       for c in goal['components']],
                        'visual_verdict': 'not_applicable', 'reason': 'Synthetic'}]})
                else:
                    rows.append({'direction_id': goal['direction_id'], 'status': 'missing', 'evidence': [], 'reason': 'No whole-goal question'})
            return {'rows': rows}, {}
        if stage.startswith('v3-map-check'):
            return {'relation_checks': [{'relation_id': r['relation_id'], 'status': 'supported', 'reason': 'x'} for r in ctx['relations']],
                    'target_checks': [{'target_id': t['target_id'], 'status': 'consistent', 'reason': 'x'} for t in ctx['targets']],
                    'direction_checks': [{'direction_id': gl['direction_id'], 'scope_status': 'consistent', 'reason': 'x'}
                                         for t in ctx['targets'] for gl in t['goals']], 'issues': []}, {}
        if stage == 'v3-supplement':
            rows = []
            for q in ctx['questions']:
                if self.supplement == 'point':
                    rows.append({'question_id': q['question_id'], 'decision': 'point', 'duplicate_of': None, 'reason': 'Missed',
                                 'point': {'point': 'Synthetic missed point', 'importance_basis': BASIS,
                                           'source_refs': [{'source_id': 'S1', 'pages': [], 'locator': 'synthetic paragraph'}]}})
                else:
                    rows.append({'question_id': q['question_id'], 'decision': 'out_of_scope', 'point': None, 'duplicate_of': None, 'reason': 'S2 only'})
            return {'rows': rows}, {}
        if stage == 'v3-supplement-normalize':
            b = f.brief()
            t = copy.deepcopy(b['targets'][0])
            t.update(target_id=ctx['allowed']['target_ids'][0], relation_ids=['R2'])
            t['directions'] = [{**copy.deepcopy(t['directions'][1]), 'direction_id': ctx['allowed']['direction_ids'][0], 'relation_ids': ['R2']}]
            p = {**copy.deepcopy(b['points'][0]), 'point_id': ctx['points'][0]['point_id'], 'target_ids': [t['target_id']]}
            return {'targets': [t], 'points': [p]}, {}
        if stage.startswith('v3-add'):
            base = f.old.bank()['questions'][0]
            q = authored(base)
            q.update(question_id=ctx['allowed_question_ids'][0], question='Synthetic added question', point_ids=ctx['goals'][0]['point_ids'])
            return {'questions': [q], 'concepts': [], 'retrieval_plan': [], 'source_conflicts': [], 'visual_stimuli': [], 'clinical_conflicts': []}, {}
        if stage.startswith('v3-review'):
            first = stage.endswith('-0')
            return {'reviews': [{'question_id': q['question_id'], 'verdict': 'ok',
                                 'design': 'doubt' if first and q['question_id'] in self.design_doubt else 'ok',
                                 'note': '', 'suggested_answer': '', 'fix': '', 'prerequisite_checks': [
                                     {'prerequisite_id': p, 'status': 'supported', 'reason': 'x'} for p in q.get('prerequisites', [])]}
                                for q in ctx['questions']]}, {}
        if stage.startswith('v3-fix'):
            qs = []
            for q in ctx['questions']:
                fixed = authored(q)
                fixed['explanation'] = 'Synthetic clearer explanation'
                qs.append(fixed)
            return {'questions': qs, 'source_conflicts': [], 'visual_stimuli': [], 'clinical_conflicts': []}, {}
        if stage.startswith('v3-context'):
            return {'conflicts': [{'conflict_id': c['conflict_id'], 'status': 'consistent', 'reason': 'Synthetic'} for c in ctx['conflicts']],
                    'questions': [], 'unrecorded': []}, {}
        if stage.startswith('medical-'):
            assert ctx['medicalFinal'] is True
            return f.old.checks(ctx['bank']), {}
        raise AssertionError(stage)


def run(tmp_path, model=None, resume=None):
    tmp_path.mkdir(exist_ok=True)
    p = packet(tmp_path)
    model = model or Model()
    result = g.run(p, tmp_path / 'out', invoke=model, resume=resume)
    return p, model, result


def test_the_whole_v3_path_adds_and_fixes_without_touching_other_questions(tmp_path):
    p, model, result = run(tmp_path)
    meta = result['manifest']
    assert consume(result, p) == result['document']
    # Stage order: no blind medical review per round, one medical review at the end.
    assert model.calls[0] == 'normalize' and model.calls[-2:] == ['v3-context-0', 'medical-0']
    assert model.calls.count('medical-0') == 1 and not any(re.fullmatch(r'(source|repair|generate)-.*', c) for c in model.calls)
    # Q2 answered no goal → a supplement point P002 → goal DQ001, covered by Q2.
    assert [d['decision'] for d in meta['supplement']] == ['point'] and meta['supplement'][0]['point_id'] == 'P002'
    assert any(t['target_id'] == 'TQ001' for t in result['brief']['targets'])
    # D2 was a gap → one add round → Q003.
    assert meta['addRounds'] == 1 and 'Q003' in {q['question_id'] for q in result['document']['bank_snapshot']['questions']}
    # Q1 had a design doubt → fixed once → re-reviewed alone; Q2/Q003 never re-reviewed.
    assert [x['question_id'] for x in meta['fixes']] == ['Q1'] and not meta['fixes'][0]['reverted']
    assert [q['question_id'] for q in model.inputs['v3-review-0-1']['questions']] == ['Q1']
    assert {t['direction_id'] for t in result['document']['tasks']} == {'D1', 'D2', 'DQ001'}
    assert meta['notReady'] == []


def test_stage_inputs_carry_only_their_fields(tmp_path):
    _, model, _ = run(tmp_path)
    assert set(model.inputs['v3-coverage-0-0']) == {'goals', 'questions', '_pipeline_version'}
    assert set(model.inputs['v3-add-0']) == {'goals', 'existing', 'bank_concepts', 'source_conflict_ids', 'allowed_question_ids',
                                            'pages', '_pipeline_version'}
    assert set(model.inputs['v3-review-0-0']) == {'questions', 'prerequisites', 'source_conflicts', 'clinical_conflicts', 'pages',
                                                 '_pipeline_version'}
    for name, ctx in model.inputs.items():
        if name.startswith('v3-'):
            assert not {'conceptMap', 'previousAuthoring', 'sourceAudit', 'brief'} & set(ctx), name
            if not name.startswith('v3-supplement'):   # only the supplement stages get exam points (existing texts, new points)
                assert 'points' not in ctx, name
    # The add stage sees only the gap goal; the scoped coverage after it sees only the new question.
    assert [gl['direction_id'] for gl in model.inputs['v3-add-0']['goals']] == ['D2']
    assert [q['question_id'] for q in model.inputs['v3-coverage-1-0']['questions']] == ['Q003']


def test_a_doubt_does_not_change_coverage_and_a_worse_fix_is_reverted(tmp_path):
    class Worse(Model):
        def __call__(self, stage, ctx, material, model):
            value, info = super().__call__(stage, ctx, material, model)
            if stage == 'v3-review-0-1':
                for r in value['reviews']:
                    r.update(verdict='wrong', note='Synthetic worse')
            return value, info
    p, model, result = run(tmp_path, Worse())
    fix = result['manifest']['fixes']
    # First fix judged worse → reverted; the second (last allowed) attempt starts from the restored question.
    # It writes the same text again, so the recorded verdict for that content is reused (no new review) and
    # it is reverted again: the question ends as authored, with its original doubt.
    assert [(x['question_id'], x['attempt'], x['reverted']) for x in fix] == [('Q1', 1, True), ('Q1', 2, True)]
    original = next(q for q in packet(tmp_path)['intakeBank']['bank']['questions'] if q['question_id'] == 'Q1')
    assert model.inputs['v3-fix-0-1']['questions'][0]['explanation'] == original['explanation']
    assert 'v3-review-0-2' not in model.calls
    final = next(q for q in result['document']['bank_snapshot']['questions'] if q['question_id'] == 'Q1')
    assert final['explanation'] == original['explanation']
    # The coverage of D1 never depended on the doubt: it stays covered throughout.
    assert result['manifest']['notReady'] == []
    assert consume(result, p) == result['document']


def test_out_of_scope_questions_leave_the_tasks_and_are_recorded(tmp_path):
    p, model, result = run(tmp_path, Model(supplement='out_of_scope'))
    off = result['manifest']['offGoalQuestions']
    assert [r['question_id'] for r in off] == ['Q2'] and off[0]['question']['question_id'] == 'Q2'
    assert 'Q2' not in {q['question_id'] for q in result['document']['bank_snapshot']['questions']}
    assert consume(result, p) == result['document']


def test_an_add_stage_that_rewrites_an_existing_question_is_rejected(tmp_path):
    class Rewrite(Model):
        def __call__(self, stage, ctx, material, model):
            value, info = super().__call__(stage, ctx, material, model)
            if stage.startswith('v3-add'):
                value['questions'][0]['question_id'] = 'Q1'
            return value, info
    with pytest.raises(ValueError, match='allowed range|existing question'):
        run(tmp_path, Rewrite())
    ledger = json.loads((tmp_path / 'out' / 'ledger.json').read_text(encoding='utf-8'))
    assert ledger['stages']['v3-add-0']['status'] == 'failed' and ledger['addRounds'] == 1


def test_a_failed_stage_needs_a_reason_and_resume_keeps_budgets(tmp_path):
    class Once(Model):
        failed = False

        def __call__(self, stage, ctx, material, model):
            if stage == 'v3-review-0-0' and not Once.failed:
                Once.failed = True
                raise RuntimeError('synthetic interruption')
            return super().__call__(stage, ctx, material, model)
    model = Once()
    with pytest.raises(RuntimeError):
        run(tmp_path, model)
    with pytest.raises(ValueError, match='--resume'):
        run(tmp_path, model)
    before = len(model.calls)
    p, model, result = run(tmp_path, model, resume='synthetic operator reason')
    again = model.calls[before:]
    assert again[0] == 'v3-review-0-0' and 'normalize' not in again and 'v3-add-0' not in again
    assert result['manifest']['addRounds'] == 1 and result['manifest']['stageResumes'][0]['reason'] == 'synthetic operator reason'
    assert (tmp_path / 'out' / '.resume-1' / 'v3-review-0-0.input.json').exists()


def test_v3_prompts_carry_the_v2_paragraphs_verbatim():
    ll = ROOT / 'content/prompts/learning-links'

    def paras(name):
        return [p.strip() for p in re.split(r'\n\s*\n', (ll / name).read_text(encoding='utf-8')) if p.strip()]
    src, aut = paras('automation/source-v2.md'), paras('automation/author-v2.md')
    v = lambda name: (ll / 'v3' / name).read_text(encoding='utf-8')
    for i in (1, 2, 4):
        assert src[i] in v('coverage.md')
    for i in (3, 6, 10):
        assert src[i] in v('map-check.md')
    assert src[5] in v('item-review.md')
    for i in (4, 5, 6, 7, 8, 9, 12):
        assert aut[i] in v('add.md')
    for i in (4, 5, 6, 7, 8, 9):
        assert aut[i] in v('fix.md')
    # [10] asks for facts of every conflict ID (a whole-bank rule); the partial stages carry a scoped rewrite instead
    for name in ('add.md', 'fix.md'):
        assert aut[10] not in v(name) and '모든 conflict_id마다' not in v(name) and '## 충돌 (이 단계 범위)' in v(name)
        assert aut[10].split('명시한다.')[0] not in v(name)
    assert '「중요도 근거」' not in v('point-supplement.md') and '## 중요도 근거' in v('point-supplement.md')


@pytest.mark.parametrize('tamper,message', [
    (lambda r: r['document']['tasks'].pop(), 'not the assembly'),
    (lambda r: r['medical']['reviews'][0].update(verdict='wrong'), 'medical review is not of this bank'),
    (lambda r: r['manifest']['clinicalContext']['unrecorded'].append('Synthetic other'), 'merged judgments'),
    (lambda r: r['manifest']['readiness'][0].update(ready=not r['manifest']['readiness'][0]['ready']), 'readiness table'),
    (lambda r: r['manifest']['supplementPoints']['points'][0].update(point='Synthetic rewritten'), 'supplement changed'),
    (lambda r: r['manifest'].update(addRounds=2), 'add rounds differ'),
])
def test_tampered_v3_runs_are_rejected_by_the_consumer(tmp_path, tamper, message):
    p, _, result = run(tmp_path)
    tamper(result)
    with pytest.raises(ValueError, match=message):
        consume(result, p)


def test_a_bank_in_another_bank_version_is_projected_and_recorded(tmp_path):
    p = packet(tmp_path)
    p['intakeBank']['bank']['build_meta']['schema_version'] = 'BANK'
    p['intakeBank']['bank']['questions'][0].update(tier='Core', importance=5)
    p['inputHash'] = packet_hash(p)
    result = g.run(p, tmp_path / 'out', invoke=Model())
    changes = result['manifest']['intakeProjection']
    assert {'field': 'build_meta.schema_version', 'from': 'BANK', 'to': '3.3'} in changes and result['manifest']['rejectedAtIntake'] == []
    assert consume(result, p) == result['document']
    result['manifest']['intakeProjection'] = []
    with pytest.raises(ValueError, match='intake projection'):
        consume(result, p)


def test_add_and_fix_stages_get_the_merge_state_outside_their_input(tmp_path):
    """P6: the transport gets what the merge receives (`_check`); the stage input and its hash do not."""
    p, model, result = run(tmp_path)
    assert set(model.states) == {'v3-supplement', 'v3-supplement-normalize', 'v3-add-0', 'v3-fix-0-0'}
    assert {'bank', 'clinical_conflicts', 'stimuli', 'sources'} == set(model.states['v3-add-0'])
    assert not any('stimuli' in q for q in model.states['v3-add-0']['bank']['questions'])
    saved = json.loads((tmp_path / 'out' / 'v3-add-0.input.json').read_text(encoding='utf-8'))
    assert '_check' not in saved


def test_an_empty_coverage_runs_once_more_in_a_fresh_session(tmp_path):
    """review-retry/1 as /2: the abandoned stage is archived; a second empty judgment would stop."""
    class Empty(Model):
        def __call__(self, stage, ctx, material, model):
            if stage == 'v3-coverage-0-0' and self.calls.count(stage) == 0:
                self.calls.append(stage)
                return {'rows': [{'direction_id': gl['direction_id'], 'status': 'unknown', 'evidence': [], 'reason': 'Gave up'}
                                 for gl in ctx['goals']]}, {}
            return super().__call__(stage, ctx, material, model)
    _, model, result = run(tmp_path, Empty())
    assert model.calls.count('v3-coverage-0-0') == 2
    retry = result['manifest']['reviewRetries']
    assert [r['stage'] for r in retry] == ['v3-coverage-0-0'] and retry[0]['kind'] == 'empty-judgment'
    assert (tmp_path / 'out' / '.retry-v3-coverage-0-0' / 'v3-coverage-0-0.raw.json').exists()


def test_the_medical_review_runs_in_batches_inside_one_stage(tmp_path, monkeypatch):
    monkeypatch.setattr(g3, 'MEDICAL_BATCH', 1)
    seen = []

    class Count(Model):
        def __call__(self, stage, ctx, material, model):
            if stage.startswith('medical-'):
                seen.append([q['question_id'] for q in ctx['bank']['questions']])
            return super().__call__(stage, ctx, material, model)
    _, model, result = run(tmp_path, Count())
    bank = result['document']['bank_snapshot']
    assert len(seen) == len(bank['questions']) and all(len(x) == 1 for x in seen)
    assert {r['question_id'] for r in result['medical']['reviews']} == {q['question_id'] for q in bank['questions']}
    stages = {s['name'] for s in result['manifest']['stages']}
    assert 'medical-0' in stages and not any(n.startswith('medical-1') for n in stages)


def test_a_bad_image_crop_is_found_by_the_stage_check(tmp_path):
    """P6: the render that runs after an add/fix stage runs in its check, so the model can correct the crop."""
    import fitz
    import hashlib
    pdf = tmp_path / 'notes.pdf'
    doc = fitz.open()
    doc.new_page()
    doc.save(pdf)
    sources = [{'id': 'S1', 'localPath': str(pdf), 'sha256': hashlib.sha256(pdf.read_bytes()).hexdigest()}]
    bank = f.old.bank()
    for q in bank['questions']:
        q.pop('stimuli', None)
    ids = v3.next_question_ids(bank, 1)
    q = authored(bank['questions'][0])
    q.update(question_id=ids[0], point_ids=['P1'])
    ctx = {'allowed_question_ids': ids, 'existing': [], 'bank_concepts': [{'concept_id': c['concept_id'], 'title': ''} for c in bank['concepts']],
           'goals': [{'point_ids': ['P1']}], 'source_conflict_ids': []}
    state = {'bank': bank, 'clinical_conflicts': [], 'stimuli': [], 'sources': sources}
    good = {'question_id': ids[0], 'source_id': 'S1', 'page': 1, 'crop': [0, 0, 0.5, 0.5], 'reason': 'Synthetic figure'}
    out = {'questions': [q], 'concepts': [], 'retrieval_plan': [], 'source_conflicts': [], 'visual_stimuli': [good], 'clinical_conflicts': []}
    assert g3.check_stage('add', out, ctx, state, tmp_path / 'scratch') == out
    bad = copy.deepcopy(out)
    bad['visual_stimuli'][0]['page'] = 9
    with pytest.raises(ValueError, match='물리쪽'):
        g3.check_stage('add', bad, ctx, state, tmp_path / 'scratch')


NEW_CF = {'conflict_id': 'CF07', 'description': 'Synthetic lecture/jokbo conflict', 'source_refs': [{'source_id': 'S1', 'locator': 'x'}],
          'unresolved': False}


class Cites(Model):
    """The first fix makes Q1 cite a new conflict CF07 (record and facts)."""
    def __call__(self, stage, ctx, material, model):
        value, info = super().__call__(stage, ctx, material, model)
        if stage == 'v3-fix-0-0':
            for q in value['questions']:
                if q['question_id'] == 'Q1':
                    q['conflict_id'] = 'CF07'
                    value['source_conflicts'] = [copy.deepcopy(NEW_CF)]
                    value['clinical_conflicts'] = [{'conflict_id': 'CF07', 'facts': 'Synthetic facts'}]
        return value, info


def test_a_revert_takes_back_the_conflicts_its_fix_added(tmp_path):
    """261102_02 (2026-11-10): Q109's reverted fix left CF-POLIO-28, which no question cited; the context
    judgment called it incomplete and every goal lost its task."""
    class Reverted(Cites):
        def __call__(self, stage, ctx, material, model):
            value, info = super().__call__(stage, ctx, material, model)
            if stage == 'v3-review-0-1':
                for r in value['reviews']:
                    if r['question_id'] == 'Q1':
                        r.update(verdict='wrong', note='Synthetic worse')
            return value, info
    p, model, result = run(tmp_path, Reverted(design_doubt=('Q1', 'Q2')))
    meta = result['manifest']
    first = [(x['question_id'], x['reverted']) for x in meta['fixes'] if x['stage'] == 'v3-fix-0-0']
    assert first == [('Q1', True), ('Q2', False)]
    assert 'CF07' not in {c['conflict_id'] for c in meta['clinicalConflicts']}
    assert 'CF07' not in {c['conflict_id'] for c in result['document']['bank_snapshot'].get('source_conflicts', [])}
    q2 = next(q for q in result['document']['bank_snapshot']['questions'] if q['question_id'] == 'Q2')
    assert q2['explanation'] == 'Synthetic clearer explanation'   # the kept fix stays
    assert 'CF07' not in json.dumps(model.inputs['v3-context-0'])
    assert consume(result, p) == result['document']


def test_a_kept_fix_keeps_its_conflict(tmp_path):
    p, model, result = run(tmp_path, Cites())
    assert {c['conflict_id'] for c in result['manifest']['clinicalConflicts']} == {'CF07'}
    assert consume(result, p) == result['document']


class Judged(Cites):
    """v3-context-0 gives CF07 `status`; `again` repeats that at v3-context-1. `flag` names a question whose text
    carries review history."""
    def __init__(self, status='incomplete', again=False, flag=None, **kw):
        super().__init__(**kw)
        self.status, self.again, self.flag = status, again, flag

    def __call__(self, stage, ctx, material, model):
        value, info = super().__call__(stage, ctx, material, model)
        if stage == 'v3-context-0' or (stage == 'v3-context-1' and self.again):
            for row in value['conflicts']:
                row.update(status=self.status, reason='CF07 does not state the adopted answer')
            if self.flag and any(q['question_id'] == self.flag for q in ctx['questions']):
                value['questions'] = [{'question_id': self.flag, 'reason': 'Synthetic review history'}]
        return value, info


def test_a_context_verdict_sends_the_citing_questions_to_one_fix(tmp_path):
    p, model, result = run(tmp_path, Judged())
    meta = result['manifest']
    tail = model.calls[model.calls.index('v3-context-0'):]
    # The re-review of unchanged content is reused from the verdict ledger (P2), so it may not be called.
    assert tail[:2] == ['v3-context-0', 'v3-fix-context-0'] and tail[-2:] == ['v3-context-1', 'medical-0']
    assert [q['question_id'] for q in model.inputs['v3-fix-context-0']['questions']] == ['Q1']
    finding = model.inputs['v3-fix-context-0']['findings'][0]
    assert any('CF07 does not state the adopted answer' in x for x in finding['code_findings'])
    assert meta['contextRepairs'] == [{'stage': 'v3-context-0', 'open': {'conflicts': ['CF07'], 'questions': []}, 'targets': ['Q1']}]
    assert [x['attempt'] for x in meta['fixes'] if x['question_id'] == 'Q1'] == [1, 2]   # within the per-question budget
    assert [c['conflict_id'] for c in model.inputs['v3-context-1']['conflicts']] == ['CF07']   # only what the repair touched
    assert [(r['conflict_id'], r['status'], r['stage']) for r in meta['clinicalContext']['conflicts']] == [('CF07', 'consistent', 1)]
    assert [c['conflict_id'] for c in model.inputs['medical-0']['clinicalInput']['clinical_conflicts']] == ['CF07']
    assert consume(result, p) == result['document']


@pytest.mark.parametrize('status', ['incomplete', 'contamination'])
def test_a_context_verdict_never_stops_the_lecture(tmp_path, status):
    """261102_02 (2026-11-10): one lecture-wide context verdict about three records stopped 134 questions, and a
    completed stage with a blocking value could not be resumed. Now the record's facts are not sent to the medical
    review; every question and task stays."""
    _, _, clean = run(tmp_path / 'clean', Cites())
    p, model, result = run(tmp_path, Judged(status=status, again=True))
    meta = result['manifest']
    assert model.calls[-2:] == ['v3-context-1', 'medical-0']
    assert model.inputs['medical-0']['clinicalInput']['clinical_conflicts'] == []
    assert [(r['conflict_id'], r['status']) for r in meta['clinicalContext']['conflicts']] == [('CF07', status)]
    assert 'CF07' in result['sourceAudit']['assessment']['assessment']['clinical_context_reason']
    assert {c['conflict_id'] for c in meta['clinicalConflicts']} == {'CF07'}   # the record itself is kept
    assert [t['direction_id'] for t in result['document']['tasks']] == [t['direction_id'] for t in clean['document']['tasks']]
    assert consume(result, p) == result['document']


def test_a_question_with_review_history_in_its_text_is_repaired_once(tmp_path):
    p, model, result = run(tmp_path, Judged(status='consistent', flag='Q2'))
    assert [q['question_id'] for q in model.inputs['v3-fix-context-0']['questions']] == ['Q2']
    assert 'Q2' in {q['question_id'] for q in model.inputs['v3-context-1']['questions']}
    assert result['manifest']['clinicalContext']['questions'] == []
    assert consume(result, p) == result['document']


def test_an_unjudged_context_runs_once_more_in_a_fresh_session(tmp_path):
    class Unknown(Cites):
        seen = 0

        def __call__(self, stage, ctx, material, model):
            value, info = super().__call__(stage, ctx, material, model)
            if stage == 'v3-context-0' and not self.seen:
                self.seen += 1
                for row in value['conflicts']:
                    row['status'] = 'unknown'
            return value, info
    p, model, result = run(tmp_path, Unknown())
    assert model.calls.count('v3-context-0') == 2
    assert [(r['stage'], r['kind']) for r in result['manifest']['reviewRetries']] == [('v3-context-0', 'empty-judgment')]
    assert consume(result, p) == result['document']


def test_a_map_check_that_judged_nothing_runs_once_more(tmp_path):
    class Lazy(Model):
        seen = 0

        def __call__(self, stage, ctx, material, model):
            value, info = super().__call__(stage, ctx, material, model)
            if stage == 'v3-map-check-0' and not self.seen:
                self.seen += 1
                for key, field in (('relation_checks', 'status'), ('target_checks', 'status'), ('direction_checks', 'scope_status')):
                    for row in value[key]:
                        row[field] = 'unknown'
            return value, info
    p, model, result = run(tmp_path, Lazy())
    assert model.calls.count('v3-map-check-0') == 2
    assert consume(result, p) == result['document']


def test_no_task_stops_before_the_medical_review_with_the_reasons(tmp_path):
    class NoTarget(Model):
        def __call__(self, stage, ctx, material, model):
            value, info = super().__call__(stage, ctx, material, model)
            if stage.startswith('v3-map-check'):
                for row in value['target_checks']:
                    row['status'] = 'conflict'
            return value, info
    model = NoTarget()
    with pytest.raises(ValueError, match='과제가 0개.*target'):
        run(tmp_path, model)
    assert 'medical-0' not in model.calls
    table = json.loads((tmp_path / 'out' / 'readiness.json').read_text(encoding='utf-8'))
    assert table['counts'].get('ready', 0) == 0 and table['counts']['target'] == len(table['rows'])


def test_a_missing_medical_verdict_is_asked_once_more_then_recorded(tmp_path):
    class Skips(Model):
        def __call__(self, stage, ctx, material, model):
            value, info = super().__call__(stage, ctx, material, model)
            if stage.startswith('medical-'):
                value = {**value, 'reviews': [r for r in value['reviews'] if r['question_id'] != 'Q2']}
            return value, info
    p, model, result = run(tmp_path, Skips())
    assert model.calls.count('medical-0') == 2   # the batch, then Q2 alone
    assert [q['question_id'] for q in model.inputs['medical-0']['bank']['questions']] == ['Q2']
    row = next(r for r in result['medical']['reviews'] if r['question_id'] == 'Q2')
    assert row['verdict'] == 'doubt' and row['note'].startswith(v3.UNREVIEWED_NOTE)
    assert [r['question_id'] for r in result['manifest']['medicalUnreviewed']] == ['Q2']
    assert consume(result, p) == result['document']


def test_review_history_in_a_question_is_a_fix_target_not_a_stop(tmp_path):
    """/2 medical_input refuses the whole input for one such string; in /3 that stopped the lecture at the last stage."""
    class Marked(Model):
        def __call__(self, stage, ctx, material, model):
            value, info = super().__call__(stage, ctx, material, model)
            if stage == 'v3-add-0':
                value['questions'][0]['explanation'] = '이전 검토 판정에 따라 고친 설명'
            if stage.startswith('v3-fix') and not self.keep:
                pass
            if stage.startswith('v3-fix') and self.keep:
                for q in value['questions']:
                    if q['question_id'] == self.added:
                        q['explanation'] = '이전 검토 판정에 따라 고친 설명'
            if stage == 'v3-add-0':
                self.added = value['questions'][0]['question_id']
            return value, info
    model = Marked()
    model.keep = False
    p, model, result = run(tmp_path, model)
    fix = next(s for s in model.calls if s.startswith('v3-fix') and model.added in {q['question_id'] for q in model.inputs[s]['questions']})
    assert any('검수·판정 이력' in x for f_ in model.inputs[fix]['findings'] for x in f_['code_findings'])
    assert result['manifest']['medicalUnreviewed'] == []
    model = Marked()
    model.keep = True
    p, model, result = run(tmp_path / 'kept', model)   # still there after the fix budget: left out of the medical review, recorded
    assert [r['question_id'] for r in result['manifest']['medicalUnreviewed']] == [model.added]
    assert model.added not in {q['question_id'] for q in model.inputs['medical-0']['clinicalInput']['questions']}
    assert consume(result, p) == result['document']


def test_a_resume_archives_the_stages_an_earlier_code_version_left(tmp_path):
    p, model, result = run(tmp_path)
    out = tmp_path / 'out'
    ledger = json.loads((out / 'ledger.json').read_text(encoding='utf-8'))
    ledger['stages']['context-0'] = dict(ledger['stages']['v3-context-0'])
    (out / 'ledger.json').write_text(json.dumps(ledger), encoding='utf-8')
    for suffix in ('.input.json', '.raw.json', '.usage.json', '.json'):
        (out / ('context-0' + suffix)).write_bytes((out / ('v3-context-0' + suffix)).read_bytes())
    (out / 'result.json').unlink()
    with pytest.raises(ValueError, match='이전 단계 기록'):
        run(tmp_path, model)
    p, model, result = run(tmp_path, model, resume='synthetic: lecture-wide context stage retired')
    assert 'context-0' not in {s['name'] for s in result['manifest']['stages']}
    assert result['manifest']['stageResumes'][-1]['superseded'][-1]['name'] == 'context-0'
    assert consume(result, p) == result['document']


# ---------------------------------------------------------------- any judgment value reaches a result
import random   # noqa: E402

TERMINAL = ('과제가 0개', 'judged nothing', 'left unknown')   # no task at all; a stage that judged nothing twice


class AnyVerdict(Cites):
    """Every judgment value a stage may return, chosen at random: the shapes stay valid (the stage checks own
    those), the verdicts do not. Models what a fake that only matches formats cannot: a judgment that flips."""
    def __init__(self, seed):
        super().__init__(design_doubt=('Q1', 'Q2'))
        self.r = random.Random(seed)

    def __call__(self, stage, ctx, material, model):
        value, info = super().__call__(stage, ctx, material, model)
        r = self.r
        if stage.startswith('v3-coverage'):
            for row in value['rows']:
                if r.random() < 0.3:
                    row['status'] = r.choice(['missing', 'unknown'])
                for e in row['evidence']:
                    e['visual_verdict'] = r.choice(['ok', 'doubt', 'wrong', 'not_applicable', 'not_applicable'])
                    for part in e['components']:
                        if r.random() < 0.2:
                            part.update(location=r.choice(['provided', 'explanation', 'missing', 'unknown']), answer_unit_indices=[])
                if row['status'] == 'covered' and not any(all(c['location'] == 'answer' for c in e['components']) for e in row['evidence']):
                    row['status'] = 'missing'
        elif stage.startswith('v3-map-check'):
            for row in value['relation_checks']:
                row['status'] = r.choice(['supported', 'supported', 'supported', 'conflict', 'unknown'])
            for key, field in (('target_checks', 'status'), ('direction_checks', 'scope_status')):
                for row in value[key]:
                    row[field] = r.choice(['consistent', 'consistent', 'consistent', 'conflict', 'unknown'])
        elif stage.startswith('v3-review'):
            for row in value['reviews']:
                row['verdict'], row['design'] = r.choice(v3.VERDICTS + ('ok', 'ok')), r.choice(v3.VERDICTS + ('ok', 'ok'))
                row['note'] = 'Synthetic finding' if row['verdict'] != 'ok' or row['design'] != 'ok' else ''
                for check in row['prerequisite_checks']:
                    check['status'] = r.choice(['supported', 'supported', 'unnecessary', 'unknown'])
        elif stage.startswith('v3-context'):
            for row in value['conflicts']:
                row['status'] = r.choice(v3.CONTEXT_STATES)
            if ctx['questions'] and r.random() < 0.3:
                value['questions'] = [{'question_id': r.choice(ctx['questions'])['question_id'], 'reason': 'Synthetic history'}]
            if r.random() < 0.3:
                value['unrecorded'] = ['Synthetic unrecorded conflict']
        elif stage.startswith('medical-'):
            rows = [dict(row, verdict=r.choice(['ok', 'doubt', 'wrong'])) for row in value['reviews'] if r.random() > 0.15]
            value = {**value, 'reviews': rows}
        return value, info


@pytest.mark.parametrize('seed', range(300))
def test_any_judgment_value_reaches_a_result_or_a_named_stop(tmp_path, seed):
    """The lecture is stopped only by having no task at all or by a stage that judged nothing twice. Every other
    combination of verdicts ends in a result the consumer accepts (docs/changes/2026-11-10-gen3-item-scope)."""
    try:
        p, model, result = run(tmp_path, AnyVerdict(seed))
    except ValueError as error:
        assert any(text in str(error) for text in TERMINAL), str(error)
        return
    assert consume(result, p) == result['document']
    ready = {r['direction_id'] for r in result['manifest']['readiness'] if r['ready']}
    assert ready == {t['direction_id'] for t in result['document']['tasks']}
    assert all(r['ready'] or r['reasons'] for r in result['manifest']['readiness'])


def test_a_dangling_conflict_or_image_list_is_found_before_the_context():
    bank = f.old.bank()
    for q in bank['questions']:
        q.pop('stimuli', None)
    v3.check_integrity(bank, [], [])
    with pytest.raises(ValueError, match='no question cites: CF07'):
        v3.check_integrity(bank, [{'conflict_id': 'CF07', 'facts': 'x'}], [])
    v3.check_integrity(bank, [{'conflict_id': 'CF07', 'facts': 'x'}], [], {'CF07'})   # an intake record stays as it came
    stray = {'question_id': 'Q1', 'source_id': 'S1', 'page': 1, 'crop': [0, 0, 1, 1], 'reason': 'x'}
    with pytest.raises(ValueError, match='image list differs'):
        v3.check_integrity(bank, [], [stray])


def test_a_conflict_a_fix_stops_citing_is_taken_out_not_a_stop(tmp_path):
    class Uncites(Judged):
        def __call__(self, stage, ctx, material, model):
            value, info = super().__call__(stage, ctx, material, model)
            if stage == 'v3-fix-context-0':
                for q in value['questions']:
                    q['conflict_id'] = ''
                value['clinical_conflicts'] = []
            return value, info
    p, model, result = run(tmp_path, Uncites())
    meta = result['manifest']
    assert meta['clinicalConflicts'] == [] and meta['clinicalContext']['conflicts'] == []
    assert [(r['kind'], r['id']) for r in meta['restatedIgnored'] if r['kind'] == 'orphan_conflict'] == [('orphan_conflict', 'CF07')]
    assert consume(result, p) == result['document']

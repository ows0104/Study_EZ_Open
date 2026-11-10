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
        if stage.startswith('context-'):
            return {'clinical_context_status': 'consistent', 'clinical_context_reason': 'Synthetic', 'clinical_context_problem': 'none'}, {}
        if stage.startswith('medical-'):
            assert ctx['medicalFinal'] is True
            return f.old.checks(ctx['bank']), {}
        raise AssertionError(stage)


def run(tmp_path, model=None, resume=None):
    p = packet(tmp_path)
    model = model or Model()
    result = g.run(p, tmp_path / 'out', invoke=model, resume=resume)
    return p, model, result


def test_the_whole_v3_path_adds_and_fixes_without_touching_other_questions(tmp_path):
    p, model, result = run(tmp_path)
    meta = result['manifest']
    assert consume(result, p) == result['document']
    # Stage order: no blind medical review per round, one medical review at the end.
    assert model.calls[0] == 'normalize' and model.calls[-2:] == ['context-0', 'medical-0']
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
    (lambda r: r['manifest']['clinicalContext'].update(clinical_context_reason='Synthetic other'), 'context proof|gathered judgments'),
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

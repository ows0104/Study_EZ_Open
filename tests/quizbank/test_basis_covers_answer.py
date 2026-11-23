"""A question's importance basis covers its whole answer (docs/changes/2026-11-23-basis-covers-answer/spec.md).

R1-R4 are prompt rules; the tests pin their sentences. R5 (fix-splits/1) is code: a fix given new IDs may write
what a finding asks apart from the fixed question as new questions with their own basis, on the synthetic /4
lecture of test_root_generation_v4."""
import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_root_generation_v4 as t4
from quizbank import connection_generate as g
from quizbank import connection_generate_v3 as g3
from quizbank import connection_generate_v4 as g4
from studyez_contracts.roots import generation_v4 as v4
from studyez_contracts.roots.automation import validate_result as consume

PROMPTS = Path(__file__).resolve().parents[2] / 'content' / 'prompts' / 'learning-links' / 'v4'


def prompt(name):
    return (PROMPTS / name).read_text(encoding='utf-8')


# ---------------------------------------------------------------- R1-R4: prompt rules
INTAKE = PROMPTS.parent / 'map-tree' / 'bank-task-v4.md'


@pytest.mark.parametrize('name', ['add.md', 'fix.md', INTAKE])
def test_a_basis_row_points_at_the_whole_answer(name):
    text = prompt(name)
    assert '근거 한 줄은 그 문항이 답으로 묻는 내용 전체를 원본에서 가리킬 때만 적는다' in text
    assert '답 단위 일부만 가리키는 줄(기출이 다섯 중 셋만 물었다, 밑줄이 다섯 중 하나에만 있다)은 이 문항의 근거가 아니다' in text
    assert '한 줄의 refs가 여러 쪽에 걸쳐 함께 답 전체를 보여 주면 전체를 가리킨 것이다' in text


@pytest.mark.parametrize('name', ['add.md', INTAKE])
def test_a_basis_on_some_elements_lives_on_as_their_own_question(name):
    """User 2026-11-23: the emphasized element gets its own question with the emphasis, and whether the list question
    stays is judged case by case (existence questions and lists a goal asks for whole stay)."""
    text = prompt(name)
    assert '근거가 답 일부만 가리키면 그 근거를 버리지 않고, 그 일부를 묻는 문항으로 살린다' in text
    assert '그 일부가 다른 물음(다른 연결·다른 범주)이면 그 일부를 묻는 문항으로 나누고, 그 근거를 그 문항에 적는다' in text
    assert '그 원소를 따로 묻는 문항을 쓰고 그 근거를 그 문항에 적는다. 목록 문항에는 그 줄을 쓰지 않는다' in text
    assert '「다섯 중 중요한 것은?」처럼 강조 자체를 묻지 않는다' in text
    assert '목록 문항을 함께 둘지는 사례마다 판단한다' in text
    assert '근거가 없는 원소를 하나씩 따로 묻지 않는다. 「나머지 …」 같은 강의에 없는 묶음을 만들지 않는다' in text
    assert '근거가 없는 내용을 근거를 얻으려고 나누지 않는다' in text
    keep = {'add.md': '존재 문항(input.existence)과, 목표의 components가 그 원소 전부를 답으로 요구하는 목록은 남긴다',
            INTAKE: '목록 전체를 아는 것이 학습목표이거나 다른 문항이 그 목록을 전제로 하면'}[name]
    assert keep in text


def test_a_fix_keeps_the_emphasis_as_a_split_question():
    text = prompt('fix.md')
    assert '고친 문항의 근거가 답 일부만 가리키면 그 근거를 버리지 않는다' in text
    assert '목록 문항을 그 원소 문항으로 줄일지는 사례마다 판단한다' in text
    assert '존재 문항(input.existence)과, covered_goals가 그 원소 전부를 답으로 요구하는 목록은 줄이지 않는다' in text
    assert 'input.asked는 고치는 문항의 covered_goals를 이미 답하는 다른 문항이다' in text


def test_a_fix_asks_what_the_question_asked():
    text = prompt('fix.md')
    assert '고친 문항은 원래 문항이 묻던 것을 묻는다' in text
    assert '원래 답에 없던 원본의 다른 항목을 답에 더하지 않고' in text
    assert '그 부분은 이 ID에 적용하지 않는다' in text
    assert '적용하지 않은 이유를 exam_rationale에 남긴다' in text
    # the three exceptions, existence among them
    assert '예외는 셋이다' in text and '존재 문항(input.existence)이 components의 빠진 원소를 채우는 것' in text
    assert '틀린 정답을 원본에 맞는 정답으로 바꾸는 것' in text
    assert '고친 답 전체가 아니라 그 일부만 가리키는 기존 줄은 뺀다' in text


def test_a_fix_writes_a_split_question_with_its_own_basis():
    text = prompt('fix.md')
    assert '## 따로 묻는 문항 (split_questions, input.allowed_split_question_ids가 있을 때만)' in text
    assert 'split_from에는 갈라 나온 원래 문항의 question_id를 적는다' in text
    assert '원래 문항의 근거를 옮겨 오지 않는다' in text


def test_a_review_fix_stays_inside_the_question():
    text = prompt('item-review.md')
    assert 'fix는 그 문항이 묻는 것 안에서 고칠 방향이다' in text
    assert 'note에 「별도 문항: …」으로 적는다' in text
    assert '그 이유만으로 design을 doubt·wrong으로 하지 않는다' in text


# ---------------------------------------------------------------- R5: fix-splits/1 contract
def fix_ctx():
    q = t4.authored(t4.f.old.bank()['questions'][0])
    q.update(point_ids=['P1'])
    return {'questions': [q], 'allowed_split_question_ids': ['Q010', 'Q011']}, q


def fix_value(q, **split):
    new = {**copy.deepcopy(q), 'question_id': 'Q010', 'question': 'Synthetic split question', 'split_from': q['question_id']}
    new.update(split)
    return {'questions': [copy.deepcopy(q)], 'split_questions': [new], 'source_conflicts': [], 'visual_stimuli': [],
            'clinical_conflicts': [],
            'question_importance': [{'question_id': q['question_id'], 'importance_basis': []},
                                    {'question_id': new['question_id'], 'importance_basis': t4.basis('learning_objective')}]}


def test_the_fix_schema_follows_its_input():
    assert v4.fix_schema({}) is v4.FIX_OUTPUT
    assert v4.fix_schema({'allowed_split_question_ids': []}) is v4.FIX_SPLIT_OUTPUT
    assert 'split_from' in v4.FIX_SPLIT_OUTPUT['properties']['split_questions']['items']['required']
    from runner import root_native_json as native
    assert native.v3_schema('v4-fix-0-0', {'allowed_split_question_ids': ['Q010']}) is v4.FIX_SPLIT_OUTPUT
    assert native.v3_schema('v4-fix-presuppose-0', {}) is v4.FIX_OUTPUT


def test_a_split_question_is_checked_against_its_source():
    ctx, q = fix_ctx()
    assert v4.check_fixed(fix_value(q), ctx)
    with pytest.raises(ValueError, match='outside input.allowed_split_question_ids'):
        v4.check_fixed(fix_value(q, question_id='Q099'), {**ctx, 'allowed_split_question_ids': ['Q010']})
    with pytest.raises(ValueError, match='split_from names a fixed question'):
        v4.check_fixed(fix_value(q, split_from='Q2'), ctx)
    with pytest.raises(ValueError, match='takes the concept'):
        v4.check_fixed(fix_value(q, concept_id='C-other'), ctx)
    with pytest.raises(ValueError, match='point_ids are among'):
        v4.check_fixed(fix_value(q, point_ids=['P9']), ctx)
    value = fix_value(q)
    value['question_importance'] = value['question_importance'][:1]
    with pytest.raises(ValueError, match='importance_basis missing for Q010'):
        v4.check_fixed(value, ctx)
    # a fix not given new IDs keeps the /4 shape it had
    old = fix_value(q)
    old.pop('split_questions')
    old['question_importance'] = old['question_importance'][:1]
    assert v4.check_fixed(old, {'questions': ctx['questions']})
    with pytest.raises(ValueError, match='fields'):
        v4.check_fixed(fix_value(q), {'questions': ctx['questions']})


# ---------------------------------------------------------------- R5: fix-splits/1 in the run
class Splitter(t4.Model):
    """Each fix of a question with a first-review doubt splits one question off it. `worse`: the re-review of these
    sources is wrong, so their fixes are reverted."""

    def __init__(self, worse=(), **kw):
        super().__init__(**kw)
        self.worse, self.split = set(worse), {}

    def __call__(self, stage, ctx, material, model):
        if stage.startswith('v4-review') and 'map_relations' in ctx:
            # the split question recalls the relation of the question it came from
            self.relations = {'Q1': [('R1', 'whole')], 'Q2': [('R1', 'whole')], 'Q003': [('R2', 'whole')],
                              **{s: [('R1' if src != 'Q003' else 'R2', 'whole')] for s, src in self.split.items()}}
        value, info = super().__call__(stage, ctx, material, model)
        if stage.startswith('v4-review') and not stage.endswith('-0'):
            for r in value['reviews']:
                if r['question_id'] in self.worse:
                    r['verdict'] = 'wrong'
        if stage.startswith('v4-fix') and ctx.get('allowed_split_question_ids'):
            free = list(ctx['allowed_split_question_ids'])
            for q in ctx['questions']:
                if not free:
                    break
                new = {**t4.authored(q), 'question_id': free.pop(0), 'question': 'Synthetic split of ' + q['question_id'],
                       'explanation': 'Synthetic split', 'split_from': q['question_id']}
                self.split[new['question_id']] = q['question_id']
                value['split_questions'].append(new)
                value['question_importance'].append({'question_id': new['question_id'],
                                                     'importance_basis': t4.basis('learning_objective')})
        return value, info


def bank_ids(result):
    return [q['question_id'] for q in result['document']['bank_snapshot']['questions']]


def test_a_fix_splits_a_question_off_with_its_own_basis(tmp_path):
    p, model, result = t4.run(tmp_path, Splitter())
    assert consume(result, p) == result['document']
    meta = result['manifest']
    assert model.inputs['v4-fix-0-0']['allowed_split_question_ids'] == ['Q004']
    assert bank_ids(result) == ['Q1', 'Q2', 'Q003', 'Q004']
    # its own basis, not the source's; the source keeps its basis
    assert meta['questionImportance']['Q004'] == t4.basis('learning_objective')
    assert meta['questionImportance']['Q1'] == t4.INTAKE_BASIS['Q1']
    tiers = {q['question_id']: q['tier'] for q in result['document']['bank_snapshot']['questions']}
    assert tiers['Q004'] == 'Core' and tiers['Q1'] == 'Essential'
    assert meta['fixes'] == [{'question_id': 'Q1', 'attempt': 1, 'stage': 'v4-fix-0-0', 'reverted': False, 'split_questions': ['Q004']}]
    # reviewed beside the fix, and judged with it for the fixed question's goals
    assert {q['question_id'] for q in model.inputs['v4-review-0-1']['questions']} == {'Q1', 'Q004'}
    assert {q['question_id'] for q in model.inputs['v4-coverage-fix-0-0']['questions']} >= {'Q1', 'Q004'}
    assert any(t['question_id'] == 'Q004' for t in result['document']['tasks'])
    assert {r['question_id'] for r in meta['itemReviews']} == {'Q1', 'Q2', 'Q003', 'Q004'}


def test_a_reverted_fix_takes_its_split_question_with_it(tmp_path):
    p, model, result = t4.run(tmp_path, Splitter(worse=('Q1',)))
    assert consume(result, p) == result['document']
    assert bank_ids(result) == ['Q1', 'Q2', 'Q003']
    assert result['manifest']['fixes'][0] == {'question_id': 'Q1', 'attempt': 1, 'stage': 'v4-fix-0-0', 'reverted': True,
                                              'split_questions': ['Q004']}
    assert 'Q004' not in result['manifest']['questionImportance']


def test_a_ledger_made_before_fix_splits_gives_the_fix_no_new_ids(tmp_path, monkeypatch):
    class Legacy(g3.Stages):
        def __init__(self, *a, fresh=None, **kw):
            super().__init__(*a, fresh={k: v for k, v in (fresh or {}).items() if k != 'fixSplits'}, **kw)
    monkeypatch.setattr(g4, 'Stages', Legacy)
    p, model, result = t4.run(tmp_path, Splitter())
    assert consume(result, p) == result['document']
    assert 'allowed_split_question_ids' not in model.inputs['v4-fix-0-0']
    assert bank_ids(result) == ['Q1', 'Q2', 'Q003']


def comparable(result):
    value = copy.deepcopy(result)
    value['manifest'].pop('batchPhases', None)
    value['validation'].pop('checked_at', None)
    value['medical'].pop('reviewed_at', None)
    # the fix inputs differ by their conflict scope and the medical review by its time (test_root_batch_parallel)
    value['manifest']['stages'] = [s['name'] for s in value['manifest']['stages']]
    value['manifest'].pop('runtimeHash')
    return value


def test_batches_side_by_side_split_into_their_own_id_ranges(tmp_path, monkeypatch):
    monkeypatch.setattr(g4, 'REVIEW_BATCH', 1)
    monkeypatch.setattr(g3, 'MEDICAL_BATCH', 1)
    model = Splitter(design_doubt=('Q1', 'Q2', 'Q003'))
    tmp_path.mkdir(exist_ok=True)
    p = t4.packet(tmp_path)
    side = g.run(p, tmp_path / 'side', invoke=model)
    assert consume(side, p) == side['document']
    assert {r['phase']: r['mode'] for r in side['manifest']['batchPhases']}['item-review'] == 'parallel'
    # one batch of one question: two IDs per batch (one per fix round), after every ID the run used
    ranges = {s: c['allowed_split_question_ids'] for s, c in model.inputs.items() if s.startswith('v4-fix')}
    assert ranges == {'v4-fix-0-0': ['Q004'], 'v4-fix-1-0': ['Q006'], 'v4-fix-2-0': ['Q008']}
    assert bank_ids(side) == ['Q1', 'Q2', 'Q003', 'Q004', 'Q006', 'Q008']

    monkeypatch.setattr(g3.Stages, 'parallel', property(lambda self: False))
    one = Splitter(design_doubt=('Q1', 'Q2', 'Q003'))
    after = g.run(p, tmp_path / 'one', invoke=one)
    assert {s: c['allowed_split_question_ids'] for s, c in one.inputs.items() if s.startswith('v4-fix')} == ranges
    # A split question's re-check read the goal's other questions as the phase started (Q2 for D1); batch 1 then fixed
    # Q2, so side by side the goal is judged once more on the merged bank (connection_batches.stale_coverage).
    a, b = comparable(side), comparable(after)
    assert [n for n in a['manifest']['stages'] if n not in b['manifest']['stages']] == ['v4-coverage-merge-0']
    a['manifest']['stages'].remove('v4-coverage-merge-0')
    assert a == b
    # the re-check read the goal's other questions, and kept their first evidence
    assert {q['question_id'] for q in model.inputs['v4-coverage-fix-0-0']['questions']} == {'Q1', 'Q004', 'Q2'}
    assert ranges and model.inputs['v4-fix-0-0']['asked'] == [
        {'question_id': 'Q2', 'question': next(q['question'] for q in model.inputs['v4-review-1-0']['questions']),
         'answer': next(q['answer'] for q in model.inputs['v4-review-1-0']['questions']), 'direction_ids': ['D1']}]


class CopySplitter(Splitter):
    """The split question asks again what Q2 asks: the re-check after the fix names them duplicates."""

    def __call__(self, stage, ctx, material, model):
        value, info = super().__call__(stage, ctx, material, model)
        if stage.startswith('v4-coverage-fix'):
            qids = {q['question_id'] for q in ctx['questions']}
            for row in value['rows']:
                if row['direction_id'] == 'D1' and {'Q004', 'Q2'} <= qids:
                    row['evidence'] = [e for e in row['evidence'] if e['question_id'] != 'Q004'] + [
                        {**copy.deepcopy(row['evidence'][0]), 'question_id': 'Q004'}]
                    row['duplicates'] = [{'question_ids': ['Q2', 'Q004'], 'reason': 'Synthetic: the split asks what Q2 asks'}]
        return value, info


def test_a_split_question_that_repeats_a_goal_question_is_merged(tmp_path):
    p, model, result = t4.run(tmp_path, CopySplitter())
    assert consume(result, p) == result['document']
    # Q2 answered D1 before the fix and was not a duplicate partner of Q1: it is read beside the split question
    assert {q['question_id'] for q in model.inputs['v4-coverage-fix-0-0']['questions']} == {'Q1', 'Q2', 'Q004'}
    merged = {(m['question_id'], m['kept']) for m in result['manifest']['mergedDuplicates']}
    assert merged in ({('Q004', 'Q2')}, {('Q2', 'Q004')})
    # Q2's first evidence stayed as it was judged before
    d1 = next(r for r in result['manifest']['coverage'] if r['direction_id'] == 'D1')
    assert [e['question_id'] for e in d1['evidence']].count('Q2') == 1

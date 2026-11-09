"""사슬알균(26110901) 추가 전용 시험 — 커버 확인 → 빈 목표만 추가 출제 → 전체 재확인.

User approval 2026-11-09: 「승인, 돌려줘」 for the plan in plan.md, including sending S1 notes + S2 jokbo and
their derivatives to OpenAI Codex CLI again. Three model calls, no automatic retry, nothing outside
runs/_e2e/26110901/add-only-trial is written. generation-4 is read only.

Frozen inputs: generation-4 packet (S1/S2 sha256), generation-4 generate.json (brief 119 goals, 102 questions).
The producer's own code builds every stage input; this script only replaces the round order.

  python trial.py prepare | coverage | add | recheck | compare
"""
import copy
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MAIN = ROOT.parents[1] if ROOT.parent.name == '.worktrees' else ROOT
sys.path.insert(0, str(ROOT))
from quizbank import connection_generate as g, connection_visuals as visual  # noqa: E402
from runner import root_native_json as rnj  # noqa: E402
from studyez_contracts.roots import generation_v2 as c, document_hash  # noqa: E402
from studyez_contracts.roots.source_assessment import envelope  # noqa: E402
from studyez_contracts.bank.validate import validate_bank  # noqa: E402
from studyez_contracts.bank.cloze import normalize_cloze  # noqa: E402

GEN4 = MAIN / 'runs/_e2e/26110901/generation-4'
OUT = MAIN / 'runs/_e2e/26110901/add-only-trial'
MODEL = None  # codex default (gpt-6.1-sol), same as generation-4
GAP_STATUSES = ('missing', 'unknown', 'partial')

ADD_ONLY = '''
TRIAL OVERRIDE — ADD-ONLY STAGE (사용자 승인 2026-11-09, docs/changes/2026-11-10-add-only-trial).
This stage only adds questions. These rules take precedence over the repair rules above:
- Copy every question of previousAuthoring.bank with local code, byte for byte. Never change, delete, merge,
  split or extend an existing question (question, answer, answer_units, options, explanations, stimuli,
  prerequisites, point_ids, tiers — every field).
- Copy previousAuthoring.brief unchanged. Do not change the Map. map_change_reason states that nothing changed.
- repairReasons lists only goals that no question answers as a whole. For each such goal write new question(s)
  whose answer covers that goal's answer_scope (with its relations/components), from the original sources.
  When a reason suggests enlarging an existing question, add a new question instead.
- New question_id values continue after the highest existing number. Follow the item-quality rules above.
- Keep every existing clinical_conflicts and visual_stimuli entry unchanged; add entries only for new questions.
- Record each added question and its goal in audit_summary.changes. Do not fix any other issue in this stage.
'''


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write(path, value):
    g.write(Path(path), value)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def packet():
    return read(OUT / 'packet.json')


def base(p, sources):
    b = {k: p[k] for k in ('title', 'scope', 'conceptMap', 'points', 'examDate')}
    b.update(lecture_id=p['subject'] + '/' + p['runId'], sources=sources,
             preserved_scope=g.lecture_scope(p['title'], p['sources']))
    table = c.importance_table(p)
    if table is not None:
        b['importanceTable'] = table
    return b, table


def source_ctx(p, sources, authored):
    """Same construction as connection_generate_v2.run's round loop."""
    b, table = base(p, sources)
    brief, bank = authored['brief'], authored['bank']
    return {**b, 'brief': brief, 'bank': bank, 'clinical_conflicts': authored['clinical_conflicts'],
            **({'targetImportance': c.target_importance(brief, table)} if table is not None else {}),
            'questionFronts': [{'question_id': q['question_id'], 'question': normalize_cloze(q)['question'], 'options': q['options']}
                               for q in bank['questions']],
            'stimulusFiles': [{'question_id': q['question_id'], 'file': 'material/stimulus-' + s['sha256'] + '.png', 'sha256': s['sha256']}
                              for q in bank['questions'] for s in q.get('stimuli', [])],
            '_pipeline_version': c.POLICY}


def call(name, ctx):
    """One model call through the producer's native adapter; inputs, raw output and usage are kept."""
    for suffix in ('.input.json', '.raw.json', '.usage.json', '.json'):
        assert not (OUT / (name + suffix)).exists(), name + ': already ran — no automatic repeat'
    assert not (OUT / '.native' / name).exists(), name + ': an earlier attempt is preserved — no automatic repeat'
    write(OUT / (name + '.input.json'), ctx)
    raw, info = rnj.NativeJson(OUT)(name, ctx, OUT / 'material', MODEL)
    write(OUT / (name + '.usage.json'), info)
    return raw, info


def review(name, authored):
    p = packet()
    ctx = source_ctx(p, read(OUT / 'sources.json'), authored)
    raw, info = call(name, ctx)
    evidence = envelope(ctx['brief'], ctx['bank'], raw)
    write(OUT / (name + '.raw.json'), evidence)
    value = c.compile_assessment(ctx['brief'], ctx['bank'], evidence)
    write(OUT / (name + '.json'), value)
    return value, info


def coverage(audit):
    return {r['direction_id']: r['status'] for r in audit['goal_coverage']}


# ---------------------------------------------------------------- steps
def prepare():
    assert not OUT.exists(), 'Preserve the earlier trial; no automatic restart.'
    OUT.mkdir(parents=True)
    p = read(GEN4 / 'packet.json')
    shutil.copy2(GEN4 / 'packet.json', OUT / 'packet.json')
    sources = g.prepare(p, OUT / 'material')
    write(OUT / 'sources.json', sources)
    authored = read(GEN4 / 'generate.json')
    write(OUT / 'baseline-authoring.json', authored)
    # The rebuilt source input must match what generation-4 gave source-0 for the same bank (code drift check).
    rebuilt = source_ctx(p, sources, authored)
    before = read(GEN4 / 'source-0.input.json')
    drift = sorted(k for k in set(rebuilt) | set(before) if rebuilt.get(k) != before.get(k))
    record = {'authorization': '2026-11-09 사용자 「승인, 돌려줘」 — 추가 전용 시험, 필기·족보 OpenAI 재전송 포함',
              'packetSha256': sha(GEN4 / 'packet.json'), 'generateSha256': sha(GEN4 / 'generate.json'),
              'questions': len(authored['bank']['questions']), 'goals': sum(len(t['directions']) for t in authored['brief']['targets']),
              'sourceInputDriftFromGeneration4': drift}
    write(OUT / 'provenance.json', record)
    print(json.dumps(record, ensure_ascii=False))


def step_coverage():
    audit, info = review('source-0', read(OUT / 'baseline-authoring.json'))
    counts = {}
    for s in coverage(audit).values():
        counts[s] = counts.get(s, 0) + 1
    print(json.dumps({'coverage': counts, 'durationMs': info.get('duration_ms')}, ensure_ascii=False))


def gap_reasons(authored, audit):
    gaps = {d for d, s in coverage(audit).items() if s in GAP_STATUSES}
    validation = validate_bank(authored['bank'], [s['id'] for s in packet()['sources']])
    reasons = [r for r in c.repair_reasons(authored['brief'], authored['bank'], audit, None, validation)
               if r['kind'] == 'required_gap' and set(r['direction_ids']) & gaps]
    named = {d for r in reasons for d in r['direction_ids']}
    for t in authored['brief']['targets']:
        for d in t['directions']:
            if d['direction_id'] in gaps and d['direction_id'] not in named:
                reasons.append({'kind': 'required_gap', 'question_ids': [], 'direction_ids': [d['direction_id']],
                                'text': f"{d['direction_id']}: 이 목표 전체(answer_scope)를 답으로 묻는 문항이 없다 "
                                        f"(커버 확인 {coverage(audit)[d['direction_id']]})."})
    return reasons, validation, sorted(gaps)


def step_add():
    authored = read(OUT / 'baseline-authoring.json')
    audit = read(OUT / 'source-0.json')
    reasons, validation, gaps = gap_reasons(authored, audit)
    assert reasons, 'No uncovered goal'
    p = packet()
    b, _ = base(p, read(OUT / 'sources.json'))
    ctx = {**b, 'brief': authored['brief'], 'bank': visual.authored(authored['bank']),
           'previousAuthoring': {**authored, 'bank': visual.authored(authored['bank'])},
           'sourceAudit': audit, 'medical': None,
           'validation': {k: v for k, v in validation.items() if k != 'checked_at'},
           'repairReasons': reasons, '_pipeline_version': c.POLICY}
    original = rnj.task_for
    rnj.task_for = lambda stage: original(stage) + (ADD_ONLY if stage == 'repair-1' else '')
    try:
        raw, info = call('repair-1', ctx)
    finally:
        rnj.task_for = original
    write(OUT / 'repair-1.raw.json', raw)
    # The producer's own acceptance for an authoring stage …
    c.validate_authoring(raw, ctx['previousAuthoring'])
    value = copy.deepcopy(raw)
    value['bank'] = visual.render(value['bank'], raw['visual_stimuli'], p, OUT / 'material')
    # … plus the add-only rule, checked by code (not by the prompt).
    old = {q['question_id']: q for q in visual.authored(authored['bank'])['questions']}
    new = {q['question_id']: q for q in visual.authored(value['bank'])['questions']}
    changed = sorted(q for q in old if new.get(q) != old[q])
    added = sorted(q for q in new if q not in old)
    kept_conflicts = all(x in raw['clinical_conflicts'] for x in authored['clinical_conflicts'])
    kept_stimuli = all(x in raw['visual_stimuli'] for x in authored['visual_stimuli'])
    check = {'changedExisting': changed, 'added': added, 'briefUnchanged': raw['brief'] == authored['brief'],
             'conflictsKept': kept_conflicts, 'stimuliKept': kept_stimuli, 'gapGoals': gaps, 'reasons': len(reasons),
             'durationMs': info.get('duration_ms')}
    write(OUT / 'add-only-check.json', check)
    write(OUT / 'repair-1.json', value)
    print(json.dumps({k: (v if not isinstance(v, list) else len(v)) for k, v in check.items()} | {'changedExisting': changed}, ensure_ascii=False))
    assert not changed and check['briefUnchanged'] and kept_conflicts and kept_stimuli, 'Add-only rule broken — kept for inspection, not used'


def step_adopt():
    """repair-1 kept every existing question but changed the Map (recall_units on 8 goals, 2026-11-10).
    Adopt only its new questions on the frozen Map; the model's Map change stays in repair-1.raw.json."""
    check = read(OUT / 'add-only-check.json')
    assert not check['changedExisting'] and check['conflictsKept'] and check['stimuliKept'], 'Existing questions changed'
    assert not (OUT / 'repair-1-adopted.json').exists(), 'Already adopted'
    authored, raw = read(OUT / 'baseline-authoring.json'), read(OUT / 'repair-1.raw.json')
    alt = copy.deepcopy(raw)
    alt['brief'] = authored['brief']
    alt['map_change_reason'] = '추가 전용 시험: 모델이 바꾼 지도(recall_units)는 채택하지 않고 고정 지도를 쓴다.'
    c.validate_authoring(alt, authored)
    value = copy.deepcopy(alt)
    value['bank'] = visual.render(value['bank'], alt['visual_stimuli'], packet(), OUT / 'material')
    changed = [t['target_id'] for t, u in zip(authored['brief']['targets'], raw['brief']['targets']) if t != u]
    write(OUT / 'repair-1-adopted.json', value)
    write(OUT / 'adopt.json', {'reason': 'repair-1 changed the frozen Map; only its new questions are adopted',
                               'mapChangeRejectedTargets': changed, 'modelMapChangeReason': raw['map_change_reason'],
                               'questions': len(value['bank']['questions'])})
    print(json.dumps({'rejectedMapTargets': changed, 'questions': len(value['bank']['questions'])}, ensure_ascii=False))


def step_recheck():
    check = read(OUT / 'add-only-check.json')
    assert not check['changedExisting'], 'Add-only stage did not hold'
    path = OUT / 'repair-1.json' if check['briefUnchanged'] else OUT / 'repair-1-adopted.json'
    audit, info = review('source-1', read(path))
    print(json.dumps({'reviewed': path.name, 'durationMs': info.get('duration_ms')}))


SCOPED = '''
TRIAL SCOPE — NARROWED RE-CHECK (사용자 「좁힌 재확인 만들기」 2026-11-10, docs/changes/2026-11-10-add-only-trial).
input.json holds only part of this lecture on purpose: the goals that the earlier review found uncovered, and only
the questions added for them. Every other goal and question was already reviewed and is absent by design; do not
report their absence. Judge, for every listed goal, whether one of the listed questions asks the whole goal
(answer_scope with its components/relations), with the same evidence rules as above.
'''


def scoped_subset(authored, gaps, added):
    """Brief limited to the uncovered goals (all concepts kept so the tree validates), bank to the new questions."""
    b = copy.deepcopy(authored['brief'])
    targets = [x for x in b['targets'] if any(d['direction_id'] in gaps for d in x['directions'])]
    assert all(d['direction_id'] in gaps for x in targets for d in x['directions']), 'A kept target has a covered goal'
    tids = {x['target_id'] for x in targets}
    rids = {r for x in targets for r in x['relation_ids']} | {r for x in targets for d in x['directions'] for r in d['relation_ids']}
    b['targets'] = targets
    b['relations'] = [r for r in b['relations'] if r['relation_id'] in rids]
    b['points'] = [{**p, 'target_ids': [x for x in p['target_ids'] if x in tids]} for p in b['points'] if set(p['target_ids']) & tids]
    c.validate_brief(b)
    bank = copy.deepcopy(authored['bank'])
    bank['questions'] = [q for q in bank['questions'] if q['question_id'] in added]
    assert len(bank['questions']) == len(added)
    return {**authored, 'brief': b, 'bank': bank}


def step_scoped():
    check = read(OUT / 'add-only-check.json')
    assert not check['changedExisting'], 'Add-only stage did not hold'
    authored = read(OUT / ('repair-1.json' if check['briefUnchanged'] else 'repair-1-adopted.json'))
    sub = scoped_subset(authored, set(check['gapGoals']), set(check['added']))
    write(OUT / 'scoped-subset.json', {'goals': sorted(d['direction_id'] for t in sub['brief']['targets'] for d in t['directions']),
                                        'questions': [q['question_id'] for q in sub['bank']['questions']],
                                        'relations': len(sub['brief']['relations']), 'points': len(sub['brief']['points'])})
    original = rnj.task_for
    rnj.task_for = lambda stage: original(stage) + (SCOPED if stage == 'source-2' else '')
    try:
        audit, info = review('source-2', sub)
    finally:
        rnj.task_for = original
    cov = coverage(audit)
    tally = {}
    for s in cov.values():
        tally[s] = tally.get(s, 0) + 1
    print(json.dumps({'coverage': tally, 'durationMs': info.get('duration_ms')}, ensure_ascii=False))


def verdicts(audit):
    return {r['question_id']: r['verdict'] for r in audit['question_reviews']} if 'question_reviews' in audit else \
        {r['question_id']: r['verdict'] for r in audit['assessment']['assessment']['question_reviews']}


def step_compare():
    first, second = read(OUT / 'source-0.json'), read(OUT / 'source-1.json')
    check = read(OUT / 'add-only-check.json')
    c0, c1 = coverage(first), coverage(second)
    gaps = check['gapGoals']
    v0, v1 = verdicts(first['assessment']['assessment']), verdicts(second['assessment']['assessment'])
    old = [q for q in v0]
    flips = sorted((q, v0[q], v1.get(q)) for q in old if v1.get(q) != v0[q])
    gen4 = read(GEN4 / 'source-2.json')

    def tally(cov):
        out = {}
        for s in cov.values():
            out[s] = out.get(s, 0) + 1
        return out
    result = {
        'coverageBefore': tally(c0), 'coverageAfter': tally(c1),
        'gapGoals': len(gaps), 'gapGoalsNowConfirmed': sorted(d for d in gaps if c1.get(d) == 'confirmed'),
        'gapGoalsStillOpen': {d: c1.get(d) for d in gaps if c1.get(d) != 'confirmed'},
        'confirmedLost': sorted(d for d, s in c0.items() if s == 'confirmed' and c1.get(d) != 'confirmed'),
        'added': check['added'], 'addedVerdicts': {q: v1.get(q) for q in check['added']},
        'existingVerdictFlips': flips,
        'generation4Final': {'coverage': tally(coverage(gen4)), 'questions': len(verdicts(gen4['assessment']['assessment']))},
    }
    write(OUT / 'compare.json', result)
    print(json.dumps(result, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    {'prepare': prepare, 'coverage': step_coverage, 'add': step_add, 'adopt': step_adopt, 'recheck': step_recheck, 'scoped': step_scoped, 'compare': step_compare}[sys.argv[1]]()

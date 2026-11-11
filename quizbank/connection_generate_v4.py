"""root-generation/4: exam points are a coverage checklist (docs/changes/2026-11-10-importance-at-authoring).

The /3 run (connection_generate_v3) with these differences (spec R1-R7):
- each authoring output (intake bank, add, fix) names its questions' importance basis (`question_importance`);
  tiers are computed from it at assembly, and the exam points carry none;
- coverage is the union of answered components; an add stage receives only the components nobody asks;
- the coverage judgment names true duplicates; every source-ok question becomes a task except merged duplicates;
- the map check sees no importance, and the item review may leave an importance note that decides nothing.
Stage names are `v4-<kind>…` so the runner uses the /4 schemas, checks and prompts (content/prompts/learning-links/v4,
falling back to v3/ for prompts that did not change). The /3 module is not changed in behaviour.
"""
import copy
import json
from pathlib import Path

from studyez_llm import codex
from studyez_contracts.roots import document_hash
from studyez_contracts.roots import generation_v2 as v2
from studyez_contracts.roots import generation_v3 as v3
from studyez_contracts.roots import generation_v4 as v4
from studyez_contracts.roots import map_tree
from studyez_contracts.roots.automation import validate_checks
from studyez_contracts.bank.validate import validate_bank
from . import connection_batches as batches
from . import connection_visuals as visual
from .connection_generate_v3 import (Stages, chunks, _bank_findings, _join_points, _medical_batches, _state,
                                     intake_rejections,
                                     COVERAGE_CHUNK, REVIEW_BATCH, ADD_PER_GOAL)

POLICY = v4.POLICY
X = 'v4-'


# ---------------------------------------------------------------- helpers
def _goals(brief):
    return {d['direction_id']: d for t in brief['targets'] for d in t['directions']}


def _merge_row(old, new, goal, replaced=()):
    """Coverage of one goal after a narrower judgment (union rule, R5): evidence and duplicate groups of the
    replaced/newly judged questions come from `new`; the status follows from the merged evidence."""
    if old is None:
        return new
    renewed = set(replaced) | {e['question_id'] for e in new['evidence']}
    keep = [e for e in old['evidence'] if e['question_id'] not in renewed]
    row = {'direction_id': new['direction_id'], 'evidence': keep + copy.deepcopy(new['evidence'])}
    asking = {e['question_id'] for e in row['evidence'] if v4.answered(e)}
    groups = [g for g in old.get('duplicates', []) if not set(g['question_ids']) & renewed] + copy.deepcopy(new['duplicates'])
    seen, kept_groups = set(), []
    for g in groups:
        ids = [q for q in g['question_ids'] if q in asking and q not in seen]
        if len(ids) >= 2:
            kept_groups.append({**g, 'question_ids': ids})
            seen |= set(ids)
    row['duplicates'] = kept_groups
    if new['status'] == 'unknown' and old['status'] == 'unknown':
        row['status'] = 'unknown'
    else:
        row['status'] = 'covered' if v4.full(row, goal) else 'missing'
    row['reason'] = new['reason'] if new['status'] != 'unknown' else old['reason']
    return row


def _intake(packet, out):
    """The independent bank with each question's basis; questions with format errors are left out (as /3)."""
    intake = copy.deepcopy(packet['intakeBank'])
    basis = v4.check_intake(intake)
    bank, projection = v3.intake_projection(intake['bank'])
    sources = [s['id'] for s in packet['sources']]
    report = validate_bank(bank, sources)
    rejected = intake_rejections(report['errors'])
    bad = {r['question_id'] for r in rejected}
    if bad:
        bank['questions'] = [q for q in bank['questions'] if q['question_id'] not in bad]
        for q in bank['questions']:
            q['prerequisites'] = [p for p in q.get('prerequisites', []) if p not in bad]
        intake['visual_stimuli'] = [s for s in intake['visual_stimuli'] if s['question_id'] not in bad]
        basis = {q: b for q, b in basis.items() if q not in bad}
    rendered = visual.render(bank, intake['visual_stimuli'], packet, out / 'material')
    return rendered, intake['visual_stimuli'], intake['clinical_conflicts'], rejected, projection, basis


def check_stage(kind, value, ctx, state, scratch):
    """/4 version of connection_generate_v3.check_stage: the same merge and render, with the /4 output shapes."""
    if kind == 'supplement-normalize':
        return v3.check_supplement_normalize(value, ctx, state)
    if kind == 'supplement':
        return v4.check_supplement(value, ctx, state)
    scratch = Path(scratch)
    scratch.mkdir(parents=True, exist_ok=True)
    if kind == 'add':
        v4.check_added(value, ctx)
        merged, _ = v3.merge_added(state['bank'], state['clinical_conflicts'], v4.without_basis(value), ctx['allowed_question_ids'])
        stimuli = [*state['stimuli'], *value['visual_stimuli']]
    else:
        v4.check_fixed(value, ctx)
        merged, _, changed = v3.merge_fixes(state['bank'], state['clinical_conflicts'], v4.without_basis(value),
                                            [q['question_id'] for q in ctx['questions']])
        stimuli = [s for s in state['stimuli'] if s['question_id'] not in set(changed)] + value['visual_stimuli']
    visual.render(merged, stimuli, {'sources': state['sources']}, scratch)
    return value


# ---------------------------------------------------------------- run
def run(packet, out, model, invoke, resume=None):
    from . import connection_generate as g
    out = Path(out)
    v3.require(packet.get('generationPolicy') == POLICY, 'root-generation/4 packet required')
    sources = g.prepare(packet, out / 'material')
    page_counts = {s['source_id']: s['page_count'] for s in sources}
    # review-evidence/1 (docs/changes/2026-11-11-evidence-from-citations): a new run's item review names the notes
    # pages of each answer; an older ledger keeps reviewing without them.
    evidence_notes = v4.evidence_source(sources)
    # review-relations/1 (docs/changes/2026-11-11-place-by-review): a new run places each question by the map relations
    # its item review names; the goal coverage judgment only finds what is not asked yet.
    fresh = {'placement': {'policy': v4.REVIEW_PLACEMENT}}
    if evidence_notes:
        fresh['reviewEvidence'] = {'policy': v4.REVIEW_EVIDENCE, 'sourceId': evidence_notes['source_id']}
    st = Stages(packet, out, model, invoke, resume, policy=POLICY, prompts=('v3', 'v4'), fresh=fresh)
    ledger = st.ledger
    evidence_on = ledger.get('reviewEvidence', {}).get('policy') == v4.REVIEW_EVIDENCE
    placement = 'review' if ledger.get('placement') == {'policy': v4.REVIEW_PLACEMENT} else 'evidence'
    base = {k: packet[k] for k in ('title', 'scope', 'conceptMap', 'points', 'examDate')}
    base.update(lecture_id=packet['subject'] + '/' + packet['runId'], sources=sources,
                preserved_scope=g.lecture_scope(packet['title'], packet['sources']))
    points_doc = v4.check_points(json.loads(packet['points']))
    profile = points_doc['notebook_profile']

    # 1c: intake bank and its basis ------------------------------------------
    bank, stimuli, conflicts, rejected, intake_changes, basis = _intake(packet, out)
    initial_bank = copy.deepcopy(bank)
    intake_conflict_ids = {c['conflict_id'] for c in [*bank.get('source_conflicts', []), *conflicts]}

    # normalize (+ one structural correction); target importance is computed at assembly -------------
    def accept_brief(raw):
        v2.validate_shape(raw, v2.BRIEF, 'initial brief2')
        value = v2.blank_target_importance(raw)
        if value['scope']['label'] != packet['title']:
            value = {**value, 'scope': {**value['scope'], 'label': packet['title']}}
        v3.require(raw['sources'] == sources and raw['lecture_id'] == base['lecture_id'], 'Different initial source/lecture')
        return value
    brief = st.run('normalize', base, accept_brief)
    initial_brief = brief
    findings = v2.brief_findings(brief)
    if findings:
        fixed = st.run(X + 'brief-fix', {'brief': brief, 'errors': findings, 'pages': []},
                       lambda raw: v3.check_brief_fix(raw, {'brief': brief}))
        brief = v2.blank_target_importance(fixed['brief'])

    def judge(name, ctx, stages=None):
        return (stages or st).judged(name, ctx, lambda raw, ctx=ctx: v4.check_coverage(raw, ctx['goals'], ctx['questions']))

    # 2: coverage (union rule, duplicates), 2m: map check without importance -------------------------
    # Independent judgments: side by side in a new run (docs/changes/2026-11-11-root-batch-parallel).
    rows = {}
    dids = [d['direction_id'] for t in brief['targets'] for d in t['directions']]
    calls = [(f'{X}coverage-0-{k}', ctx, lambda raw, ctx=ctx: v4.check_coverage(raw, ctx['goals'], ctx['questions']))
             for k, ctx in enumerate(v3.coverage_input(brief, bank, part) for part in chunks(dids, COVERAGE_CHUNK))]
    ctx = v4.map_check_input(brief)
    calls.append((X + 'map-check-0', ctx, lambda raw, ctx=ctx: v3.check_map_input(raw, ctx)))
    values = batches.judgments(st, calls)
    for value in values[:-1]:
        rows.update({r['direction_id']: r for r in value['rows']})
    map_checks = [values[-1]]

    # 2a: off-goal questions → supplement points (no basis) ------------------
    off_goal = v4.off_goal(bank, rows.values(), placement)
    supplement, out_of_scope = [], []
    if off_goal:
        ctx = v3.supplement_input(bank, off_goal, points_doc, page_counts)
        state = {'points_doc': points_doc}
        value = st.run(X + 'supplement', ctx, lambda raw: check_stage('supplement', raw, ctx, state, None), state)
        points_doc, supplement = v4.attach_points(points_doc, value, off_goal, page_counts)
        new_points = [p for p in points_doc['points'] if p['point_id'] in {d['point_id'] for d in supplement if d['decision'] == 'point'}]
        dup = [d for d in supplement if d['decision'] == 'duplicate_of']
        out_of_scope = [d for d in supplement if d['decision'] == 'out_of_scope']
        if new_points:
            allowed = v3.supplement_ids(brief, len(new_points))
            ctx = v3.supplement_normalize_input(brief, new_points, allowed)
            state = {'brief': brief, 'blank': True}
            addition = st.run(X + 'supplement-normalize', ctx, lambda raw: check_stage('supplement-normalize', raw, ctx, state, None), state)
            brief, new_tids = v3.extend_brief(brief, v3.supplement_addition(brief, addition, True), [p['point_id'] for p in new_points])
            new_dids = [d['direction_id'] for t in brief['targets'] if t['target_id'] in new_tids for d in t['directions']]
            origins = [p['origin_question_id'] for p in new_points]
            value = judge(X + 'coverage-supplement', v3.coverage_input(brief, bank, new_dids, origins))
            rows.update({r['direction_id']: r for r in value['rows']})
            ctx = v4.map_check_input(brief, new_tids)
            map_checks.append(st.judged(X + 'map-check-1', ctx, lambda raw, ctx=ctx: v3.check_map_input(raw, ctx)))
        if dup:
            owner = {d['direction_id']: t for t in brief['targets'] for d in t['directions']}
            goal_ids = sorted({did for d in dup for did, t in owner.items()
                               if any(d['point_id'] in p['point_id'] and t['target_id'] in p['target_ids'] for p in brief['points'])})
            if goal_ids:
                value = judge(X + 'coverage-duplicate', v3.coverage_input(brief, bank, goal_ids, [d['question_id'] for d in dup]))
                for r in value['rows']:
                    rows[r['direction_id']] = _merge_row(rows.get(r['direction_id']), r, _goals(brief)[r['direction_id']])
        gone = {d['question_id'] for d in out_of_scope}
        off_questions = [q for q in bank['questions'] if q['question_id'] in gone]
        bank['questions'] = [q for q in bank['questions'] if q['question_id'] not in gone]
        for q in bank['questions']:
            if set(q.get('prerequisites', [])) & gone:
                q['prerequisites'] = [p for p in q['prerequisites'] if p not in gone]
        stimuli = [s for s in stimuli if s['question_id'] not in gone]
        basis = {q: b for q, b in basis.items() if q not in gone}
    else:
        off_questions = []
    bank = _join_points(bank, brief, rows)

    # 3: add only the unasked components (≤2 rounds) -------------------------
    restated = []
    for n in range(v3.ADD_LIMIT):
        goals = _goals(brief)
        gaps = {did: v4.missing_components(rows[did], goals[did]) for did in goals if rows[did]['status'] != 'covered'}
        if not gaps:
            break
        allowed = v3.next_question_ids(bank, ADD_PER_GOAL * len(gaps))
        ctx = v4.add_input(brief, bank, gaps, allowed)
        if ledger['addRounds'] < n + 1:
            ledger['addRounds'] = n + 1
            st.save()
        state = _state(bank, conflicts, stimuli, packet)
        value = st.run(f'{X}add-{n}', ctx, lambda raw, ctx=ctx, state=state, n=n: check_stage('add', raw, ctx, state, out / '.check-render' / f'{X}add-{n}'), state)
        plain = v4.without_basis(value)
        restated.extend({'stage': f'{X}add-{n}', **r} for r in v3.restated(visual.authored(bank), conflicts, plain))
        bank, conflicts = v3.merge_added(visual.authored(bank), conflicts, plain, allowed)
        basis.update(v4.collect_basis(value['question_importance'], [q['question_id'] for q in value['questions']]))
        stimuli = [*stimuli, *value['visual_stimuli']]
        bank = visual.render(bank, stimuli, packet, out / 'material')
        added = [q['question_id'] for q in value['questions']]
        for k, part in enumerate(chunks(list(gaps), COVERAGE_CHUNK)):
            got = judge(f'{X}coverage-{n + 1}-{k}', v3.coverage_input(brief, bank, part, added))
            for r in got['rows']:
                rows[r['direction_id']] = _merge_row(rows[r['direction_id']], r, goals[r['direction_id']])

    # 4: item review and fixes by batch ---------------------------------------
    # Batches start from one snapshot and run side by side unless a conflict record or a prerequisite link joins
    # two of them (connection_batches, docs/changes/2026-11-11-root-batch-parallel); otherwise one after another.
    source_ids = [s['id'] for s in packet['sources']]

    def covered_by(S):
        cov = {}
        for did, r in S.rows.items():
            for q in v4.covering(r):
                cov.setdefault(q, []).append(did)
        return cov

    def review_batch(S, stages, name, qids):
        got, todo = {}, []
        for q in S.bank['questions']:
            if q['question_id'] not in qids:
                continue
            again = v3.reusable(S.verdicts, 'item', q['question_id'], v3.item_hash(q, S.bank, S.conflicts))
            if again is not None:
                got[q['question_id']] = again
            else:
                todo.append(q['question_id'])
        if not todo:
            return got
        ctx = v4.with_importance(v3.review_input(S.bank, todo, S.conflicts), S.basis)
        if evidence_on:
            ctx['evidence_source'] = evidence_notes
        if placement == 'review':
            ctx['map_relations'] = v4.map_relations(brief, map_checks)
        value = stages.judged(name, ctx, lambda raw: v4.check_review_input(raw, ctx))
        by_id = {q['question_id']: q for q in S.bank['questions']}
        for r in value['reviews']:
            got[r['question_id']] = r
            entry = v3.ledger_entry('item', r['question_id'], v3.item_hash(by_id[r['question_id']], S.bank, S.conflicts), r, name)
            if entry not in S.verdicts:
                S.verdicts.append(entry)
        st.save()
        return got

    def fix_round(S, stages, name, review_name, coverage_name, targets, findings):
        ctx = v4.with_importance(v3.fix_input(S.bank, findings, targets, S.conflicts, covered_by(S)), S.basis)
        if S.scope:
            ctx['conflict_scope'] = S.scope
        state = _state(S.bank, S.conflicts, S.stimuli, packet)
        value = stages.run(name, ctx, lambda raw, ctx=ctx, state=state: check_stage('fix', raw, ctx, state, out / '.check-render' / name), state)
        plain = v4.without_basis(value)
        before = (copy.deepcopy(S.bank), copy.deepcopy(S.conflicts), copy.deepcopy(S.stimuli), copy.deepcopy(S.basis))
        before_reviews = {q: S.reviews[q] for q in targets}
        cited = {q.get('conflict_id') for q in plain['questions'] if q.get('conflict_id')}
        S.restated.extend({'stage': name, **r} for r in v3.restated(visual.authored(S.bank), S.conflicts, plain, cited))
        merged, S.conflicts, changed = v3.merge_fixes(visual.authored(S.bank), S.conflicts, plain, targets)
        fixed_basis = v4.collect_basis(value['question_importance'], [q['question_id'] for q in value['questions']])
        S.basis.update({q: fixed_basis[q] for q in changed})
        S.stimuli = [s for s in S.stimuli if s['question_id'] not in set(changed)] + value['visual_stimuli']
        S.bank = visual.render(merged, S.stimuli, packet, S.material)
        again = review_batch(S, stages, review_name, set(changed))
        reverted = [q for q in changed if q in again and v3.worse(before_reviews[q], again[q])]
        kept = [q for q in changed if q not in reverted]
        if reverted and not kept:
            S.bank, S.conflicts, S.stimuli, S.basis = before
        elif reverted:
            part = v3.fixes_of(plain, kept)
            merged, S.conflicts, _ = v3.merge_fixes(visual.authored(before[0]), before[1], part, targets)
            S.stimuli = [s for s in before[2] if s['question_id'] not in set(kept)] + part['visual_stimuli']
            S.bank = visual.render(merged, S.stimuli, packet, S.material)
            S.basis = {**before[3], **{q: fixed_basis[q] for q in kept}}
        for q in changed:
            S.reviews[q] = before_reviews[q] if q in reverted else again.get(q, S.reviews[q])
            S.fixes.append({'question_id': q, 'attempt': S.attempts[q], 'stage': name, 'reverted': q in reverted})
        goal_ids = sorted({did for q in kept for did, r in S.rows.items() if any(e['question_id'] == q for e in r['evidence'])})
        if goal_ids:
            # A fixed question is judged again with its duplicate partners, so the group is decided anew, not dropped.
            partners = {p for did in goal_ids for grp in S.rows[did].get('duplicates', []) if set(grp['question_ids']) & set(kept)
                        for p in grp['question_ids']}
            judged_ids = [q['question_id'] for q in S.bank['questions'] if q['question_id'] in set(kept) | partners]
            got = judge(coverage_name, v3.coverage_input(brief, S.bank, goal_ids, judged_ids), stages)
            for r in got['rows']:
                S.rows[r['direction_id']] = _merge_row(S.rows[r['direction_id']], r, _goals(brief)[r['direction_id']], judged_ids)
            S.coverage.append((got['rows'], judged_ids, goal_ids))

    def count_attempts(S, targets):
        with st.lock:
            for q in targets:
                S.attempts[q] = S.attempts.get(q, 0) + 1
                ledger['fixAttempts'][q] = max(ledger['fixAttempts'].get(q, 0), S.attempts[q])
            st.save()

    def batch_body(b, batch, S, stages):
        S.reviews.update(review_batch(S, stages, f'{X}review-{b}-0', set(batch)))
        for k in range(v3.FIX_LIMIT):
            code = _bank_findings(S.bank, source_ids, S.attempts)
            targets = [q for q in batch if (v3.needs_fix(S.reviews[q]) or q in code) and S.attempts.get(q, 0) < v3.FIX_LIMIT]
            if not targets:
                break
            count_attempts(S, targets)
            findings = [{**S.reviews[q], 'code_findings': code.get(q, [])} for q in targets]
            fix_round(S, stages, f'{X}fix-{b}-{k}', f'{X}review-{b}-{k + 1}', f'{X}coverage-fix-{b}-{k}', targets, findings)

    def apply_coverage(rows_, got_rows, judged_ids):
        for r in got_rows:
            rows_[r['direction_id']] = _merge_row(rows_[r['direction_id']], r, _goals(brief)[r['direction_id']], judged_ids)

    order = [q['question_id'] for q in bank['questions']]
    batch_ids = chunks(order, REVIEW_BATCH)
    start = batches.Batch(bank=bank, conflicts=conflicts, stimuli=stimuli, basis=basis, rows=rows, reviews={}, fixes=[], attempts={},
                          restated=restated, verdicts=ledger['verdictLedger'])
    S = batches.review_phase(st, out, batch_ids, start, batch_body, apply_coverage)
    if S is not start:
        # A batch judged a duplicate partner from another batch that the other batch then changed: those goals are
        # judged once more on the merged bank (spec R6).
        stale = batches.stale_coverage(S, batch_ids, start)
        if stale:
            goal_ids, judged_ids = stale
            got = judge(X + 'coverage-merge-0', v3.coverage_input(brief, S.bank, goal_ids, judged_ids))
            apply_coverage(S.rows, got['rows'], judged_ids)
    bank, conflicts, stimuli, basis, rows = S.bank, S.conflicts, S.stimuli, S.basis, S.rows
    reviews, fixes, attempts, restated = S.reviews, S.fixes, S.attempts, S.restated

    # context per conflict record (+ one repair), as /3 -------------------------
    def context_judgment(name, conflict_ids=None, question_ids=None):
        nonlocal bank, conflicts
        bank, conflicts, orphans = v3.drop_orphans(bank, conflicts, intake_conflict_ids)
        restated.extend({'stage': name, 'kind': 'orphan_conflict', 'id': cid, 'changed': True} for cid in orphans
                        if not any(r['kind'] == 'orphan_conflict' and r['id'] == cid for r in restated))
        v3.check_integrity(bank, conflicts, stimuli, intake_conflict_ids)
        ctx = v3.context_input(bank, conflicts, conflict_ids, question_ids)
        return st.judged(name, ctx, lambda raw, ctx=ctx: v3.check_context(raw, ctx))
    context_judgments = [context_judgment(X + 'context-0')]
    targets = v3.context_repair_targets(bank, context_judgments[0], attempts)
    if targets:
        ledger.setdefault('contextRepairs', [])
        if not ledger['contextRepairs']:
            ledger['contextRepairs'].append({'stage': X + 'context-0', 'open': v3.context_open(context_judgments[0]), 'targets': targets})
        count_attempts(S, targets)
        notes = v3.context_findings(bank, context_judgments[0], targets)
        code = _bank_findings(bank, source_ids, attempts)
        findings = [{**reviews[q], 'code_findings': [*code.get(q, []), *notes.get(q, [])]} for q in targets]
        S.bank, S.conflicts, S.stimuli, S.basis = bank, conflicts, stimuli, basis
        fix_round(S, batches.BatchStages(st, S), X + 'fix-context-0', X + 'review-context-1', X + 'coverage-fix-context-0', targets, findings)
        bank, conflicts, stimuli, basis = S.bank, S.conflicts, S.stimuli, S.basis
        present = {c['conflict_id'] for c in [*bank.get('source_conflicts', []), *conflicts]}
        cited = {q['conflict_id'] for q in bank['questions'] if q.get('conflict_id')} | set(intake_conflict_ids)
        again = sorted(({q['conflict_id'] for q in bank['questions'] if q['question_id'] in set(targets) and q.get('conflict_id')}
                        | (present - {r['conflict_id'] for r in context_judgments[0]['conflicts']})) & cited)
        context_judgments.append(context_judgment(X + 'context-1', again, targets))
    context = v3.context_merge(context_judgments[0], context_judgments[1] if len(context_judgments) == 2 else None, bank, conflicts,
                               ledger['contextRepairs'][0]['targets'] if ledger.get('contextRepairs') else ())

    # notes citations follow the last review's evidence pages, once after every fix (R2, no model call) -------
    alignments = None
    if evidence_on:
        bank, alignments = v4.align_citations(bank, reviews, ledger['reviewEvidence']['sourceId'])
        if alignments:
            print(f"── 인용 쪽 맞춤 {len(alignments)}문항 (검토 근거 쪽으로)", flush=True)

    # assembly (before the medical review) ----------------------------------------
    coverage_rows = [rows[d['direction_id']] for t in brief['targets'] for d in t['directions']]
    review_rows = [reviews[q['question_id']] for q in bank['questions']]
    map_check = {k: [x for m in map_checks for x in m[k]] for k in ('relation_checks', 'target_checks', 'direction_checks', 'issues')}
    relation_seen = {}
    for r in map_check['relation_checks']:
        relation_seen.setdefault(r['relation_id'], r)
    map_check['relation_checks'] = list(relation_seen.values())
    summary = ('root-generation/4: coverage (union of answered components), map check without importance, item review and '
               'per-conflict context judgments gathered by studyez_contracts.roots.generation_v4.assessment_raw; no judgment is filled in.')
    raw = v4.assessment_raw(brief, bank, coverage_rows, map_check, review_rows, v3.context_summary(context), summary, placement)
    audit = v4.compile_assessment(brief, bank, v2.envelope(brief, bank, raw), placement)
    basis = {q['question_id']: basis[q['question_id']] for q in bank['questions']}
    doc, placed, proofs = v4.assemble(brief, bank, audit, coverage_rows, basis, profile,
                                      revision=packet['revision'], title=packet['title'], exam_date=packet['examDate'],
                                      placement=placement)
    ready_rows = v4.readiness(brief, coverage_rows, doc)
    covered = sum(1 for r in ready_rows if r['covered'])
    print(f"── 조립 예행: 목표 {len(ready_rows)}개 중 전부 출제됨 {covered}개 · 과제 {len(doc['tasks'])}개 · "
          f"중복으로 합침 {len(placed['mergedDuplicates'])}개 · 목표 없음 {len(placed['unplacedQuestions'])}개", flush=True)
    g.write(out / 'readiness.json', {'rows': ready_rows, **placed, 'importanceWarnings': proofs['importanceWarnings']})
    v3.require(doc['tasks'], '학습 가능한 과제가 0개입니다. 의학 검토 전에 멈춥니다. readiness.json을 보세요.')

    # medical (once, medical-final/1) ----------------------------------------------
    clinical_input, _ = v3.medical_parts(bank, v3.context_sent(conflicts, context))
    med_ctx = {'title': packet['title'], 'bank': bank, 'clinicalInput': clinical_input, 'medicalFinal': True}
    st.invoke = _medical_batches(invoke, workers=batches.BATCH_WORKERS if st.parallel else 1)
    medical = st.run('medical-0', med_ctx, lambda raw: validate_checks(raw, bank))
    medical_unreviewed = [{'question_id': r['question_id'], 'reason': r['note'][len(v3.UNREVIEWED_NOTE):]}
                          for r in medical['reviews'] if r['note'].startswith(v3.UNREVIEWED_NOTE)]
    st.retire_legacy()

    snapshot = doc['bank_snapshot']
    result = {'brief': brief, 'document': doc, 'sourceAudit': audit, 'medical': medical,
              'validation': validate_bank(snapshot, source_ids), 'manifest': {
                  'pipelineVersion': POLICY, 'inputHash': packet['inputHash'], 'briefHash': document_hash(brief),
                  'bankHash': document_hash(snapshot), 'model': codex.model_name(model), 'runtimeHash': ledger['identity'],
                  'stages': [{'name': k, **v} for k, v in ledger['stages'].items()],
                  'verdictLedger': ledger['verdictLedger'], 'verdictLedgerHash': document_hash(ledger['verdictLedger']),
                  'addRounds': ledger['addRounds'], 'notReady': v4.not_ready(brief, coverage_rows, review_rows),
                  'offGoalQuestions': [{'question_id': q['question_id'], 'question': q,
                                        'reason': next(d['reason'] for d in out_of_scope if d['question_id'] == q['question_id'])}
                                       for q in off_questions],
                  'rejectedAtIntake': rejected, 'intakeProjection': intake_changes, 'restatedIgnored': restated,
                  'supplement': supplement, 'supplementPoints': points_doc if supplement else None,
                  'initialBrief': initial_brief, 'initialBank': initial_bank, 'coverage': coverage_rows, 'mapCheck': map_check,
                  'itemReviews': review_rows, 'clinicalContext': context, 'contextJudgments': context_judgments,
                  'medicalUnreviewed': medical_unreviewed, 'readiness': ready_rows, 'clinicalConflicts': conflicts,
                  'visualStimuli': stimuli, 'medicalFinal': True, 'sourceAssessment': raw, 'fixes': fixes,
                  'questionImportance': basis, 'importanceNotes': v4.importance_notes(review_rows),
                  'importanceWarnings': proofs['importanceWarnings'], **placed,
                  **({'bankProjection': proofs['bankProjection']} if proofs['bankProjection'] else {}),
                  'importanceProjection': proofs['importanceProjection'],
                  **({'stageResumes': ledger['stageResumes']} if ledger.get('stageResumes') else {}),
                  **({'reviewRetries': ledger['reviewRetries']} if ledger.get('reviewRetries') else {}),
                  **({'contextRepairs': ledger['contextRepairs']} if ledger.get('contextRepairs') else {}),
                  **({'batchPhases': ledger['batchPhases']} if ledger.get('batchPhases') else {}),
                  **({'reviewEvidence': ledger['reviewEvidence'], 'citationAlignments': alignments} if evidence_on else {}),
                  **({'placement': ledger['placement']} if placement == 'review' else {}),
                  **({'derivedPacket': map_tree.public(packet), 'auditOpen': packet['frontStages']['openPoints']}
                     if 'derivedFrom' in packet else {})}}
    v4.validate_result(result, packet)
    g.write(out / 'result.json', result)
    return result

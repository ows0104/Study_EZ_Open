"""presuppose-only/1: existence goals added to a published root-generation/4 revision (docs/changes/2026-11-15-tree-edge-goals
spec R6, 사용자 「처음부터 재출제는 에바, 옛날꺼는 보강만」).

A lecture published before presuppose/1 asks details whose upper link (A has / causes / is treated with B) its stems
hand over and no question asks. This run starts from that published run (`previous`, its generation folder), as
unplaced-only/1 does, and only adds:

- the stem judgment `v4-presuppose-<k>` over every question of the published bank (questions do not change);
- for links nobody recalls, existence goals (`v4-supplement-normalize-presuppose`, `v4-coverage-presuppose`,
  `v4-map-check-presuppose`), their questions (`v4-add-presuppose-<n>`, ≤ ADD_LIMIT rounds), the item review and
  fixes of those new questions only (`v4-review-presuppose-<k>`, `v4-fix-presuppose-<k>`, ≤ FIX_LIMIT);
- the medical review of the new questions only (`medical-presuppose`): the published review stands for the rest;
- the study-order prerequisites at assembly (presuppose/1).

Every published question, ID, task, judgment and medical verdict stays. New questions may not add clinical conflict
records: the published context judgment covers the bank's conflicts and is not judged again.
The map is not checked again; the result is an ordinary /4 result the server takes as the restart that replaces the
published revision.

Fill mode (`fill`, docs/changes/2026-11-17-fill-recovery, 사용자 「얹기로 하자」·「11-16 네 편 복구해줘」): a revision that
was already judged (first made with presuppose/1 and discriminate/1) is not judged again — a second judgment would make a
second goal for the same link. An operator's record names the goals to write questions for (`goals`, their unasked
components) and, at most, published questions to write again from a finding (`rewrite`). Everything after the judgment is
the same run: one add round, review and fixes of those questions, their medical review, the pinned assembly and the
carry check. A rewritten question changes, so its own learning history starts over; it is the only one that does.
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
from studyez_contracts.roots import presuppose as pre
from studyez_contracts.roots import discriminate as dis
from studyez_contracts.roots.automation import validate_checks
from studyez_contracts.bank.validate import validate_bank
from . import connection_batches as batches
from . import connection_dedupe as dedupe
from . import connection_visuals as visual
from .connection_generate_v3 import Stages, chunks, _bank_findings, _medical_batches, _state, ADD_PER_GOAL, COVERAGE_CHUNK
from .connection_generate_v4 import _goals, _merge_row, _first_evidence, check_stage

# One add round: every existence goal gets its one question in it (pre.written_for keeps a second round from asking it
# again). On the 2026-11-16 trial the second round only wrote four stray questions (two never placed) for about three
# minutes a lecture (docs/changes/2026-11-16-presuppose-faster).
ADD_ROUNDS = 1

POLICY = 'presuppose-only/1'
X = 'v4-'
TAG = '-presuppose'
RTAG = '-discriminate'
LABEL = '존재 목표 보강'
MEDICAL = 'medical' + TAG


def _no_new_conflicts(before, conflicts):
    v3.require([c['conflict_id'] for c in conflicts] == [c['conflict_id'] for c in before],
               f'{LABEL}: 새 문항은 임상 충돌 기록을 더하지 않습니다(공개된 판의 맥락 판정을 다시 하지 않습니다).')


def check_fill(fill, old):
    """The operator's fill record against the published revision it was written for. Returns it normalized."""
    v3.require(type(fill) is dict and type(fill.get('goals')) is list and type(fill.get('rewrite', [])) is list
               and all(type(fill.get(k)) is str and fill[k].strip() for k in ('previousRevision', 'reason', 'approval', 'at')),
               f'{LABEL}: 채우기 기록의 형식이 다릅니다(previousRevision·goals·reason·approval·at).')
    v3.require(fill['previousRevision'] == old['document']['revision'],
               f"{LABEL}: 채우기 기록은 다른 판({fill['previousRevision']})을 위한 것입니다.")
    goals = {d['direction_id'] for t in old['brief']['targets'] for d in t['directions']}
    v3.require(len(fill['goals']) == len(set(fill['goals'])) and set(fill['goals']) <= goals,
               f"{LABEL}: 채우기 목표가 이 판의 지도에 없습니다: {sorted(set(fill['goals']) - goals)}")
    questions = {q['question_id'] for q in old['document']['bank_snapshot']['questions']}
    rewrite = fill.get('rewrite', [])
    v3.require(all(type(r) is dict and set(r) == {'question_id', 'note', 'fix'} and r['question_id'] in questions
                   and all(type(r[k]) is str and r[k].strip() for k in ('note', 'fix')) for r in rewrite)
               and len({r['question_id'] for r in rewrite}) == len(rewrite),
               f'{LABEL}: 다시 쓸 문항 기록의 형식이 다르거나 이 판에 없는 문항입니다(question_id·note·fix).')
    v3.require(fill['goals'] or rewrite, f'{LABEL}: 채우기 기록에 목표도 다시 쓸 문항도 없습니다.')
    return {'previousRevision': fill['previousRevision'], 'goals': list(fill['goals']), 'rewrite': copy.deepcopy(rewrite),
            'reason': fill['reason'], 'approval': fill['approval'], 'at': fill['at']}


def fill_gaps(goal_ids, rows, brief, presuppositions, discriminations, bank):
    """The listed goals with what a new question has to answer: an existence or reverse goal whole (as their own gap
    rules give it), any other goal its unasked components. A listed goal that lacks nothing is left out."""
    goals = _goals(brief)
    existence = pre.existence_gaps(rows, brief, presuppositions) if presuppositions else {}
    reverse = dis.gaps(brief, discriminations, bank) if discriminations else {}
    gaps = {}
    for did in goal_ids:
        missing = existence.get(did) or reverse.get(did) or v4.missing_components(rows[did], goals[did])
        if missing:
            gaps[did] = missing
    return gaps


def run(packet, out, model, invoke, previous, resume=None, fill=None):
    from . import connection_generate as g
    out, previous = Path(out), Path(previous)
    v3.require(packet.get('generationPolicy') == v4.POLICY, f'{LABEL}은 root-generation/4 packet만 받습니다.')
    # Every published task stays: without the earlier revisions' fingerprints the new revision would start every learner
    # over (docs/changes/2026-11-15-replace-carry-records).
    v3.require(packet.get('carrySources'), f'{LABEL}: 이전 판 문항 지문(carrySources)이 없어 학습 기록을 이을 수 없습니다. '
               '새 서버에서 다시 요청하세요.')
    old_packet = json.loads((previous / 'packet.json').read_text(encoding='utf-8'))
    old = json.loads((previous / 'result.json').read_text(encoding='utf-8'))
    v4.validate_result(old, old_packet)
    v3.require(dedupe.lecture_input(old_packet) == dedupe.lecture_input(packet), f'{LABEL}: 이전 실행과 강의 입력이 다릅니다.')
    v3.require(old['document']['revision'] != packet['revision'], f'{LABEL}: 새 판 이름이 이전 판과 같습니다.')
    v3.require(codex.model_name(model) == old['manifest']['model'],
               f"{LABEL}: 이전 실행의 모델({old['manifest']['model']})과 지금 모델({codex.model_name(model)})이 다릅니다.")
    meta, brief = old['manifest'], old['brief']
    if fill is None:
        v3.require('presuppositions' not in meta, f'{LABEL}: 이미 presuppose/1로 만든 판입니다.')
        v3.require('discriminations' not in meta, f'{LABEL}: 이미 discriminate/1로 만든 판입니다.')
    else:
        fill = check_fill(fill, old)
        v3.require('presuppositions' in meta or 'discriminations' in meta,
                   f'{LABEL}: 채우기는 전제·역방향 판정을 이미 거친 판만 받습니다(아닌 판은 보강으로 요청하세요).')
        # A second backfill of one lecture would run stages of the same names (v4-add-presuppose-0, medical-presuppose).
        v3.require('presupposeOnly' not in meta, f'{LABEL}: 이미 보강한 판은 다시 채우지 않습니다.')
    v3.require(meta.get('placement') in ({'policy': v4.REVIEW_PLACEMENT}, {'policy': v4.REVIEW_PLACEMENT2}),
               f'{LABEL}: 문항 검토 배치(review-relations) 실행만 받습니다.')
    dedupe.seed(previous, out, packet, model, old, key='presupposeOnly', policy=POLICY, label=LABEL,
                extra={'placement': {'policy': v4.REVIEW_PLACEMENT2}, 'presuppositions': {'policy': pre.PRESUPPOSE},
                       'discriminations': {'policy': dis.DISCRIMINATE}})
    st = Stages(packet, out, model, invoke, resume or packet.get('restartReason') or LABEL, policy=v4.POLICY, prompts=('v3', 'v4'))
    ledger = st.ledger
    v3.require(ledger.get('presupposeOnly', {}).get('previousRevision') == old['document']['revision'],
               f'{LABEL}: 이 폴더는 다른 판에서 시작했습니다.')
    ledger.setdefault('fixAttempts', {})
    if fill is not None:
        v3.require(ledger['presupposeOnly'].setdefault('fill', fill) == fill, f'{LABEL}: 이 폴더는 다른 채우기 기록으로 시작했습니다.')
        st.save()

    placement = 'review-coverage'
    bank = v2.restore_container_concepts(v2.restore_importance(old['document']['bank_snapshot'], meta.get('importanceProjection')),
                                         meta.get('bankProjection'))
    published = [q['question_id'] for q in bank['questions']]
    # notes-update/1 (docs/changes/2026-11-16-replace-updated-notes): the published revision may have taken corrected
    # notes of the same pages. Its brief, judgments and figures stay those of the earlier file, and its document names
    # the corrected one. This run continues both: published figures are kept as published (rendering them again would
    # crop the corrected file, change the question and end its learning history), and the document gets the same
    # update, which the consumer applies from the record this manifest inherits.
    update = (meta.get('unplacedOnly') or {}).get('sourceUpdate')
    replaced = {r['source_id'] for r in update['sources']} if update else set()
    as_published = {q['question_id']: q for q in bank['questions']}

    def render(value, specs):
        if not replaced:
            return visual.render(value, specs, packet, out / 'material')
        return _render_keeping(value, specs, packet, out / 'material', as_published, replaced)
    rows = {r['direction_id']: copy.deepcopy(r) for r in meta['coverage']}
    map_checks = [meta['mapCheck']]
    reviews = {r['question_id']: r for r in meta['itemReviews']}
    basis = copy.deepcopy(meta['questionImportance'])
    conflicts = copy.deepcopy(meta['clinicalConflicts'])
    stimuli = copy.deepcopy(meta['visualStimuli'])
    fixes = copy.deepcopy(meta['fixes'])
    profile = v4.notebook_profile(packet, meta)
    context = v3.context_summary(meta['clinicalContext'])
    page_counts = {s['source_id']: s['page_count'] for s in brief['sources']}
    points_doc = meta.get('supplementPoints') or v4.check_points(json.loads(packet['points']))
    evidence = meta.get('reviewEvidence')
    evidence_notes = {'source_id': evidence['sourceId'], 'page_count': page_counts[evidence['sourceId']]} if evidence else None

    def judge(name, ctx):
        return st.judged(name, ctx, lambda raw, ctx=ctx: v4.check_coverage(raw, ctx['goals'], ctx['questions']))

    # 1: what each published stem gives as known, and which elements a cue alone has to pick out ----------------
    # Both judgments read the published bank only, so they run side by side (discriminate/1 adds its stage here;
    # one backfill request now makes existence goals and reverse goals, 사용자 2026-11-16 「역방향 넣고 한 번에」).
    # Fill mode keeps the published judgments and goals: nothing here runs.
    calls = [] if fill is not None else [(f'{X}presuppose-{k}', ctx, lambda raw, ctx=ctx: pre.check(raw, ctx))
             for k, ctx in enumerate(pre.stage_input(bank, part, page_counts) for part in chunks(published, pre.CHUNK))]
    pre_calls = len(calls)
    rdids = dis.goals(brief)
    calls += [(f'{X}discriminate-{k}', ctx, lambda raw, ctx=ctx: dis.check(raw, ctx))
              for k, ctx in enumerate(dis.stage_input(brief, bank, part, page_counts) for part in chunks(rdids, dis.CHUNK))
              if rdids and fill is None]   # a map with no goals asks nothing (chunks([]) is one empty part)
    if fill is not None:
        calls = []
        presuppositions, discriminations = meta.get('presuppositions'), meta.get('discriminations')
        made, made_reverse = [], []
        print(f"── {LABEL} 채우기: 목표 {len(fill['goals'])}개 · 다시 쓸 문항 {len(fill['rewrite'])}개 (판정은 공개판 그대로)", flush=True)
    else:
        judged = batches.judgments(st, calls)
        points_doc, presuppositions, made = pre.records(judged[:pre_calls], bank, points_doc,
                                                        [p['point_id'] for p in brief['points']])
        print(f"── {LABEL}: 발문이 전제로 준 연결 {len(presuppositions)}개 · 답으로 묻는 문항 없음 {len(made)}개 → 존재 목표", flush=True)
        points_doc, discriminations, made_reverse = dis.records(judged[pre_calls:], bank, points_doc, brief,
                                                                [p['point_id'] for p in brief['points']])
        print(f"── {LABEL}: 거꾸로 물을 목표 {len(discriminations)}개 · 그렇게 묻는 문항 없음 {len(made_reverse)}개 → 역방향 목표", flush=True)

    # 2: existence goals ------------------------------------------------------
    new_dids = []
    if made:
        allowed = pre.new_goal_ids(brief, made)
        ctx = pre.normalize_input(brief, made, allowed)
        state = {'brief': brief, 'blank': True}
        addition = st.run(X + 'supplement-normalize' + TAG, ctx, lambda raw: check_stage('presuppose-normalize', raw, ctx, state, None), state)
        brief, new_tids = pre.extend(brief, addition, [p['point_id'] for p in made])
        new_dids = [d['direction_id'] for t in brief['targets'] if t['target_id'] in new_tids for d in t['directions']]
        # Coverage and map check both read only the extended map: side by side (2026-11-16, about 2 minutes a lecture).
        cov = v3.coverage_input(brief, bank, new_dids, sorted({p['origin_question_id'] for p in made}))
        chk = v4.map_check_input(brief, new_tids)
        got, checked = batches.judgments(st, [
            (X + 'coverage' + TAG, cov, lambda raw, ctx=cov: v4.check_coverage(raw, ctx['goals'], ctx['questions'])),
            (X + 'map-check' + TAG, chk, lambda raw, ctx=chk: v3.check_map_input(raw, ctx))])
        rows.update({r['direction_id']: r for r in got['rows']})
        map_checks.append(checked)
        st.save()

    # 2d: reverse goals (discriminate/1) --------------------------------------
    rev_dids = []
    # After the existence goals: both take their IDs from the brief as it stands, so this order fixes which goal gets
    # which TQ/DQ number.
    if made_reverse:
        allowed = v3.supplement_ids(brief, len(made_reverse))
        ctx = dis.normalize_input(brief, made_reverse, allowed)
        state = {'brief': brief, 'blank': True}
        addition = st.run(X + 'supplement-normalize' + RTAG, ctx,
                          lambda raw: check_stage('discriminate-normalize', raw, ctx, state, None), state)
        brief, new_tids = dis.extend(brief, addition, [p['point_id'] for p in made_reverse])
        rev_dids = [d['direction_id'] for t in brief['targets'] if t['target_id'] in new_tids for d in t['directions']]
        rows.update(dis.blank_rows(rev_dids))   # judged after the add round, not before (spec R4)
        chk = v4.map_check_input(brief, new_tids)
        map_checks.append(st.judged(X + 'map-check' + RTAG, chk, lambda raw, ctx=chk: v3.check_map_input(raw, ctx)))
        st.save()

    # 3: their questions (add rounds on the new goals only) ---------------------
    added = []
    for n in range(ADD_ROUNDS):
        goals = _goals(brief)
        if fill is not None:
            # Only the goals the operator listed. Not `exclude=published`: here the published questions are the ones
            # written for the existence and reverse goals, and those goals are not written again.
            gaps = fill_gaps(fill['goals'], rows, brief, presuppositions, discriminations, bank)
        else:
            gaps = {did: v4.missing_components(rows[did], goals[did]) for did in new_dids if rows[did]['status'] != 'covered'}
            gaps.update(pre.existence_gaps(rows, brief, presuppositions))   # asked whole, in one question
            for did in pre.written_for(bank, brief, presuppositions, exclude=published):   # one question per goal
                gaps.pop(did, None)
            gaps.update(dis.gaps(brief, discriminations, bank, exclude=published))              # reverse goals: not a coverage verdict
        if not gaps:
            break
        allowed = v3.next_question_ids(bank, ADD_PER_GOAL * len(gaps))
        ctx = pre.mark_existence(v4.add_input(brief, bank, gaps, allowed, rows), brief, presuppositions, bank)
        dis.mark_add(ctx, brief, discriminations, bank)
        state = _state(bank, conflicts, stimuli, packet)
        name = f'{X}add{TAG}-{n}'

        def accept(raw, ctx=ctx, state=state, name=name):
            value = check_stage('add', raw, ctx, state, out / '.check-render' / name)
            if not v4.empty_added(value):
                _no_new_conflicts(state['clinical_conflicts'], v3.merge_added(state['bank'], state['clinical_conflicts'],
                                                                             v4.without_basis(value), ctx['allowed_question_ids'])[1])
            return value
        value = st.run(name, ctx, accept, state)
        if v4.empty_added(value):
            break
        plain = v4.without_basis(value)
        bank, conflicts = v3.merge_added(visual.authored(bank), conflicts, plain, allowed)
        basis.update(v4.collect_basis(value['question_importance'], [q['question_id'] for q in value['questions']]))
        stimuli = [*stimuli, *value['visual_stimuli']]
        bank = render(bank, stimuli)
        new = [q['question_id'] for q in value['questions']]
        added += new
        for part in chunks(list(gaps), COVERAGE_CHUNK):
            wanted = set(new) | {e['question_id'] for did in part for e in rows[did]['evidence']}
            got = judge(f'{X}coverage{TAG}-{n + 1}-{part[0]}', v3.coverage_input(brief, bank, part,
                                                                                [q['question_id'] for q in bank['questions'] if q['question_id'] in wanted]))
            for r in got['rows']:
                prior = rows[r['direction_id']]
                rows[r['direction_id']] = _merge_row(prior, _first_evidence(prior, r), goals[r['direction_id']], by_evidence=True)
        st.save()

    # 4: item review and fixes of the new questions ------------------------------
    def review(name, qids):
        ctx = v4.with_importance(v3.review_input(bank, qids, conflicts), basis)
        if evidence_notes:
            ctx['evidence_source'] = evidence_notes
        ctx['map_relations'] = v4.map_relations(brief, map_checks)
        # existence questions are judged as such (2026-11-16); published questions are not written for them (2026-11-17)
        pre.mark_review(ctx, brief, presuppositions, bank, exclude=published)
        dis.mark_review(ctx, brief, discriminations, bank, exclude=published)   # ... and reverse ones too
        value = st.judged(name, ctx, lambda raw: v4.check_review_input(raw, ctx))
        by_id = {q['question_id']: q for q in bank['questions']}
        for r in value['reviews']:
            entry = v3.ledger_entry('item', r['question_id'], v3.item_hash(by_id[r['question_id']], bank, conflicts), r, name)
            if entry not in ledger['verdictLedger']:
                ledger['verdictLedger'].append(entry)
        st.save()
        return {r['question_id']: r for r in value['reviews']}

    # Fill mode: a published question the operator found wrong is given to the first fix round with that finding
    # (the model writes it again, as it fixes a reviewed question). Its fix budget is the published run's.
    operator = {r['question_id']: {**reviews[r['question_id']], 'design': 'wrong', 'note': r['note'], 'fix': r['fix']}
                for r in (fill or {}).get('rewrite', [])}
    for q in operator:
        v3.require(ledger['fixAttempts'].get(q, 0) < v3.FIX_LIMIT, f'{LABEL}: {q}는 고치기 상한을 이미 다 썼습니다.')
    rewritten = []
    if added or operator:
        if added:
            reviews.update(review(f'{X}review{TAG}-0', added))
        attempts = {q: ledger['fixAttempts'].get(q, 0) for q in operator}
        source_ids = [s['id'] for s in packet['sources']]
        for k in range(v3.FIX_LIMIT):
            code = _bank_findings(bank, source_ids, attempts)
            pending = list(operator) if k == 0 else []
            targets = [q for q in [*added, *rewritten]
                       if (v3.needs_fix(reviews[q]) or q in code) and attempts.get(q, 0) < v3.FIX_LIMIT] + pending
            if not targets:
                break
            for q in targets:
                attempts[q] = attempts.get(q, 0) + 1
                ledger['fixAttempts'][q] = max(ledger['fixAttempts'].get(q, 0), attempts[q])
            covered = {}
            for did, r in rows.items():
                for q in v4.covering(r):
                    covered.setdefault(q, []).append(did)
            shown = {q: operator[q] if q in pending else reviews[q] for q in targets}   # what the fix is judged against
            findings = [{**shown[q], 'code_findings': code.get(q, [])} for q in targets]
            ctx = pre.mark_review(v4.with_importance(v3.fix_input(bank, findings, targets, conflicts, covered), basis),
                                  brief, presuppositions, bank, exclude=published)
            dis.mark_review(ctx, brief, discriminations, bank, exclude=published)
            state = _state(bank, conflicts, stimuli, packet)
            name = f'{X}fix{TAG}-{k}'

            def accept(raw, ctx=ctx, state=state, name=name):
                value = check_stage('fix', raw, ctx, state, out / '.check-render' / name)
                _no_new_conflicts(state['clinical_conflicts'], v3.merge_fixes(state['bank'], state['clinical_conflicts'],
                                                                             v4.without_basis(value), ctx_targets(ctx))[1])
                return value
            value = st.run(name, ctx, accept, state)
            plain = v4.without_basis(value)
            before = (copy.deepcopy(bank), copy.deepcopy(stimuli), copy.deepcopy(basis))
            conflicts_before = copy.deepcopy(conflicts)
            before_reviews = {q: reviews[q] for q in targets}
            merged, conflicts, changed = v3.merge_fixes(visual.authored(bank), conflicts, plain, targets)
            fixed_basis = v4.collect_basis(value['question_importance'], [q['question_id'] for q in value['questions']])
            basis.update({q: fixed_basis[q] for q in changed})
            stimuli = [s for s in stimuli if s['question_id'] not in set(changed)] + value['visual_stimuli']
            bank = render(merged, stimuli)
            again = review(f'{X}review{TAG}-{k + 1}', changed) if changed else {}
            # An operator's rewrite is also undone when its re-review is worse than the published question's review, in
            # the answer or in the design. Judged only against the operator's finding (design: wrong), any rewrite
            # looks better, and a rewrite left with a design doubt and no fix budget is no task: the published task
            # went missing and the whole lecture was refused (2026-11-25 job 746 / 261123_06, Q072·Q100).
            reverted = [q for q in changed if q in again and (
                v3.worse(shown[q], again[q]) or q in pending and v3.worse(before_reviews[q], again[q]))]
            if reverted and not [q for q in changed if q not in reverted]:
                # Every fix of the round was worse: the round is undone as a whole, as the first run does
                # (connection_generate_v4). Merging the empty rest again is not a fix output — 2026-11-17 job 670 /
                # 261112_03 stopped there with 「v3 fix output.questions: too few entries」.
                bank, stimuli, basis = before
                conflicts = conflicts_before
            elif reverted:
                # A fix that made its question worse is undone.
                kept = [q for q in changed if q not in reverted]
                part = v3.fixes_of(plain, kept)
                merged, conflicts, _ = v3.merge_fixes(visual.authored(before[0]), conflicts, part, targets)
                stimuli = [s for s in before[1] if s['question_id'] not in set(kept)] + part['visual_stimuli']
                bank = render(merged, stimuli)
                basis = {**before[2], **{q: fixed_basis[q] for q in kept}}
            for q in changed:
                reviews[q] = before_reviews[q] if q in reverted else again.get(q, reviews[q])
                fixes.append({'question_id': q, 'attempt': attempts[q], 'stage': name, 'reverted': q in reverted})
            kept = [q for q in changed if q not in reverted]
            rewritten += [q for q in kept if q in operator and q not in rewritten]
            goal_ids = sorted({did for q in kept for did, r in rows.items() if any(e['question_id'] == q for e in r['evidence'])})
            if goal_ids:
                got = judge(f'{X}coverage-fix{TAG}-{k}', v3.coverage_input(brief, bank, goal_ids, kept))
                for r in got['rows']:
                    rows[r['direction_id']] = _merge_row(rows[r['direction_id']], r, _goals(brief)[r['direction_id']], kept, by_evidence=True)
            st.save()

    # notes citations of the new questions follow their review evidence (review-evidence/1) ------------------
    alignments = copy.deepcopy(meta.get('citationAlignments') or []) if evidence else None
    fresh = [*added, *rewritten]   # the questions this run wrote: reviewed, cited and medically reviewed as its own
    if evidence and fresh:
        new_reviews = {q: reviews[q] for q in fresh}
        bank, more = v4.align_citations(bank, new_reviews, evidence['sourceId'])
        alignments += more

    # assembly -----------------------------------------------------------------
    coverage_rows = [rows[d['direction_id']] for t in brief['targets'] for d in t['directions']]
    review_rows = [reviews[q['question_id']] for q in bank['questions']]
    map_check = {k: [x for m in map_checks for x in m[k]] for k in ('relation_checks', 'target_checks', 'direction_checks', 'issues')}
    seen = {}
    for r in map_check['relation_checks']:
        seen.setdefault(r['relation_id'], r)
    map_check['relation_checks'] = list(seen.values())
    raw = v4.assessment_raw(brief, bank, coverage_rows, map_check, review_rows, context, meta['sourceAssessment']['summary'], placement)
    audit = v4.compile_assessment(brief, bank, v2.envelope(brief, bank, raw), placement)
    basis = {q['question_id']: basis[q['question_id']] for q in bank['questions']}
    # Where the published revision placed its tasks. The assembly keeps each of them there and merges none of them
    # away (v4.keep_published, merged_duplicates `held`); the record carries the same map, so the consumer assembles
    # the same document. PR #206 made the pin and its consumer side, and this call never passed the map: the pin did
    # nothing until 2026-11-17 (docs/changes/2026-11-17-backfill-pin-callers).
    settled_places = {t['question_id']: t['direction_id'] for t in old['document']['tasks']}
    doc, placed, proofs = v4.assemble(brief, bank, audit, coverage_rows, basis, profile, revision=packet['revision'],
                                      title=packet['title'], exam_date=packet['examDate'], placement=placement,
                                      presuppositions=presuppositions, discriminations=discriminations,
                                      settled=published, settled_places=settled_places)
    kept_tasks = {t['question_id'] for t in old['document']['tasks']}
    # Strict: a published task never becomes a duplicate of an added question (its history would stop).
    v3.require(kept_tasks <= {t['question_id'] for t in doc['tasks']}, f'{LABEL}: 이전 판의 과제가 빠졌습니다.')
    doc['equivalences'], carry = v4.carry_links(doc, packet['carrySources'])
    previous_carry = next((r for r in carry if r['revision'] == old['document']['revision']), None)
    staying = {t['question_id'] for t in doc['tasks']}
    carried = sum(t['question_id'] in staying for t in old['document']['tasks'])
    if rewritten:
        # A question the operator had rewritten is another question now: its history starts over, and only its.
        # Every other published task must still be the same question on the same goal.
        from studyez_contracts.roots.validate import task_fingerprints
        now, before = task_fingerprints(doc), task_fingerprints(old['document'])
        mine = {(t['direction_id'], now[t['task_id']]) for t in doc['tasks']}
        broken = [t['question_id'] for t in old['document']['tasks']
                  if t['question_id'] not in set(rewritten) and (t['direction_id'], before[t['task_id']]) not in mine]
        v3.require(not broken, f"{LABEL}: 다시 쓰지 않은 문항의 학습 기록이 끊깁니다: {', '.join(broken)}")
        carried = sum((t['direction_id'], before[t['task_id']]) in mine for t in old['document']['tasks'])
    v3.require(previous_carry and previous_carry['tasks'] == carried,
               f'{LABEL}: 이전 판의 과제 중 같은 문항으로 이을 수 없는 것이 있습니다 — 학습 기록이 끊깁니다.')
    if update:
        doc = v4.apply_source_update(doc, brief, packet, update)   # after the carry links, as the consumer does
    counts = pre.report(presuppositions, doc)
    rcounts = dis.report(discriminations, doc, bank)
    ready_rows = v4.readiness(brief, coverage_rows, doc)
    g.write(out / 'readiness.json', {'rows': ready_rows, **placed, 'importanceWarnings': proofs['importanceWarnings']})

    # medical: the new questions only; the published review stands for the rest --------------------------
    sent_all = v3.context_sent(conflicts, meta['clinicalContext'])
    sub = {**bank, 'questions': [q for q in bank['questions'] if q['question_id'] in set(fresh)]}
    added_medical, unreviewed = None, [r for r in meta['medicalUnreviewed'] if r['question_id'] not in set(rewritten)]
    if fresh:
        clinical_input, _ = v3.medical_parts(sub, sent_all)
        st.invoke = _medical_batches(st.invoke, workers=batches.BATCH_WORKERS if st.parallel else 1)
        added_medical = st.run(MEDICAL, {'title': packet['title'], 'bank': sub, 'clinicalInput': clinical_input, 'medicalFinal': True},
                               lambda raw: validate_checks(raw, sub))
        unreviewed += [{'question_id': r['question_id'], 'reason': r['note'][len(v3.UNREVIEWED_NOTE):]}
                       for r in added_medical['reviews'] if r['note'].startswith(v3.UNREVIEWED_NOTE)]
    medical = _merge_medical(old['medical'], added_medical, bank, rewritten)
    st.save()

    record = {**ledger['presupposeOnly'], 'tasksBefore': len(old['document']['tasks']), 'tasksAfter': len(doc['tasks']),
              'addedQuestions': added, 'settledPlaces': settled_places, 'previousMedical': old['medical'], 'addedMedical': added_medical,
              'existenceGoals': new_dids, 'reverseGoals': rev_dids, 'carry': carry, 'counts': {k: (len(v) if k == 'open' else v) for k, v in counts.items()},
              **({'rewrittenQuestions': rewritten} if rewritten else {}),
              'reverseCounts': {k: (len(v) if k in ('open', 'answerInStem') else v) for k, v in rcounts.items()}}
    print(f"── {LABEL} 조립: 과제 {record['tasksBefore']} → {record['tasksAfter']} · 새 문항 {len(added)}개 · 존재 목표 {len(new_dids)}개 · "
          f"선행 연결 {counts['prerequisites']}개 · 남은 전제 {len(counts['open'])}개", flush=True)
    print(f"── {LABEL} 역방향: 거꾸로 물 목표 {rcounts['reversible']}개 중 이미 그렇게 묻던 것 {rcounts['alreadyAsked']} · "
          f"역방향 목표 {rcounts['goalsMade']}개 중 문항 생김 {rcounts['goalsWithTask']} · 남은 연결 {len(rcounts['open'])} · "
          f"발문이 답을 흘린 문항 {len(rcounts['answerInStem'])}개", flush=True)

    manifest = copy.deepcopy(meta)
    manifest.pop('coverageFallback', None)
    snapshot = doc['bank_snapshot']
    supplement = meta.get('supplement') or []
    manifest.update(inputHash=packet['inputHash'], runtimeHash=ledger['identity'], briefHash=document_hash(brief),
                    bankHash=document_hash(snapshot), stages=[{'name': k, **v} for k, v in ledger['stages'].items()],
                    verdictLedger=ledger['verdictLedger'], verdictLedgerHash=document_hash(ledger['verdictLedger']),
                    notReady=v4.not_ready(brief, coverage_rows, review_rows), coverage=coverage_rows, mapCheck=map_check,
                    sourceAssessment=raw, readiness=ready_rows, itemReviews=review_rows, fixes=fixes,
                    questionImportance=basis, importanceNotes=v4.importance_notes(review_rows), visualStimuli=stimuli,
                    medicalUnreviewed=unreviewed, importanceWarnings=proofs['importanceWarnings'],
                    importanceProjection=proofs['importanceProjection'],
                    supplementPoints=meta.get('supplementPoints') if fill is not None
                    else points_doc if supplement or made or made_reverse else None,
                    placement={'policy': v4.REVIEW_PLACEMENT2},
                    presuppositions=presuppositions, discriminations=discriminations, presupposeOnly=record, **placed)
    if evidence:
        manifest['citationAlignments'] = alignments
    if ledger.get('stageResumes'):
        manifest['stageResumes'] = ledger['stageResumes']
    if proofs['bankProjection']:
        manifest['bankProjection'] = proofs['bankProjection']
    else:
        manifest.pop('bankProjection', None)
    if 'derivedFrom' in packet:
        manifest.update(derivedPacket=map_tree.public(packet), auditOpen=packet['frontStages']['openPoints'])
    source_ids = [s['id'] for s in packet['sources']]
    result = {'brief': brief, 'document': doc, 'sourceAudit': audit, 'medical': medical,
              'validation': validate_bank(snapshot, source_ids), 'manifest': manifest}
    v4.validate_result(result, packet)
    g.write(out / 'result.json', result)
    return result


def _render_keeping(bank, specs, packet, material, as_published, replaced):
    """`visual.render` for a published revision whose notes were replaced (notes-update/1). A published question with
    a figure on a replaced source keeps the figures it was published with: they were cropped from the earlier file,
    which the brief still names. A new question cannot have such a figure yet — the earlier file is not in the packet.
    2026-11-17 job 670 / 261112_03: every merge rendered the five published figures again from the corrected notes,
    and the assembly stopped with 「stimuli: source/page mismatch」."""
    held = {s['question_id'] for s in specs if s['source_id'] in replaced}
    new = sorted(held - set(as_published))
    v3.require(not new, f"{LABEL}: 필기를 교체한 판입니다 — 새 문항({', '.join(new)})의 그림은 교체 전 필기에서 자를 수 없어 "
               '아직 받지 않습니다.')
    value = visual.render(bank, [s for s in specs if s['question_id'] not in held], packet, material)
    for q in value['questions']:
        if q['question_id'] in held:
            q['stimuli'] = copy.deepcopy(as_published[q['question_id']]['stimuli'])
    return value


def _merge_medical(prev, more, bank, rewritten=()):
    """The published medical review with the review of the added questions, in bank order (counts recomputed).
    `rewritten`: published questions this run wrote again — their published verdict is replaced by the new one."""
    if more is None:
        return prev
    from .review import shape
    order = {q['question_id']: i for i, q in enumerate(bank['questions'])}
    rows = sorted([*(r for r in prev['reviews'] if r['question_id'] not in set(rewritten)), *more['reviews']],
                  key=lambda r: order[r['question_id']])
    return shape({'summary': prev['summary'] + ' / ' + more['summary'], 'reviews': rows,
                  'pool_checks': [*prev.get('pool_checks', []), *more.get('pool_checks', [])]}, bank)


def ctx_targets(ctx):
    return [q['question_id'] for q in ctx['questions']]

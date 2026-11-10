"""root-generation/3: add-only coverage, one job per judgment, minimal stage inputs.

docs/changes/2026-11-10-root-generation-3 (spec.md, plan.md). The /2 producer (connection_generate_v2) is
not changed; this module reuses its normalize/context/medical stages and its document assembly.

Order: intake bank → normalize (+ brief-fix) → coverage → map check → off-goal points → add ≤2
→ item review/fix by batch → context → medical (once) → assembly.

Every model call goes through `invoke(stage, ctx, material, model)` (runner.root_native_json.NativeJson).
Inputs, raw outputs and usage are written next to the ledger; nothing is retried automatically. A failed or
interrupted stage continues only with an operator reason (`resume`); completed stages are kept, and the
add rounds and fix attempts recorded in the ledger are never reset.
"""
import copy
import hashlib
import json
import re
import shutil
from pathlib import Path

import jsonschema
from studyez_llm import codex
from studyez_contracts.roots import document_hash
from studyez_contracts.roots import generation_v2 as v2
from studyez_contracts.roots import generation_v3 as v3
from studyez_contracts.roots import map_tree
from studyez_contracts.roots.automation import validate_checks
from studyez_contracts.roots.source_assessment import envelope
from studyez_contracts.bank.validate import validate_bank
from . import connection_visuals as visual

POLICY = v3.POLICY
COVERAGE_CHUNK = 60      # goals per coverage call (plan U2)
REVIEW_BATCH = 40        # questions per item review (plan U2)
ADD_PER_GOAL = 2         # new IDs offered per gap goal
_QID = re.compile(r'^(Q[0-9A-Za-z_-]+)\b')


def _prompt_hash():
    folder = Path(__file__).resolve().parents[1] / 'content/prompts/learning-links/v3'
    return document_hash({p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(folder.glob('*.md'))})


def chunks(items, size):
    return [items[i:i + size] for i in range(0, len(items), size)] or [[]]


class Stages:
    """Ledger of stage calls with archived evidence. Same rules as the /2 producer: no automatic rerun."""

    def __init__(self, packet, out, model, invoke, resume=None):
        from . import connection_generate as g
        self.g, self.out, self.model, self.invoke = g, Path(out), model, invoke
        self.path = self.out / 'ledger.json'
        identity = document_hash({'base': g.identity(packet, model), 'v3': POLICY, 'prompts': _prompt_hash()})
        if self.path.exists():
            self.ledger = json.loads(self.path.read_text(encoding='utf-8'))
            v3.require(self.ledger.get('pipelineVersion') == POLICY, '기존 실행의 파이프라인 판이 다릅니다. 이력과 상한을 보존합니다.')
            v3.require(self.ledger.get('inputHash') == packet['inputHash'], '다른 packet으로는 이어 가지 않습니다.')
            if self.ledger.get('identity') != identity or any(s['status'] != 'completed' for s in self.ledger['stages'].values()):
                v3.require(type(resume) is str and resume.strip(),
                           '이전 실행이 실패·중단됐거나 코드가 달라졌습니다. 이력과 상한을 보존합니다. 이어 가려면 --resume <이유>.')
            self.resume_row = None
            if resume:
                self.resume_row = {'reason': resume, 'identityBefore': self.ledger.get('identity'), 'identity': identity, 'superseded': []}
                self.ledger.setdefault('stageResumes', []).append(self.resume_row)
                self.ledger['identity'] = identity
        else:
            v3.require(not any(p.name != 'packet.json' for p in self.out.glob('*.json')), '기존 산출물의 ledger가 없습니다. 자동 재시작하지 않습니다.')
            self.out.mkdir(parents=True, exist_ok=True)
            self.ledger = {'pipelineVersion': POLICY, 'inputHash': packet['inputHash'], 'identity': identity, 'stages': {},
                           'addRounds': 0, 'fixAttempts': {}, 'verdictLedger': []}
            self.resume_row = None
        self.save()

    def save(self):
        self.g.write(self.path, self.ledger)

    def _archive(self, name):
        rows = self.ledger.setdefault('stageResumes', [])
        archive = self.out / f'.resume-{len(rows)}'
        archive.mkdir(exist_ok=True)
        for suffix in ('.input.json', '.raw.json', '.usage.json', '.json'):
            path = self.out / (name + suffix)
            if path.exists():
                path.replace(archive / path.name)
        seat = self.out / '.native' / name
        if seat.exists():
            (archive / '.native').mkdir(exist_ok=True)
            seat.replace(archive / '.native' / name)
        self.resume_row['superseded'].append({'name': name, 'entry': self.ledger['stages'].pop(name)})

    def run(self, name, ctx, accept):
        """One model stage. A completed stage with the same input is reused; anything else runs once."""
        ctx = {**ctx, '_pipeline_version': POLICY}
        input_hash = document_hash(ctx)
        prior = self.ledger['stages'].get(name)
        if prior and prior['status'] == 'completed' and prior['inputHash'] == input_hash:
            return json.loads((self.out / (name + '.json')).read_text(encoding='utf-8'))
        if prior:
            v3.require(self.resume_row is not None, name + ': 중단/실패/달라진 호출은 자동 재실행하지 않습니다.')
            self._archive(name)
        entry = {'status': 'started', 'inputHash': input_hash}
        self.ledger['stages'][name] = entry
        self.save()
        self.g.write(self.out / (name + '.input.json'), ctx)
        print('── 연결 자동출제 /3 ' + name, flush=True)
        try:
            raw, info = self.invoke(name, ctx, self.out / 'material', self.model)
            self.g.write(self.out / (name + '.raw.json'), raw)
            self.g.write(self.out / (name + '.usage.json'), info)
            entry.update(rawOutputHash=document_hash(raw), usageHash=document_hash(info))
            value = accept(raw)
            self.g.write(self.out / (name + '.json'), value)
            entry.update(status='completed', outputHash=document_hash(value))
            self.save()
            return value
        except BaseException:
            entry['status'] = 'failed'
            self.save()
            raise


# ---------------------------------------------------------------- helpers
def _merge_row(old, new, replaced=()):
    """Coverage of one goal after a narrower judgment: evidence of replaced/new questions comes from `new`."""
    if old is None:
        return new
    keep = [e for e in old['evidence'] if e['question_id'] not in set(replaced) | {x['question_id'] for x in new['evidence']}]
    evidence = keep + copy.deepcopy(new['evidence'])
    probe = {**new, 'status': 'covered', 'evidence': keep}
    kept_cover = old['status'] == 'covered' and bool(v3.covering(probe))
    status = 'covered' if new['status'] == 'covered' or kept_cover else new['status']
    return {'direction_id': new['direction_id'], 'status': status, 'evidence': evidence,
            'reason': new['reason'] if new['status'] == 'covered' or not kept_cover else old['reason']}


def _bank_findings(bank, sources):
    """Code checks per question (format errors and quality measures); never a model call."""
    found = {}
    for text in validate_bank(bank, sources)['errors'] + [r['text'] for r in v2.quality_reasons(bank)]:
        m = _QID.match(text.replace('문항 품질: ', ''))
        if m:
            found.setdefault(m.group(1), []).append(text)
    return found


def _intake(packet, out):
    """The independently authored bank (1c or a web response). Questions with format errors are left out."""
    intake = copy.deepcopy(packet['intakeBank'])
    bank, projection = v3.intake_projection(intake['bank'])
    sources = [s['id'] for s in packet['sources']]
    report = validate_bank(bank, sources)
    rejected = []
    for text in report['errors']:
        m = _QID.match(text)
        v3.require(m, '문제은행 형식 오류가 특정 문항에 속하지 않습니다. 결과를 만들지 않고 보존합니다: ' + text)
        rejected.append({'question_id': m.group(1), 'error': text})
    bad = {r['question_id'] for r in rejected}
    if bad:
        bank['questions'] = [q for q in bank['questions'] if q['question_id'] not in bad]
        for q in bank['questions']:
            q['prerequisites'] = [p for p in q.get('prerequisites', []) if p not in bad]
        intake['visual_stimuli'] = [s for s in intake['visual_stimuli'] if s['question_id'] not in bad]
    rendered = visual.render(bank, intake['visual_stimuli'], packet, out / 'material')
    return rendered, intake['visual_stimuli'], intake['clinical_conflicts'], rejected, projection


def _join_points(bank, brief, rows):
    """Code join: a question implements the points of the goals it was judged against (spec R0)."""
    owner = {d['direction_id']: t['target_id'] for t in brief['targets'] for d in t['directions']}
    points_of = {}
    for p in brief['points']:
        for tid in p['target_ids']:
            points_of.setdefault(tid, []).append(p['point_id'])
    found = {}
    for did, row in rows.items():
        for e in row['evidence']:
            found.setdefault(e['question_id'], set()).update(points_of.get(owner[did], []))
    value = copy.deepcopy(bank)
    for q in value['questions']:
        if q['question_id'] in found:
            q['point_ids'] = sorted(found[q['question_id']])
    return value


# ---------------------------------------------------------------- run
def run(packet, out, model, invoke, resume=None):
    from . import connection_generate as g
    out = Path(out)
    v3.require(packet.get('generationPolicy') == POLICY, 'root-generation/3 packet required')
    st = Stages(packet, out, model, invoke, resume)
    ledger = st.ledger
    sources = g.prepare(packet, out / 'material')
    page_counts = {s['source_id']: s['page_count'] for s in sources}
    base = {k: packet[k] for k in ('title', 'scope', 'conceptMap', 'points', 'examDate')}
    base.update(lecture_id=packet['subject'] + '/' + packet['runId'], sources=sources,
                preserved_scope=g.lecture_scope(packet['title'], packet['sources']))
    table = v2.importance_table(packet)
    points_doc = json.loads(packet['points']) if table is not None else None

    # 1c: intake bank -------------------------------------------------------
    bank, stimuli, conflicts, rejected, intake_changes = _intake(packet, out)
    initial_bank = copy.deepcopy(bank)

    # normalize (+ one structural correction) -------------------------------
    def accept_brief(raw):
        v2.validate_shape(raw, v2.BRIEF, 'initial brief2')
        value = v2.blank_target_importance(raw) if table is not None else raw
        if value['scope']['label'] != packet['title']:
            value = {**value, 'scope': {**value['scope'], 'label': packet['title']}}
        v3.require(raw['sources'] == sources and raw['lecture_id'] == base['lecture_id'], 'Different initial source/lecture')
        return value
    brief = st.run('normalize', base, accept_brief)
    initial_brief = brief
    findings = v2.brief_findings(brief)
    if findings:
        fixed = st.run('v3-brief-fix', {'brief': brief, 'errors': findings, 'pages': []},
                       lambda raw: v3.check_brief_fix(raw, {'brief': brief}))
        brief = v2.blank_target_importance(fixed['brief']) if table is not None else fixed['brief']

    # 2: coverage -----------------------------------------------------------
    rows = {}
    dids = [d['direction_id'] for t in brief['targets'] for d in t['directions']]
    for k, part in enumerate(chunks(dids, COVERAGE_CHUNK)):
        ctx = v3.coverage_input(brief, bank, part)
        value = st.run(f'v3-coverage-0-{k}', ctx, lambda raw, ctx=ctx: v3.check_coverage(raw, ctx['goals'], ctx['questions']))
        rows.update({r['direction_id']: r for r in value['rows']})

    # 2m: map check ---------------------------------------------------------
    ctx = v3.map_check_input(brief, table)
    map_checks = [st.run('v3-map-check-0', ctx, lambda raw: v3.check_map_input(raw, ctx))]

    # 2a: off-goal questions → supplement points ----------------------------
    judged = {e['question_id'] for r in rows.values() for e in r['evidence']}
    off_goal = [q['question_id'] for q in bank['questions'] if q['question_id'] not in judged]
    supplement, out_of_scope = [], []
    if off_goal:
        v3.require(points_doc is not None, '목표 밖 문항의 포인트 보충에는 exam-point-extract/3 포인트가 필요합니다.')
        ctx = v3.supplement_input(bank, off_goal, points_doc, page_counts)
        value = st.run('v3-supplement', ctx, lambda raw: v3.check_supplement(raw, ctx))
        points_doc, table, supplement = v3.attach_points(points_doc, value, off_goal, page_counts)
        new_points = [p for p in points_doc['points'] if p['point_id'] in {d['point_id'] for d in supplement if d['decision'] == 'point'}]
        dup = [d for d in supplement if d['decision'] == 'duplicate_of']
        out_of_scope = [d for d in supplement if d['decision'] == 'out_of_scope']
        if new_points:
            allowed = v3.supplement_ids(brief, len(new_points))
            ctx = v3.supplement_normalize_input(brief, new_points, allowed)
            addition = st.run('v3-supplement-normalize', ctx, lambda raw: v3.check_supplement_normalize(raw, ctx))
            added_targets = v2.blank_target_importance({**brief, 'targets': addition['targets']})['targets'] if table is not None else addition['targets']
            brief, new_tids = v3.extend_brief(brief, {'targets': added_targets, 'points': addition['points']}, [p['point_id'] for p in new_points])
            new_dids = [d['direction_id'] for t in brief['targets'] if t['target_id'] in new_tids for d in t['directions']]
            origins = [p['origin_question_id'] for p in new_points]
            ctx = v3.coverage_input(brief, bank, new_dids, origins)
            value = st.run('v3-coverage-supplement', ctx, lambda raw: v3.check_coverage(raw, ctx['goals'], ctx['questions']))
            rows.update({r['direction_id']: r for r in value['rows']})
            ctx = v3.map_check_input(brief, table, new_tids)
            map_checks.append(st.run('v3-map-check-1', ctx, lambda raw: v3.check_map_input(raw, ctx)))
        if dup:
            owner = {d['direction_id']: t for t in brief['targets'] for d in t['directions']}
            goal_ids = sorted({did for d in dup for did, t in owner.items()
                               if any(d['point_id'] in p['point_id'] and t['target_id'] in p['target_ids'] for p in brief['points'])})
            if goal_ids:
                ctx = v3.coverage_input(brief, bank, goal_ids, [d['question_id'] for d in dup])
                value = st.run('v3-coverage-duplicate', ctx, lambda raw: v3.check_coverage(raw, ctx['goals'], ctx['questions']))
                for r in value['rows']:
                    rows[r['direction_id']] = _merge_row(rows.get(r['direction_id']), r)
        gone = {d['question_id'] for d in out_of_scope}
        off_questions = [q for q in bank['questions'] if q['question_id'] in gone]
        bank['questions'] = [q for q in bank['questions'] if q['question_id'] not in gone]
        stimuli = [s for s in stimuli if s['question_id'] not in gone]
    else:
        off_questions = []
    bank = _join_points(bank, brief, rows)

    # 3: add only for gap goals (≤2) ----------------------------------------
    # Round numbers are fixed (v3-add-0, v3-add-1): a resumed run replays completed rounds from their records,
    # so the recorded count only grows and never exceeds ADD_LIMIT.
    restated = []   # facts an add stage wrote again for existing conflicts; not taken, kept for the record
    for n in range(v3.ADD_LIMIT):
        gaps = [did for did in [d['direction_id'] for t in brief['targets'] for d in t['directions']] if rows[did]['status'] != 'covered']
        if not gaps:
            break
        allowed = v3.next_question_ids(bank, ADD_PER_GOAL * len(gaps))
        ctx = v3.add_input(brief, bank, gaps, allowed)
        if ledger['addRounds'] < n + 1:
            ledger['addRounds'] = n + 1
            st.save()
        value = st.run(f'v3-add-{n}', ctx, lambda raw: v3.check_added(raw, ctx))
        restated.extend({'stage': f'v3-add-{n}', **r} for r in v3.restated_facts(conflicts, value))
        bank, conflicts = v3.merge_added(visual.authored(bank), conflicts, value, allowed)
        stimuli = [*stimuli, *value['visual_stimuli']]
        bank = visual.render(bank, stimuli, packet, out / 'material')
        added = [q['question_id'] for q in value['questions']]
        for k, part in enumerate(chunks(gaps, COVERAGE_CHUNK)):
            ctx = v3.coverage_input(brief, bank, part, added)
            got = st.run(f'v3-coverage-{n + 1}-{k}', ctx, lambda raw, ctx=ctx: v3.check_coverage(raw, ctx['goals'], ctx['questions']))
            for r in got['rows']:
                rows[r['direction_id']] = _merge_row(rows[r['direction_id']], r)

    # 4: item review and fixes by batch -------------------------------------
    source_ids = [s['id'] for s in packet['sources']]
    reviews, fixes = {}, []

    def covered_by():
        cov = {}
        for did, r in rows.items():
            for q in v3.covering(r):
                cov.setdefault(q, []).append(did)
        return cov

    def review_batch(name, qids):
        """Reviews of `qids`: a recorded verdict for the same content is reused (P2); only the rest are asked."""
        got, todo = {}, []
        for q in bank['questions']:
            if q['question_id'] not in qids:
                continue
            again = v3.reusable(ledger['verdictLedger'], 'item', q['question_id'], v3.item_hash(q, bank, conflicts))
            if again is not None:
                got[q['question_id']] = again
            else:
                todo.append(q['question_id'])
        if not todo:
            return got
        ctx = v3.review_input(bank, todo, conflicts)
        value = st.run(name, ctx, lambda raw: v3.check_review_input(raw, ctx))
        by_id = {q['question_id']: q for q in bank['questions']}
        for r in value['reviews']:
            got[r['question_id']] = r
            entry = v3.ledger_entry('item', r['question_id'], v3.item_hash(by_id[r['question_id']], bank, conflicts), r, name)
            if entry not in ledger['verdictLedger']:   # a resumed run replays the same records
                ledger['verdictLedger'].append(entry)
        st.save()
        return got

    order = [q['question_id'] for q in bank['questions']]
    attempts = {}   # replayed from fixed stage names (v3-fix-<batch>-<k>); the ledger keeps the maximum seen
    for b, batch in enumerate(chunks(order, REVIEW_BATCH)):
        reviews.update(review_batch(f'v3-review-{b}-0', set(batch)))
        for k in range(v3.FIX_LIMIT):
            code = _bank_findings(bank, source_ids)
            targets = [q for q in batch if (v3.needs_fix(reviews[q]) or q in code) and attempts.get(q, 0) < v3.FIX_LIMIT]
            if not targets:
                break
            for q in targets:
                attempts[q] = attempts.get(q, 0) + 1
                ledger['fixAttempts'][q] = max(ledger['fixAttempts'].get(q, 0), attempts[q])
            st.save()
            findings = [{**reviews[q], 'code_findings': code.get(q, [])} for q in targets]
            ctx = v3.fix_input(bank, findings, targets, conflicts, covered_by())
            value = st.run(f'v3-fix-{b}-{k}', ctx, lambda raw: v3.check_fixed(raw, ctx))
            before_bank, before_reviews = copy.deepcopy(bank), {q: reviews[q] for q in targets}
            merged, conflicts, changed = v3.merge_fixes(visual.authored(bank), conflicts, value, targets)
            stimuli = [s for s in stimuli if s['question_id'] not in set(changed)] + value['visual_stimuli']
            bank = visual.render(merged, stimuli, packet, out / 'material')
            again = review_batch(f'v3-review-{b}-{k + 1}', set(changed))
            reverted = []
            for q in changed:
                if q in again and v3.worse(before_reviews[q], again[q]):
                    old = next(x for x in before_bank['questions'] if x['question_id'] == q)
                    bank['questions'] = [old if x['question_id'] == q else x for x in bank['questions']]
                    reviews[q] = before_reviews[q]
                    reverted.append(q)
                elif q in again:
                    reviews[q] = again[q]
            for q in changed:
                fixes.append({'question_id': q, 'attempt': attempts[q], 'stage': f'v3-fix-{b}-{k}', 'reverted': q in reverted})
            kept = [q for q in changed if q not in reverted]
            goals = sorted({did for q in kept for did, r in rows.items() if any(e['question_id'] == q for e in r['evidence'])})
            if goals:
                ctx = v3.coverage_input(brief, bank, goals, kept)
                got = st.run(f'v3-coverage-fix-{b}-{k}', ctx, lambda raw, ctx=ctx: v3.check_coverage(raw, ctx['goals'], ctx['questions']))
                for r in got['rows']:
                    rows[r['direction_id']] = _merge_row(rows[r['direction_id']], r, kept)

    # context and medical (once, medical-final/1) ---------------------------
    ctx = {k: base[k] for k in ('title', 'scope', 'lecture_id', 'sources')} | {'bank': bank, 'clinical_conflicts': conflicts}

    def accept_context(raw):
        jsonschema.validate(raw, g.output_schema(v2.CONTEXT_OUTPUT))
        v2.validate_context(raw)
        return raw
    context = st.run('context-0', ctx, accept_context)
    v3.require(not v2.context_blocks_medical(context), '독립 정답 검수 입력 분리가 완료되지 않았습니다. 결과를 만들지 않고 보존합니다.')
    med_ctx = {'title': packet['title'], 'bank': bank, 'clinicalInput': v2.medical_input(bank, conflicts), 'medicalFinal': True}
    medical = st.run('medical-0', med_ctx, lambda raw: validate_checks(raw, bank))

    # assembly ----------------------------------------------------------------
    coverage_rows = [rows[d['direction_id']] for t in brief['targets'] for d in t['directions']]
    review_rows = [reviews[q['question_id']] for q in bank['questions']]
    map_check = {k: [x for m in map_checks for x in m[k]] for k in ('relation_checks', 'target_checks', 'direction_checks', 'issues')}
    relation_seen = {}
    for r in map_check['relation_checks']:
        relation_seen.setdefault(r['relation_id'], r)   # a relation judged again for a new goal keeps its first judgment
    map_check['relation_checks'] = list(relation_seen.values())
    summary = ('root-generation/3: coverage, map check, item review and context judgments gathered by '
               'studyez_contracts.roots.generation_v3.assessment_raw; no judgment is filled in.')
    raw = v3.assessment_raw(brief, bank, coverage_rows, map_check, review_rows, context, summary)
    audit = v2.compile_assessment(brief, bank, envelope(brief, bank, raw))
    reviewed_bank = bank
    snapshot, projection = v2.project_container_concepts(bank)
    importance_proof = None
    if table is not None:
        snapshot, importance_proof = v2.project_importance(snapshot, brief, table)
    doc = v2.make_document(brief, reviewed_bank, audit, revision=packet['revision'], title=packet['title'], exam_date=packet['examDate'],
                           snapshot=snapshot if projection or importance_proof else None,
                           importance=v2.target_importance(brief, table) if importance_proof else None)
    not_ready = v3.not_ready(brief, coverage_rows, review_rows)
    result = {'brief': brief, 'document': doc, 'sourceAudit': audit, 'medical': medical,
              'validation': validate_bank(snapshot, source_ids), 'manifest': {
                  'pipelineVersion': POLICY, 'inputHash': packet['inputHash'], 'briefHash': document_hash(brief),
                  'bankHash': document_hash(doc['bank_snapshot']), 'model': codex.model_name(model), 'runtimeHash': ledger['identity'],
                  'stages': [{'name': k, **v} for k, v in ledger['stages'].items()],
                  'verdictLedger': ledger['verdictLedger'], 'verdictLedgerHash': document_hash(ledger['verdictLedger']),
                  'addRounds': ledger['addRounds'], 'notReady': not_ready,
                  'offGoalQuestions': [{'question_id': q['question_id'], 'question': q,
                                        'reason': next(d['reason'] for d in out_of_scope if d['question_id'] == q['question_id'])}
                                       for q in off_questions],
                  'rejectedAtIntake': rejected, 'intakeProjection': intake_changes, 'restatedFactsIgnored': restated,
                  'supplement': supplement, 'supplementPoints': points_doc if supplement else None,
                  'initialBrief': initial_brief, 'initialBank': initial_bank, 'coverage': coverage_rows, 'mapCheck': map_check,
                  'itemReviews': review_rows, 'clinicalContext': context, 'clinicalConflicts': conflicts,
                  'visualStimuli': stimuli, 'medicalFinal': True, 'sourceAssessment': raw, 'fixes': fixes,
                  **({'bankProjection': projection} if projection else {}),
                  **({'importanceProjection': importance_proof} if importance_proof else {}),
                  **({'stageResumes': ledger['stageResumes']} if ledger.get('stageResumes') else {}),
                  # map-tree/2: the server re-derives this packet from its request (studyez_contracts.roots.map_tree).
                  **({'derivedPacket': map_tree.public(packet), 'auditOpen': packet['frontStages']['openPoints']}
                     if 'derivedFrom' in packet else {})}}
    v3.validate_result(result, packet)
    g.write(out / 'result.json', result)
    return result

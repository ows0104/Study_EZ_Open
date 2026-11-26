"""unplaced-only/1: the questions of a published root-generation/4 revision that no goal took, placed again
(docs/changes/2026-11-15-unplaced-replace).

The published lectures were assembled under review-relations/1: a question its item review tied to no map relation
was left off the map, and nothing sent it anywhere after the review. On 2026-11-15 125 such questions of 27 lectures
were compared with the tasks: 9 were asked the same way by another task, the rest were not (or only the other way
round). This run starts from that published run (`previous`, its generation folder), as duplicates-only/1 does, and
changes nothing but the placement of those questions:

- the stage receipts of the previous run are linked into `out` and its ledger is pointed at this packet;
- the previous result is assembled again under review-relations/2 (B: a question its review ties to nothing is
  placed by the relations its coverage evidence names);
- what is still off the map (not because of a prerequisite) goes to the late supplement (`v4-supplement-late`), which
  sees no existing point (late-new-points): each question becomes a new point and goal, or stays off the map when it
  is judged out of scope. The new goals are normalized, judged for coverage and map-checked as in a new run;
- the result is assembled under this packet's revision. Questions, item reviews, importance, the medical review and
  the context judgments are the previous result's; no question leaves the bank, so none of them changes.

The map is not checked again (review-relations/2's A): a published map changed now would change every judgment.
The result is an ordinary /4 result (`generation_v4.validate_result`); the server takes it as the restart that
replaces the published revision."""
import copy
import json
import re
from pathlib import Path

from studyez_llm import codex
from studyez_contracts.roots import document_hash
from studyez_contracts.roots import generation_v2 as v2
from studyez_contracts.roots import generation_v3 as v3
from studyez_contracts.roots import generation_v4 as v4
from studyez_contracts.roots import map_tree
from . import connection_dedupe as dedupe
from . import source_update
from .connection_generate_v3 import Stages
from .connection_generate_v4 import _goals, check_stage

POLICY = 'unplaced-only/1'
X = 'v4-'
TAG = '-late'
LABEL = '못 붙은 문항 재배치'


def _merged_map_check(checks, repaired=None):
    """The first verdict of each relation, as a /4 run merges them; a relation the repair rewrote takes the verdict
    of its re-check instead (R4)."""
    value = {k: [x for m in checks for x in m[k]] for k in ('relation_checks', 'target_checks', 'direction_checks', 'issues')}
    seen = {}
    for r in value['relation_checks']:
        seen.setdefault(r['relation_id'], r)
    seen.update(repaired or {})
    value['relation_checks'] = list(seen.values())
    return value


UNSUPPORTED = ('unknown', 'conflict')
KEPT = ('targets', 'points', 'prerequisites', 'sources', 'scope', 'exclusions', 'lecture_id', 'recall_policy', 'schema_version')


def _check_repair(before, value, bad):
    """R4: a repair may rewrite only the unsupported relations (same IDs), add concepts, and change a concept only
    those relations use. Goals, directions, points and prerequisites stay, so no task and no judgment moves."""
    after = value['brief']
    for key in KEPT:
        v3.require(after.get(key) == before.get(key), f'관계 수선: {key}를 바꾸지 않습니다.')
    old_rel = {r['relation_id']: r for r in before['relations']}
    new_rel = {r['relation_id']: r for r in after['relations']}
    v3.require([r['relation_id'] for r in after['relations']] == [r['relation_id'] for r in before['relations']],
               '관계 수선: 관계 ID와 순서를 바꾸지 않습니다.')
    other = [rid for rid in old_rel if rid not in bad and new_rel[rid] != old_rel[rid]]
    v3.require(not other, f'관계 수선: 지도 점검이 지지한 관계는 바꾸지 않습니다: {other[:5]}')
    old_con = {c['concept_id']: c for c in before['concepts']}
    new_con = {c['concept_id']: c for c in after['concepts']}
    v3.require(set(old_con) <= set(new_con), '관계 수선: 기존 개념을 지우지 않습니다.')
    used = {cid for rid, r in old_rel.items() if rid not in bad for cid in (r['from_id'], r['to_id'])}
    used |= {cid for c in after['concepts'] for cid in c.get('parent_ids', []) if cid in old_con and c['concept_id'] not in old_con}
    touched = [cid for cid in old_con if new_con[cid] != old_con[cid] and cid in used]
    v3.require(not touched, f'관계 수선: 다른 관계가 쓰는 개념은 바꾸지 않습니다: {touched[:5]}')
    # The map is shown to students in the lecture's Korean (261111_02 repair rewrote labels as English sentences).
    # A list of organism names and numbers has no Korean of its own (261106_06 PR014 「B. fragilis 25%, …」): only an
    # English sentence (function words, no Hangul) is refused.
    english = [rid for rid in bad if _hangul(old_rel[rid].get('condition')) and _english(new_rel[rid].get('condition'))]
    english += [cid for cid in old_con if new_con[cid] != old_con[cid] and _hangul(old_con[cid]['label']) and _english(new_con[cid]['label'])]
    english += [cid for cid in new_con if cid not in old_con and _english(new_con[cid]['label'])
                and any(_hangul(c['label']) for c in before['concepts'])]
    v3.require(not english, f'관계 수선: 지도는 한국어로 씁니다(고유명사만 원문 표기). 한국어가 빠진 것: {english[:8]}')
    return value


def _hangul(text):
    return any('가' <= ch <= '힣' for ch in str(text or ''))


ENGLISH_WORDS = {'the', 'of', 'and', 'is', 'are', 'to', 'in', 'with', 'by', 'for', 'from', 'as', 'a', 'an', 'that', 'which',
                 'than', 'more', 'most', 'bind', 'binds', 'causes', 'cause', 'its', 'their', 'it', 'be', 'was', 'were', 'or'}


def _english(text):
    """An English sentence where the map is Korean: no Hangul and at least one English function word."""
    words = {w.lower() for w in re.findall(r'[A-Za-z]+', str(text or ''))}
    return not _hangul(text) and bool(words & ENGLISH_WORDS)


def run(packet, out, model, invoke, previous, resume=None):
    from . import connection_generate as g
    out, previous = Path(out), Path(previous)
    v3.require(packet.get('generationPolicy') == v4.POLICY, f'{LABEL}은 root-generation/4 packet만 받습니다.')
    # R1: without the earlier revisions' fingerprints the new revision would start every learner over.
    v3.require(packet.get('carrySources'), f'{LABEL}: 이전 판 문항 지문(carrySources)이 없어 학습 기록을 이을 수 없습니다. '
               '새 서버에서 다시 요청하세요.')
    old_packet = json.loads((previous / 'packet.json').read_text(encoding='utf-8'))
    old = json.loads((previous / 'result.json').read_text(encoding='utf-8'))
    v4.validate_result(old, old_packet)
    # notes-update/1 (docs/changes/2026-11-16-replace-updated-notes): only a source file may differ, with the same pages.
    changed = source_update.changed_sources(dedupe.lecture_input(old_packet), dedupe.lecture_input(packet), LABEL)
    update = source_update.compare(old_packet, packet, changed, LABEL) if changed else None
    v3.require(old['document']['revision'] != packet['revision'], f'{LABEL}: 새 판 이름이 이전 판과 같습니다.')
    v3.require(codex.model_name(model) == old['manifest']['model'],
               f"{LABEL}: 이전 실행의 모델({old['manifest']['model']})과 지금 모델({codex.model_name(model)})이 다릅니다.")
    meta, brief = old['manifest'], old['brief']
    v3.require(meta.get('placement') in ({'policy': v4.REVIEW_PLACEMENT}, {'policy': v4.REVIEW_PLACEMENT2}),
               f'{LABEL}: 문항 검토 배치(review-relations) 실행만 받습니다.')
    dedupe.seed(previous, out, packet, model, old, key='unplacedOnly', policy=POLICY, label=LABEL,
                extra={'placement': {'policy': v4.REVIEW_PLACEMENT2}})
    # A late stage of a previous /2 run had another input (it was offered the existing points): it runs again, recorded.
    st = Stages(packet, out, model, invoke, resume or packet.get('restartReason') or LABEL, policy=v4.POLICY, prompts=('v3', 'v4'))
    ledger = st.ledger
    v3.require(ledger.get('unplacedOnly', {}).get('previousRevision') == old['document']['revision'],
               f'{LABEL}: 이 폴더는 다른 판에서 시작했습니다.')

    if update:
        # The brief, the material the stages read and every judgment stay the earlier file's (the stage receipts are
        # checked against them); only the published document names the corrected file (spec R3).
        for r in update['sources']:
            print(f"── 필기 교체: {r['source_id']} {r['fromFilename']} → {r['toFilename']} · 바뀐 쪽 {r['changedPages']}", flush=True)

    placement = 'review-coverage'
    bank = v2.restore_container_concepts(v2.restore_importance(old['document']['bank_snapshot'], meta.get('importanceProjection')),
                                         meta.get('bankProjection'))
    order = [q['question_id'] for q in bank['questions']]
    rows = {r['direction_id']: copy.deepcopy(r) for r in meta['coverage']}
    map_checks = [meta['mapCheck']]
    reviews = meta['itemReviews']
    # answer-level/1 (docs/changes/2026-11-26-answer-holds-the-link): a revision made with it is assembled with it, from
    # the same recorded judgments the consumer reads.
    level = ({'answer_level': True, 'presuppositions': meta.get('presuppositions'), 'item_reviews': meta['itemReviews']}
             if v4.answer_level_on(meta) else {})
    basis = meta['questionImportance']
    profile = v4.notebook_profile(packet, meta)
    context = v3.context_summary(meta['clinicalContext'])
    page_counts = {s['source_id']: s['page_count'] for s in brief['sources']}
    points_doc = meta.get('supplementPoints') or v4.check_points(json.loads(packet['points']))
    supplement = copy.deepcopy(meta.get('supplement') or [])
    repaired = {}   # R4: relation -> its re-check after the repair

    def coverage_rows():
        return [rows[d['direction_id']] for t in brief['targets'] for d in t['directions']]

    def assemble():
        map_check = _merged_map_check(map_checks, repaired)
        raw = v4.assessment_raw(brief, bank, coverage_rows(), map_check, reviews, context, meta['sourceAssessment']['summary'], placement)
        audit = v4.compile_assessment(brief, bank, v2.envelope(brief, bank, raw), placement)
        doc, placed, proofs = v4.assemble(brief, bank, audit, coverage_rows(), basis, profile, revision=packet['revision'],
                                          title=packet['title'], exam_date=packet['examDate'], placement=placement, **level)
        return map_check, raw, audit, doc, placed, proofs

    before = len(meta['unplacedQuestions'])
    placed = assemble()[4]
    # R4 (사용자 「관계 수선 더해」): a question tied only to a relation the map check left unknown or in conflict
    # cannot become a task (261111_02: the late goals reused such relations, 1 of 13 placed). Those relations are
    # rewritten by the brief fix stage against the source and checked again; nothing else of the map changes.
    repair = {'relations': [], 'changed': [], 'supported': []}
    bad = {r['relation_id']: r for r in _merged_map_check(map_checks)['relation_checks'] if r['status'] in UNSUPPORTED}
    bad = {rid: c for rid, c in bad.items() if any(r['relation_id'] == rid for r in brief['relations'])}
    if bad and placed['unplacedQuestions']:
        rel = {r['relation_id']: r for r in brief['relations']}
        errors = [f"{rid}: 지도 점검 {c['status']} — {c['reason']} 현재 관계: {json.dumps(rel[rid], ensure_ascii=False)}. "
                  '원본에 맞게 이 관계의 끝점·condition(필요하면 새 세부 개념)을 고쳐 원본이 말하는 주장을 그대로 담게 한다. '
                  '관계 ID·kind, 목표·방향·포인트·선행 관계는 바꾸지 않는다. 고친 condition과 개념 이름은 기존 지도처럼 '
                  '한국어로 쓴다(균·바이러스 이름·약어 등 고유명사는 원문 표기 그대로, 영어 원문 문장을 옮겨 적지 않는다).'
                  for rid, c in bad.items()]
        pages = v3.cited_pages([e for rid in bad for e in rel[rid]['evidence']])
        old_brief = brief
        # The same check runs inside the model session (runner.root_native_json v3_check with this state), so a refused
        # repair goes back to the model instead of failing the lecture (261106_06, 2026-11-15).
        fixed = st.run(X + 'brief-fix' + TAG, {'brief': brief, 'errors': errors, 'pages': pages},
                       lambda raw: _check_repair(old_brief, v3.check_brief_fix(raw, {'brief': old_brief}), set(bad)),
                       {'repair': sorted(bad)})
        brief = v2.blank_target_importance(fixed['brief'])
        new_rel = {r['relation_id']: r for r in brief['relations']}
        changed = [rid for rid in bad if new_rel[rid] != rel[rid]]
        repair.update(relations=sorted(bad), changed=changed)
        tids = [t['target_id'] for t in brief['targets']
                if set(changed) & (set(t['relation_ids']) | {x for d in t['directions'] for x in d['relation_ids']})]
        if tids:
            ctx = v4.map_check_input(brief, tids)
            check = st.judged(X + 'map-check-fix' + TAG, ctx, lambda raw, ctx=ctx: v3.check_map_input(raw, ctx))
            repaired.update({r['relation_id']: r for r in check['relation_checks'] if r['relation_id'] in changed})
            repair['supported'] = sorted(rid for rid, r in repaired.items() if r['status'] == 'supported')
        st.save()
        placed = assemble()[4]
        print(f"── 관계 수선: 결함 관계 {len(bad)}개 · 고침 {len(changed)}개 · 다시 점검해 지지됨 {len(repair['supported'])}개 · "
              f"남은 미배치 {len(placed['unplacedQuestions'])}개", flush=True)
    late = [u['question_id'] for u in placed['unplacedQuestions'] if not u['reason'].startswith('dependency')]
    print(f"── {LABEL}: 이전 판 지도에 못 붙은 문항 {before}개 → 범위 점검 판정 뒤 {len(placed['unplacedQuestions'])}개 · "
          f"늦은 보충 {len(late)}개", flush=True)
    if late:
        ctx = v3.supplement_input(bank, late, points_doc, page_counts)
        ctx['points'] = []   # late-new-points: no existing point to name as a duplicate
        state = {'points_doc': points_doc}

        def accept(raw):
            rows_ = raw.get('rows') if type(raw) is dict else None
            v3.require(type(rows_) is not list or all(type(r) is not dict or r.get('decision') != 'duplicate_of' for r in rows_),
                       'late supplement: input.points is empty; decide point or out_of_scope, not duplicate_of')
            return check_stage('supplement', raw, ctx, state, None)
        value = st.run(X + 'supplement' + TAG, ctx, accept, state)
        points_doc, decided = v4.attach_points(points_doc, value, late, page_counts, [p['point_id'] for p in brief['points']])
        supplement.extend(decided)
        fresh = {d['point_id'] for d in decided if d['decision'] == 'point'}
        new_points = [p for p in points_doc['points'] if p['point_id'] in fresh]
        if new_points:
            allowed = v3.supplement_ids(brief, len(new_points))
            ctx = v3.supplement_normalize_input(brief, new_points, allowed)
            state = {'brief': brief, 'blank': True}
            addition = st.run(X + 'supplement-normalize' + TAG, ctx,
                              lambda raw: check_stage('supplement-normalize', raw, ctx, state, None), state)
            brief, new_tids = v3.extend_brief(brief, v3.supplement_addition(brief, addition, True), [p['point_id'] for p in new_points])
            new_dids = [d['direction_id'] for t in brief['targets'] if t['target_id'] in new_tids for d in t['directions']]
            ctx = v3.coverage_input(brief, bank, new_dids, [p['origin_question_id'] for p in new_points])
            got = st.judged(X + 'coverage-supplement' + TAG, ctx, lambda raw, ctx=ctx: v4.check_coverage(raw, ctx['goals'], ctx['questions']))
            rows.update({r['direction_id']: r for r in got['rows']})
            ctx = v4.map_check_input(brief, new_tids)
            map_checks.append(st.judged(X + 'map-check' + TAG, ctx, lambda raw, ctx=ctx: v3.check_map_input(raw, ctx)))
        st.save()

    map_check, raw, audit, doc, placed, proofs = assemble()
    rows_now = coverage_rows()
    ready_rows = v4.readiness(brief, rows_now, doc)
    record = {**ledger['unplacedOnly'], 'unplacedBefore': before, 'unplacedAfter': len(placed['unplacedQuestions']),
              'tasksBefore': len(old['document']['tasks']), 'tasksAfter': len(doc['tasks']), 'lateQuestions': late,
              'relationRepair': repair}
    print(f"── {LABEL} 조립: 과제 {record['tasksBefore']} → {record['tasksAfter']} · 지도에 못 붙은 문항 {before} → "
          f"{record['unplacedAfter']} · 범위 점검 판정 {len(placed['coverageFallback'])}개", flush=True)
    kept = {t['question_id'] for t in old['document']['tasks']}
    v3.require(kept <= {t['question_id'] for t in doc['tasks']} | {m['question_id'] for m in placed['mergedDuplicates']},
               f'{LABEL}: 이전 판의 과제가 빠졌습니다.')
    if update:
        update['questionsOnChangedPages'], update['conflictsOnChangedPages'] = source_update.on_changed_pages(
            update, doc['bank_snapshot'], reviews)
        record['sourceUpdate'] = update
        doc = v4.apply_source_update(doc, brief, packet, update)
        print(f"── 필기 교체: 바뀐 쪽을 근거로 한 문항 {len(update['questionsOnChangedPages'])}개 "
              f"{[q['question_id'] for q in update['questionsOnChangedPages']]} · 원본 충돌 기록 "
              f"{[c['conflict_id'] for c in update['conflictsOnChangedPages']]} — 문항은 그대로입니다. 사람이 확인하세요.", flush=True)
    g.write(out / 'readiness.json', {'rows': ready_rows, **placed, 'importanceWarnings': proofs['importanceWarnings']})
    doc['equivalences'], record['carry'] = v4.carry_links(doc, packet['carrySources'])
    previous_carry = next((r for r in record['carry'] if r['revision'] == old['document']['revision']), None)
    staying = {t['question_id'] for t in doc['tasks']}   # an old task merged as a duplicate stays off the task list
    v3.require(previous_carry and previous_carry['tasks'] == sum(t['question_id'] in staying for t in old['document']['tasks']),
               f'{LABEL}: 이전 판의 과제 중 같은 문항으로 이을 수 없는 것이 있습니다 — 학습 기록이 끊깁니다.')
    print(f"── {LABEL} 학습 기록 승계: " + ', '.join(f"{r['revision']} {r['tasks']}/{r['of']}과제" for r in record['carry']), flush=True)

    manifest = copy.deepcopy(meta)
    for key in ('coverageFallback',):
        manifest.pop(key, None)
    manifest.update(inputHash=packet['inputHash'], runtimeHash=ledger['identity'], briefHash=document_hash(brief),
                    bankHash=document_hash(doc['bank_snapshot']), stages=[{'name': k, **v} for k, v in ledger['stages'].items()],
                    verdictLedger=ledger['verdictLedger'], verdictLedgerHash=document_hash(ledger['verdictLedger']),
                    notReady=v4.not_ready(brief, rows_now, reviews), coverage=rows_now, mapCheck=map_check,
                    sourceAssessment=raw, readiness=ready_rows, importanceWarnings=proofs['importanceWarnings'],
                    importanceProjection=proofs['importanceProjection'], supplement=supplement,
                    supplementPoints=points_doc if supplement else None, placement={'policy': v4.REVIEW_PLACEMENT2},
                    unplacedOnly=record, **placed)
    if ledger.get('stageResumes'):
        manifest['stageResumes'] = ledger['stageResumes']
    if proofs['bankProjection']:
        manifest['bankProjection'] = proofs['bankProjection']
    else:
        manifest.pop('bankProjection', None)
    if 'derivedFrom' in packet:
        manifest.update(derivedPacket=map_tree.public(packet), auditOpen=packet['frontStages']['openPoints'])
    result = {'brief': brief, 'document': doc, 'sourceAudit': audit, 'medical': old['medical'],
              'validation': old['validation'], 'manifest': manifest}
    v4.validate_result(result, packet)
    g.write(out / 'result.json', result)
    return result

"""duplicates-only/1: a published root-generation/4 revision judged again for duplicates only
(docs/changes/2026-11-12-dedupe-published).

Lectures whose generation ran before goal-duplicates/1 (PR #117) can keep two or three tasks that ask one goal's
same answer: their coverage re-checks read each add round's questions alone, so a question written again was never
compared with the one already there. This run starts from that published run (`previous`, its generation folder)
and changes nothing but the duplicate groups:

- the stage receipts of the previous run are copied into `out` and its ledger is pointed at this packet (the new
  request of the same lecture input); no earlier stage runs again;
- every goal whose coverage evidence names two or more questions is judged once more with the current coverage
  prompt (`v4-coverage-dup-<k>`, side by side), reading exactly those questions;
- of that judgment only the duplicate groups are taken (`_merge_row` by evidence, as goal-duplicates/1): evidence,
  status and reasons stay the previous judgment's, so no goal's coverage and no question changes;
- the assessment, audit and document are assembled again under this packet's revision. Questions, item reviews,
  importance, the medical review and the context judgments are the previous result's.

The result is an ordinary /4 result (`generation_v4.validate_result`); the server takes it as the restart that
replaces the published revision. Learning records stay with the old revision (user decision 2026-11-12).
"""
import copy
import json
import os
import shutil
from pathlib import Path

from studyez_contracts.roots import document_hash
from studyez_contracts.roots import generation_v2 as v2
from studyez_contracts.roots import generation_v3 as v3
from studyez_contracts.roots import generation_v4 as v4
from studyez_contracts.roots import map_tree
from . import connection_batches as batches
from .connection_generate_v3 import Stages, chunks, _prompt_hash, COVERAGE_CHUNK
from .connection_generate_v4 import _first_evidence, _goals, _merge_row

POLICY = 'duplicates-only/1'
X = 'v4-'
# What the previous run's folder holds besides stage receipts: its own result and the work after publication.
NOT_COPIED = {'result.json', 'readiness.json', 'packet.json', 'ledger.json', 'evidence', 'choices', '.check-render'}
# Packet fields that name the request, not the lecture input; everything else must be the previous run's.
REQUEST_KEYS = {'generationId', 'revision', 'inputHash', 'derivedFrom', 'owner', 'privatePilot', 'requestedExamDate',
                'examDate', 'restartOf', 'restartReason', 'replacePublished', 'duplicatesOnly', 'operatorResumes'}
SOURCE_LOCAL = {'snapshotKey', 'localPath', 'downloadUrl'}


def lecture_input(packet):
    value = {k: v for k, v in map_tree.public(packet).items() if k not in REQUEST_KEYS}
    value['sources'] = [{k: v for k, v in s.items() if k not in SOURCE_LOCAL} for s in packet['sources']]
    return value


def identity(packet, model):
    """The ledger identity Stages computes for a /4 run of this packet (connection_generate_v3.Stages)."""
    from . import connection_generate as g
    return document_hash({'base': g.identity(packet, model), 'v3': v4.POLICY, 'prompts': _prompt_hash(('v3', 'v4'))})


def _link(src, dst):
    """Stage receipts are written once; a hard link shares them without copying gigabytes of `.native` work."""
    try:
        os.link(src, dst)
    except OSError:
        shutil.copy2(src, dst)


def seed(previous, out, packet, model, old_result):
    """Copy the previous run's receipts and point its ledger at this packet. A folder already seeded is kept."""
    if (out / 'ledger.json').exists():
        return
    v3.require(not any(out.glob('*.json')) or {p.name for p in out.glob('*.json')} <= {'packet.json'},
               '중복 재판정: 기존 산출물의 ledger가 없습니다. 자동 재시작하지 않습니다.')
    ledger = json.loads((previous / 'ledger.json').read_text(encoding='utf-8'))
    v3.require(ledger.get('pipelineVersion') == v4.POLICY, '중복 재판정: root-generation/4 실행만 받습니다.')
    v3.require(all(s['status'] == 'completed' for s in ledger['stages'].values()), '중복 재판정: 이전 실행에 끝나지 않은 단계가 있습니다.')
    v3.require(ledger.get('identity') == old_result['manifest']['runtimeHash'], '중복 재판정: 이전 실행의 ledger가 게시 결과와 다릅니다.')
    out.mkdir(parents=True, exist_ok=True)
    for item in sorted(previous.iterdir()):
        if item.name in NOT_COPIED:
            continue
        target = out / item.name
        if item.is_dir():
            shutil.copytree(item, target, copy_function=_link, dirs_exist_ok=True)
        else:
            _link(item, target)
    ledger['duplicatesOnly'] = {'policy': POLICY, 'previousRevision': old_result['document']['revision'],
                                'previousInputHash': ledger['inputHash'], 'previousIdentity': ledger['identity']}
    ledger.update(inputHash=packet['inputHash'], identity=identity(packet, model))
    (out / 'ledger.json').write_text(json.dumps(ledger, ensure_ascii=False, indent=2), encoding='utf-8')


def run(packet, out, model, invoke, previous, resume=None):
    from . import connection_generate as g
    out, previous = Path(out), Path(previous)
    v3.require(packet.get('generationPolicy') == v4.POLICY, '중복 재판정은 root-generation/4 packet만 받습니다.')
    old_packet = json.loads((previous / 'packet.json').read_text(encoding='utf-8'))
    old = json.loads((previous / 'result.json').read_text(encoding='utf-8'))
    v4.validate_result(old, old_packet)
    v3.require(lecture_input(old_packet) == lecture_input(packet), '중복 재판정: 이전 실행과 강의 입력이 다릅니다.')
    v3.require(old['document']['revision'] != packet['revision'], '중복 재판정: 새 판 이름이 이전 판과 같습니다.')
    seed(previous, out, packet, model, old)
    st = Stages(packet, out, model, invoke, resume, policy=v4.POLICY, prompts=('v3', 'v4'))
    ledger = st.ledger
    v3.require(ledger.get('duplicatesOnly', {}).get('previousRevision') == old['document']['revision'],
               '중복 재판정: 이 폴더는 다른 판에서 시작했습니다.')

    meta, brief = old['manifest'], old['brief']
    reviewed = v2.restore_container_concepts(v2.restore_importance(old['document']['bank_snapshot'], meta.get('importanceProjection')),
                                             meta.get('bankProjection'))
    placement = v4._placement4(old, brief, reviewed, meta)
    goals = _goals(brief)
    rows = {r['direction_id']: copy.deepcopy(r) for r in meta['coverage']}
    order = [q['question_id'] for q in reviewed['questions']]

    def asked(did):
        return {e['question_id'] for e in rows[did]['evidence'] if e['question_id'] in set(order)}
    judged = [did for did in goals if len(asked(did)) >= 2]
    print(f'── 중복 재판정: 근거 문항이 둘 이상인 목표 {len(judged)}개', flush=True)
    calls = []
    for k, part in enumerate(chunks(judged, COVERAGE_CHUNK) if judged else []):
        wanted = set().union(*(asked(did) for did in part))
        ctx = v3.coverage_input(brief, reviewed, part, [q for q in order if q in wanted])
        calls.append((f'{X}coverage-dup-{k}', ctx, lambda raw, ctx=ctx: v4.check_coverage(raw, ctx['goals'], ctx['questions'])))
    changed = []
    for got in batches.judgments(st, calls) if calls else []:
        for r in got['rows']:
            did = r['direction_id']
            before = rows[did]
            # goal-duplicates/1: the questions were judged for this goal before; their first evidence stays.
            merged = _merge_row(before, _first_evidence(before, r), goals[did], by_evidence=True)
            if merged['duplicates'] != before.get('duplicates', []):
                changed.append({'direction_id': did, 'before': before.get('duplicates', []), 'after': merged['duplicates']})
            rows[did] = {**before, 'duplicates': merged['duplicates']}
    st.save()

    coverage_rows = [rows[d['direction_id']] for t in brief['targets'] for d in t['directions']]
    raw = v4.assessment_raw(brief, reviewed, coverage_rows, meta['mapCheck'], meta['itemReviews'],
                            v3.context_summary(meta['clinicalContext']), meta['sourceAssessment']['summary'], placement)
    audit = v4.compile_assessment(brief, reviewed, v2.envelope(brief, reviewed, raw), placement)
    doc, placed, proofs = v4.assemble(brief, reviewed, audit, coverage_rows, meta['questionImportance'], v4.notebook_profile(packet, meta),
                                      revision=packet['revision'], title=packet['title'], exam_date=packet['examDate'],
                                      placement=placement)
    ready_rows = v4.readiness(brief, coverage_rows, doc)
    print(f"── 중복 재판정 조립: 과제 {len(old['document']['tasks'])} → {len(doc['tasks'])} · "
          f"중복으로 합침 {len(meta['mergedDuplicates'])} → {len(placed['mergedDuplicates'])} · 묶음이 바뀐 목표 {len(changed)}개", flush=True)
    v3.require(doc['tasks'], '중복 재판정: 학습 가능한 과제가 0개입니다.')
    g.write(out / 'readiness.json', {'rows': ready_rows, **placed, 'importanceWarnings': proofs['importanceWarnings']})

    manifest = copy.deepcopy(meta)
    manifest.update(inputHash=packet['inputHash'], runtimeHash=ledger['identity'], bankHash=document_hash(doc['bank_snapshot']),
                    stages=[{'name': k, **v} for k, v in ledger['stages'].items()],
                    verdictLedger=ledger['verdictLedger'], verdictLedgerHash=document_hash(ledger['verdictLedger']),
                    notReady=v4.not_ready(brief, coverage_rows, meta['itemReviews']), coverage=coverage_rows,
                    sourceAssessment=raw, readiness=ready_rows, importanceWarnings=proofs['importanceWarnings'],
                    importanceProjection=proofs['importanceProjection'], **placed,
                    duplicatesOnly={**ledger['duplicatesOnly'], 'judgedGoals': judged, 'changedGroups': changed,
                                    'tasksBefore': len(old['document']['tasks']), 'tasksAfter': len(doc['tasks'])})
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

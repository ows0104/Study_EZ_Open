"""Pure authoring envelopes and deterministic adapters; no semantic judgments."""
import copy
import re
from .validate import document_hash, validate_document
from studyez_contracts.learning_links.schema import REVIEW_SCHEMA, TEXT, obj, arr, enum
from studyez_contracts.learning_links.validate import validate_shape, validate_review, require, index_by
from studyez_contracts.bank.schema import REVIEW, schema_errors
from studyez_contracts.bank.validate import validate_bank

CORE = ('lecture_id', 'scope', 'sources', 'concepts', 'relations', 'targets', 'points')
BRIEF_SCHEMA = obj(schema_version=enum('learning-brief/1'),
    **{k: REVIEW_SCHEMA['properties'][k] for k in (*CORE, 'provenance')},
    prerequisites=arr(obj(before_target=TEXT, after_target=TEXT, relation_id=TEXT)),
    exclusions=arr(obj(point_id=TEXT, basis=enum('out_of_scope', 'duplicate', 'non_retrievable'))))
AUDIT_SCHEMA = obj(review=REVIEW_SCHEMA, question_checks=REVIEW, input_issues=arr(TEXT))


def packet_hash(packet):
    # operatorResumes: administrators' reasons to continue a request; not part of its input identity.
    clean = {k: v for k, v in packet.items() if k not in ('inputHash','webResponse','operatorResumes')}
    clean['sources'] = [{k: v for k, v in s.items() if k not in ('downloadUrl', 'localPath')} for s in packet['sources']]
    return document_hash(clean)


def pending_review(brief, bank):
    owners = {t['target_id']: [d['direction_id'] for d in t['directions']] for t in brief['targets']}
    exclusions = index_by(brief['exclusions'], 'point_id')
    require(set(exclusions) == {p['point_id'] for p in brief['points'] if p['scope_status'] == 'excluded'},
            'brief: every excluded point needs its authored basis')
    return {'schema_version': 'learning-links/1', 'hash_policy': 'learning-links-question/1',
            'bank_sha256': document_hash(bank), **{k: copy.deepcopy(brief[k]) for k in (*CORE, 'provenance')},
            'mappings': [], 'coverage': [
                {'point_id': p['point_id'], 'status': 'unknown' if p['scope_status'] == 'included' else 'excluded',
                 'confirmed_direction_ids': [], 'partial_direction_ids': [], 'missing_direction_ids': [],
                 'unknown_direction_ids': sorted({d for tid in p['target_ids'] for d in owners[tid]}),
                 'reason': '문항 생성 전 · 방향별 원본 대조 대기',
                 'exclusion_basis': exclusions[p['point_id']]['basis'] if p['scope_status'] == 'excluded' else None}
                for p in brief['points']]}


def source_intake(packet,sources):
    return {'title':packet['title'],'scope':packet['scope'],'examDate':packet['examDate'],
            'lecture_id':f"{packet['subject']}/{packet['runId']}",'sources':sources,'inputMode':'source'}


def validate_brief(brief, sources=None, *, from_sources=False):
    validate_shape(brief, BRIEF_SCHEMA, 'brief')
    if sources is not None:
        require(brief['sources'] == sources, 'brief: source inventory changed')
    if from_sources:
        require(brief['provenance']['independent_points']=='confirmed','brief: source-only extraction evidence required')
    else:
        require(brief['provenance']['independent_points'] != 'confirmed',
                'brief: supplied map/points are not newly certified independent extraction')
    # Reuse every reference/hierarchy/point/direction check with explicitly unknown coverage.
    review = pending_review(brief, {'questions': []})
    validate_document({'schema_version': 'roots/1', 'revision': 'brief-check', 'title': brief['scope']['label'],
        'review': review, 'bank_snapshot': {'questions': []}, 'bank_source': 'standalone', 'bank_build_id': None,
        'adopted_target_ids': [t['target_id'] for t in brief['targets']], 'tasks': [], 'exam_date': None,
        'equivalences': [], 'prerequisites': brief['prerequisites']})
    return copy.deepcopy(brief)


def validate_checks(checks, bank):
    require(type(checks) is dict and not schema_errors({k: checks.get(k) for k in ('summary', 'reviews')}, REVIEW), 'checks: malformed review')
    rows = index_by(checks['reviews'], 'question_id')
    require(set(rows) == {q['question_id'] for q in bank['questions']}, 'checks: missing/unknown question verdicts')
    return checks


def validate_audit(brief, bank, audit):
    if audit.get('schema_version')=='source-audit/2':
        from .generation_v2 import validate_audit as check
        return check(brief,bank,audit)
    validate_shape(audit, AUDIT_SCHEMA, 'audit')
    review = audit['review']
    require(all(review[k] == brief[k] for k in CORE), 'audit: supplied map/points/sources changed')
    require(review['provenance']['independent_points'] == brief['provenance']['independent_points'],
            'audit: extraction provenance changed')
    require(review['provenance']['status'] == 'reviewed', 'audit: source review is not complete')
    validate_review(review, bank, bank_sha256=document_hash(bank),
                    source_hashes={s['source_id']: s['sha256'] for s in brief['sources']})
    validate_checks(audit['question_checks'], bank)
    return audit


def make_document(brief, bank, audit, *, revision, title, exam_date,medical=None):
    if audit.get('schema_version')=='source-audit/2':
        from .generation_v2 import make_document as make
        return make(brief,bank,audit,revision=revision,title=title,exam_date=exam_date,medical=medical)
    validate_audit(brief, bank, audit)
    review = audit['review']
    coverage = {c['point_id']: c for c in review['coverage']}
    tasks = []
    for target in brief['targets']:
        relevant = [coverage[p['point_id']] for p in brief['points'] if target['target_id'] in p['target_ids']]
        for direction in target['directions']:
            did = direction['direction_id']
            if not relevant or not all(did in row['confirmed_direction_ids'] for row in relevant):
                continue
            qids = {m['question_id'] for m in review['mappings'] if m['direction_id'] == did
                    and set(direction['relation_ids']) <= set(m['tested_relation_ids'])}
            q = next((q for q in bank['questions'] if q['question_id'] in qids
                      and q.get('format', 'basic') in ('basic', 'list', 'cloze', 'ox', 'mcq', 'multi_select')), None)
            if q:
                tasks.append({'task_id': 'task-' + document_hash([q['question_id'], did])[:24],
                              'question_id': q['question_id'], 'direction_id': did})
    return validate_document({'schema_version': 'roots/1', 'revision': revision, 'title': title,
        'review': copy.deepcopy(review), 'bank_snapshot': copy.deepcopy(bank), 'bank_source': 'standalone', 'bank_build_id': None,
        'adopted_target_ids': [t['target_id'] for t in brief['targets']], 'tasks': tasks, 'exam_date': exam_date,
        'equivalences': [], 'prerequisites': copy.deepcopy(brief['prerequisites'])})


def validate_result(result, packet):
    from .parallel import is_v2_source
    """Check the final artifact and complete review sets again at the consumer."""
    if packet.get('generationPolicy') == 'root-generation/3':
        # docs/changes/2026-11-10-root-generation-3: the packet names /3; a /2 packet never accepts a /3 result.
        from .generation_v3 import validate_result as check3
        return check3(result, packet)
    if packet.get('generationPolicy') == 'root-generation/4':
        # docs/changes/2026-11-10-importance-at-authoring: exam points are a coverage checklist.
        from .generation_v4 import validate_result as check4
        return check4(result, packet)
    if packet.get('pipeline') is not None:
        # map-tree/1: the run used a generation packet derived from this request; re-derive it first.
        from .map_tree import FORMATS, resolve
        require(packet['pipeline'] in FORMATS, 'result: unknown generation pipeline')
        derived = resolve(result, packet)
        if derived.get('generationPolicy') == 'root-generation/3':
            from .generation_v3 import validate_result as check3
            return check3(result, derived)
        if derived.get('generationPolicy') == 'root-generation/4':
            from .generation_v4 import validate_result as check4
            return check4(result, derived)
        from .generation_v2 import validate_result as check
        return check(result, derived)
    if is_v2_source(packet):
        from .generation_v2 import validate_result as check
        return check(result,packet)
    require(type(result) is dict and set(result) == {'brief', 'document', 'sourceAudit', 'medical', 'validation', 'manifest'},
            'result: missing or unknown artifacts')
    brief, doc, manifest = result['brief'], result['document'], result['manifest']
    require(type(doc) is dict and type(manifest) is dict and type(result['validation']) is dict,
            'result: malformed document/manifest/validation')
    if packet.get('authoring')=='web':
        require(manifest.get('webResponseHash')==packet.get('webResponseHash') and packet.get('webResponseHash'),
                'result: missing original web response identity')
    from_sources=packet.get('inputMode')=='source'
    validate_brief(brief,from_sources=from_sources)
    if from_sources:
        require(packet.get('authoring')=='web' and not packet.get('conceptMap') and not packet.get('points'),
                'result: source-only extraction cannot use supplied points')
        require(manifest.get('sourceIntakeHash')==document_hash(source_intake(packet,brief['sources'])),
                'result: source-only intake evidence mismatch')
    require(brief['lecture_id'] == f"{packet['subject']}/{packet['runId']}", 'result: wrong lecture')
    require({s['source_id']: s['sha256'] for s in brief['sources']} == {s['id']: s['sha256'] for s in packet['sources']},
            'result: wrong source revision')
    expected = make_document(brief, doc['bank_snapshot'], result['sourceAudit'], revision=packet['revision'],
                             title=packet['title'], exam_date=packet['examDate'])
    require(doc == expected, 'result: content/target/task selection changed')
    validate_checks(result['medical'], doc['bank_snapshot'])
    ids = [s['id'] for s in packet['sources']]
    actual = validate_bank(doc['bank_snapshot'], ids)
    require(all(result['validation'].get(k) == actual[k] for k in ('pass', 'errors', 'warnings')),
            'result: altered validation verdict')
    require(validate_bank(doc['bank_snapshot'], ids, check_quality=False)['pass'], 'result: structurally unusable bank')
    require(all(not q.get('option_pools') for q in doc['bank_snapshot']['questions']), 'result: unreviewed option pools')
    require(all(q['format'] in ('basic','list','cloze','ox','mcq','multi_select') for q in doc['bank_snapshot']['questions']),
            'result: unsupported compound questions')
    require(type(manifest.get('runtimeHash')) is str and re.fullmatch(r'[a-f0-9]{64}', manifest['runtimeHash'])
            and type(manifest.get('model')) is str and manifest['model'].strip(), 'result: missing runtime identity')
    require(manifest.get('inputHash') == packet['inputHash'] and manifest.get('bankHash') == document_hash(doc['bank_snapshot'])
            and manifest.get('briefHash') == document_hash(brief), 'result: stale manifest')
    require(type(manifest.get('repairRounds')) is int and 0 <= manifest['repairRounds'] <= 3, 'result: repair budget exceeded')
    require(type(manifest.get('stages')) is list and manifest['stages']
            and all(type(s) is dict for s in manifest['stages']), 'result: missing execution evidence')
    stages = manifest['stages']
    needed = ['normalize', 'generate'] + [f'{kind}-{i}' for i in range(manifest['repairRounds'] + 1) for kind in ('source', 'medical')]
    needed += [f'repair-{i}' for i in range(1, manifest['repairRounds'] + 1)]
    require(len(stages) == len(needed) and {s.get('name') for s in stages} == set(needed)
            and all(s.get('status') == 'completed' and s.get('outputHash') for s in stages), 'result: incomplete/ambiguous execution')
    hashes = {s['name']: s['outputHash'] for s in stages}
    last = manifest['repairRounds']
    require(hashes['normalize'] == document_hash(brief)
            and hashes[f'source-{last}'] == document_hash(result['sourceAudit'])
            and hashes[f'medical-{last}'] == document_hash(result['medical'])
            and hashes[f'repair-{last}' if last else 'generate'] == document_hash(doc['bank_snapshot']),
            'result: stage output fingerprint mismatch')
    from .source_assessment import VERSION,compile_source_assessment
    require(packet.get('sourceAssessmentFormat') in (None,VERSION),'result: unsupported source assessment protocol')
    source_stages=[s for s in stages if s['name'].startswith('source-')]
    if (packet.get('sourceAssessmentFormat')==VERSION or 'sourceAssessment' in manifest
        or any('rawOutputHash' in s or 'sourceFormat' in s for s in source_stages)):
        require(all(s.get('sourceFormat')==VERSION and type(s.get('rawOutputHash')) is str
            and re.fullmatch(r'[a-f0-9]{64}',s['rawOutputHash']) for s in source_stages),
            'result: incomplete source assessment evidence')
        raw=manifest.get('sourceAssessment')
        require(next(s for s in source_stages if s['name']==f'source-{last}')['rawOutputHash']==document_hash(raw),
            'result: source assessment fingerprint mismatch')
        require(compile_source_assessment(brief,doc['bank_snapshot'],raw)==result['sourceAudit'],
            'result: source assessment compilation mismatch')
    return doc

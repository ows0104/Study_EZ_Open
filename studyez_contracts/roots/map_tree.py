"""map-tree/1: the Main-Quiz pilots' front stages as an administrator request (2026-11-09 사용자 설계 결정,
docs/changes/2026-11-09-main-quiz-runner-pipeline).

The two published pilots (감염병리1 26110803, 사슬알균 26110901) ran Map /3 → points /3 → point audit →
one point repair → re-audit by hand, then froze a `provided` packet for root-generation/2. A server
request with `pipeline: map-tree/1` asks the runner to run those same stages on the server-frozen sources
and derive that generation packet. This module is the deterministic part both sides share:

- `lecture_scope`: the scope sentence, from the lecture title and page counts only. The pilots'
  handwritten lecture facts (exam years, professors) are not invented here; the jokbo PDF carries them.
- `derive_packet`: server packet + front outputs → the generation packet (the pilots' packet shape).
- `resolve`: at the consumer, re-derive the generation packet from the result's evidence and the
  server packet, so `validate_result` checks the run against what the administrator requested.

Pure: no I/O, models, DB or server imports."""
import copy
import hashlib
import json
import re
from .automation import packet_hash
from studyez_contracts.learning_links.validate import require
from studyez_contracts.learning_links import concept_tree
from studyez_contracts.bank import importance as imp

PIPELINE = 'map-tree/1'
FORMAT = 'source-assessment/2-map-tree/1'      # the server packet; earlier runners stop before any model call
# map-tree/2 (docs/changes/2026-11-10-root-generation-3, PR C): the same front stages plus an independent
# question bank (1c) next to the Map and points; the derived packet runs root-generation/3.
PIPELINE2 = 'map-tree/2'
FORMAT2 = 'source-assessment/2-map-tree/2'
FORMATS = {PIPELINE: FORMAT, PIPELINE2: FORMAT2}
GENERATION_POLICY2 = 'root-generation/3'
GENERATION_FORMAT = 'source-assessment/2'       # the derived packet the generator runs
FRONT_POLICY = 'map-tree-front/1'
SOURCE_KINDS = {'S1': 'notes_current', 'S2': 'jokbo'}
FRONT_STAGES = ('map', 'point', 'audit', 'point-repair', 'final-audit')

# Verbatim from the pilots' packet step (2026-11-09-main-quiz-second-lecture/run.py packet()).
SCOPE_SUFFIX = ('conceptMap(concept-map-extract/3)과 points는 이미 원본에서 별도로 추출한 파일이다. 이번 단계는 제공 결과의 '
                '학습 구조 정규화이므로 derived로 표시한다. Map의 concept_id와 parent_id 계층을 그대로 보존하고, 갈래를 넘는 relations로 '
                '구조를 묻는 목표(root/branch)를 만든다. 제공 points의 point_id 및 point 원문과 source_refs를 보존한다. '
                '원본 충돌·제외·불확실성 notes를 보존한다. 문항수는 실제 인출/판단 가치로 정하며 포인트 개수와 일대일로 강제하지 않는다. '
                '같은 원본/포인트 전체와 목록 밖 누락을 검수하고 실제 답한 연결·제공된 연결·해설을 구분한다.')


def text_sha256(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def public(packet):
    """The packet without machine-local fields (the server never sees `localPath`)."""
    value = copy.deepcopy(packet)
    value['sources'] = [{k: v for k, v in s.items() if k not in ('localPath', 'downloadUrl')} for s in packet['sources']]
    return value


def pages_phrase(pages):
    """「S1 1~38쪽과 S2 1~8쪽」 — the page-review range of the point audit."""
    return '과 '.join(f'{sid} 1~{n}쪽' for sid, n in pages.items())


def lecture_scope(title, pages, extra=''):
    notes = [sid for sid in pages if SOURCE_KINDS.get(sid) == 'notes_current']
    jokbo = [sid for sid in pages if SOURCE_KINDS.get(sid) == 'jokbo']
    parts = [f'올해 필기 {sid} 전체({pages[sid]}쪽, 「{title}」)가 이 강의 범위다.' for sid in notes]
    for sid in jokbo:
        parts.append(f'{sid}는 이 강의 족보({pages[sid]}쪽)다. 각 쪽 머리의 연도·교수 표시를 따른다. '
                     '올해 같은 교수 기출을 우선 근거로 쓰고 다른 교수의 참고 기출은 참고로만 쓴다.')
    if jokbo:
        parts.append(f"{'·'.join(notes)}이 다루지 않는 {'·'.join(jokbo)} 내용은 범위 밖으로 둔다.")
    parts.append('원본의 교수 강조·필기자 표시·색상·범위/제외 설명을 구별해 보존한다.')
    if extra and extra.strip():
        parts.append('관리자 범위 메모: ' + extra.strip())
    return ' '.join(parts)


def format_for(pipeline):
    require(pipeline in FORMATS, 'map-tree: unknown pipeline')
    return FORMATS[pipeline]


def require_server_packet(packet):
    require(packet.get('pipeline') in FORMATS and packet.get('sourceAssessmentFormat') == FORMATS[packet['pipeline']],
            'map-tree: not a map-tree request')
    require(packet.get('inputMode') == 'source' and packet.get('authoring') == 'cli' and not packet.get('parallelAuthoring')
            and not packet.get('conceptMap') and not packet.get('points'), 'map-tree: the request must be source-only CLI')
    ids = [s['id'] for s in packet['sources']]
    require(ids in (['S1'], ['S1', 'S2']) and all(s['kind'] == SOURCE_KINDS[s['id']] for s in packet['sources']),
            'map-tree: sources are this year\'s notes (S1) and an optional jokbo (S2)')
    require(all(s['filename'].lower().endswith('.pdf') for s in packet['sources']), 'map-tree: the front stages read PDF pages')


def _refs(value, pages):
    if isinstance(value, list):
        for x in value: _refs(x, pages)
    elif isinstance(value, dict):
        if set(value) >= {'source_id', 'pages'} and isinstance(value.get('pages'), list):
            require(value['source_id'] in pages and all(type(p) is int and 1 <= p <= pages[value['source_id']] for p in value['pages']),
                    'map-tree: a source reference is outside the frozen pages')
        for x in value.values(): _refs(x, pages)


def check_outputs(concept_map, points, title, pages):
    """What the pilots checked before freezing the packet, minus the prompt-asset schemas (runner side)."""
    m = json.loads(concept_map); p = json.loads(points)
    require(m.get('schema_version') == concept_tree.VERSION and m.get('title') == title, 'map-tree: Map is not concept-map-extract/3 for this lecture')
    ids = [c['concept_id'] for c in m['concepts']]
    require(len(ids) == len(set(ids)) and all({r['from_id'], r['to_id']} <= set(ids) for r in m['relations']), 'map-tree: Map IDs')
    findings = concept_tree.tree_findings(m)
    require(not findings, 'map-tree: Map tree: ' + '; '.join(findings))
    require(p.get('schema_version') == 'exam-point-extract/3' and p.get('title') == title, 'map-tree: points are not exam-point-extract/3 for this lecture')
    pids = [x['point_id'] for x in p['points']]
    require(pids and len(pids) == len(set(pids)), 'map-tree: point IDs')
    imp.point_table(p['points'], p['notebook_profile'])  # every basis is computable (importance-basis/1)
    _refs(m, pages); _refs(p, pages)


HEX = re.compile(r'[a-f0-9]{64}')


def check_front(front, server, concept_map, points, bank=None):
    with_bank = server.get('pipeline') == PIPELINE2
    keys = {'policy', 'pageCounts', 'conceptMapSha256', 'pointsSha256', 'pointsFrom', 'audits', 'stages', 'prompts', 'resumes'}
    if with_bank:
        keys |= {'bankHash', 'openPoints'}
    require(type(front) is dict and set(front) == keys and front['policy'] == FRONT_POLICY, 'map-tree: malformed front-stage proof')
    pages = front['pageCounts']
    require(type(pages) is dict and list(pages) == [s['id'] for s in server['sources']]
            and all(type(n) is int and n > 0 for n in pages.values()), 'map-tree: page inventory')
    require(front['conceptMapSha256'] == text_sha256(concept_map) and front['pointsSha256'] == text_sha256(points), 'map-tree: front outputs changed')
    stages = front['stages']
    repaired = front['pointsFrom'] == 'point-repair'
    expected = ['map', 'point'] + (['bank'] if with_bank else []) + ['audit'] + (['point-repair', 'final-audit'] if repaired else [])
    require(front['pointsFrom'] in ('point', 'point-repair') and type(stages) is dict and list(stages) == expected,
            'map-tree: front stages out of order')
    for name, row in stages.items():
        require(type(row) is dict and set(row) == {'inputHash', 'outputSha256', 'sessionId', 'model', 'durationMs'}
                and HEX.fullmatch(row['inputHash']) and HEX.fullmatch(row['outputSha256'])
                and type(row['sessionId']) is str and row['sessionId'] and type(row['model']) is str and row['model'], 'map-tree: stage record ' + name)
    require(stages['map']['outputSha256'] == front['conceptMapSha256'] and stages[front['pointsFrom']]['outputSha256'] == front['pointsSha256'],
            'map-tree: front outputs are not the recorded stage outputs')
    audits = front['audits']
    require(type(audits) is list and len(audits) == (2 if repaired else 1), 'map-tree: audit summary')
    for row, name in zip(audits, ('audit', 'final-audit')):
        require(type(row) is dict and set(row) == {'stage', 'verdict', 'issues', 'unreadable'} and row['stage'] == name
                and row['verdict'] in ('ready', 'needs_revision') and type(row['issues']) is int and row['issues'] >= 0
                and (row['verdict'] == 'ready') == (row['issues'] == 0) and type(row['unreadable']) is int, 'map-tree: audit summary ' + name)
    require(repaired == (audits[0]['issues'] > 0), 'map-tree: one point repair exactly when the first audit found issues')
    require(type(front['prompts']) is dict and front['prompts'] and all(HEX.fullmatch(v) for v in front['prompts'].values()), 'map-tree: prompt hashes')
    require(type(front['resumes']) is list and all(type(r) is dict and set(r) == {'reason', 'stages'} and r['reason'].strip()
                                                   and type(r['stages']) is list for r in front['resumes']), 'map-tree: resume history')
    check_outputs(concept_map, points, server['title'], pages)
    if with_bank:
        from .validate import document_hash
        require(type(bank) is dict and set(bank) == {'bank', 'visual_stimuli', 'clinical_conflicts'}, 'map-tree: the independent bank is missing')
        require(front['bankHash'] == document_hash(bank) and stages['bank']['outputSha256'] == front['bankHash'],
                'map-tree: the independent bank is not the recorded bank stage output')
        _refs(bank, pages)
        pids = {p['point_id'] for p in json.loads(points)['points']}
        require(type(front['openPoints']) is list and set(front['openPoints']) <= pids
                and front['openPoints'] == sorted(set(front['openPoints'])), 'map-tree: open audit points')
    else:
        require(bank is None, 'map-tree/1 has no independent bank')


def derive_packet(server, concept_map, points, front, bank=None):
    """The generation packet: the pilots' `provided` packet built from the server-frozen request.
    map-tree/2 also carries the independent bank and names root-generation/3."""
    require_server_packet(server)
    require(packet_hash(server) == server['inputHash'], 'map-tree: server packet fingerprint')
    check_front(front, server, concept_map, points, bank)
    value = {k: copy.deepcopy(v) for k, v in server.items() if k not in ('inputHash', 'pipeline', 'operatorResumes')}
    value.update(scope=lecture_scope(server['title'], front['pageCounts'], server.get('scope', '')) + ' ' + SCOPE_SUFFIX,
                 conceptMap=concept_map, points=points, inputMode='provided', sourceAssessmentFormat=GENERATION_FORMAT,
                 speedStages=True, derivedFrom=server['inputHash'], frontStages=copy.deepcopy(front))
    if server['pipeline'] == PIPELINE2:
        value.update(generationPolicy=GENERATION_POLICY2, intakeBank=copy.deepcopy(bank))
    value['inputHash'] = packet_hash(value)
    return value


def resolve(result, server):
    """Consumer side: the generation packet this result ran, re-derived from the server request."""
    derived = result.get('manifest', {}).get('derivedPacket') if isinstance(result, dict) else None
    require(type(derived) is dict, 'map-tree: the result does not carry its derived generation packet')
    again = derive_packet(server, derived.get('conceptMap', ''), derived.get('points', ''), derived.get('frontStages'), derived.get('intakeBank'))
    require(public(again) == public(derived), 'map-tree: the generation packet is not derived from this request')
    return again

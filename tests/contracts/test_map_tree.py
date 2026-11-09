"""map-tree/1 request and derived generation packet (studyez_contracts.roots.map_tree). Pure; no files or models."""
import copy
import json
import pytest
from studyez_contracts.roots import map_tree as mt
from studyez_contracts.roots.automation import packet_hash, validate_result

TITLE = 'Synthetic lecture'
H = 'a' * 64
BASIS = [{'kind': 'current_exam', 'year': 2023, 'quote': '', 'reason': 'synthetic', 'refs': [{'source_id': 'S1', 'pages': [1]}]}]
MAP = json.dumps({'schema_version': 'concept-map-extract/3', 'title': TITLE, 'overview': 'o', 'relations': [], 'notes': [],
                  'concepts': [{'concept_id': c, 'parent_id': p, 'title': c, 'core_facts': ['f'], 'source_refs': [{'source_id': 'S1', 'pages': [1], 'locator': None}]}
                               for c, p in (('C001', None), ('C002', 'C001'), ('C003', 'C002'))]}, ensure_ascii=False)
POINTS = json.dumps({'schema_version': 'exam-point-extract/3', 'title': TITLE, 'notes': [],
                     'notebook_profile': {'legend': '', 'emphasis_style': 'slide', 'reason': 'r'},
                     'points': [{'point_id': 'P001', 'point': 'p', 'source_refs': [{'source_id': 'S1', 'pages': [2], 'locator': None}], 'importance_basis': BASIS}]},
                    ensure_ascii=False)


def server(**change):
    p = {'generationId': 'g' * 32, 'revision': 'auto-x', 'subject': 's', 'runId': 'r', 'title': TITLE, 'owner': 'admin', 'privatePilot': False,
         'sources': [{'id': 'S1', 'kind': 'notes_current', 'filename': 'n.pdf', 'sizeBytes': 1, 'sha256': H},
                     {'id': 'S2', 'kind': 'jokbo', 'filename': 'j.pdf', 'sizeBytes': 1, 'sha256': H}],
         'conceptMap': '', 'points': '', 'scope': '', 'examDate': None, 'authoring': 'cli', 'inputMode': 'source',
         'pipeline': mt.PIPELINE, 'sourceAssessmentFormat': mt.FORMAT, **change}
    p['inputHash'] = packet_hash(p)
    return p


def stage(out=H):
    return {'inputHash': H, 'outputSha256': out, 'sessionId': 's', 'model': 'm', 'durationMs': 1}


def front(**change):
    value = {'policy': mt.FRONT_POLICY, 'pageCounts': {'S1': 2, 'S2': 1}, 'conceptMapSha256': mt.text_sha256(MAP),
             'pointsSha256': mt.text_sha256(POINTS), 'pointsFrom': 'point',
             'audits': [{'stage': 'audit', 'verdict': 'ready', 'issues': 0, 'unreadable': 0}],
             'stages': {'map': stage(mt.text_sha256(MAP)), 'point': stage(mt.text_sha256(POINTS)), 'audit': stage()},
             'prompts': {'map-extract.md': H}, 'resumes': []}
    value.update(change)
    return value


def test_scope_is_built_from_title_and_pages_only():
    assert mt.lecture_scope('사슬알균', {'S1': 38, 'S2': 8}) == (
        '올해 필기 S1 전체(38쪽, 「사슬알균」)가 이 강의 범위다. S2는 이 강의 족보(8쪽)다. 각 쪽 머리의 연도·교수 표시를 따른다. '
        '올해 같은 교수 기출을 우선 근거로 쓰고 다른 교수의 참고 기출은 참고로만 쓴다. S1이 다루지 않는 S2 내용은 범위 밖으로 둔다. '
        '원본의 교수 강조·필기자 표시·색상·범위/제외 설명을 구별해 보존한다.')
    assert mt.lecture_scope('t', {'S1': 3}, ' memo ').endswith('관리자 범위 메모: memo') and '족보' not in mt.lecture_scope('t', {'S1': 3})
    assert mt.pages_phrase({'S1': 38, 'S2': 8}) == 'S1 1~38쪽과 S2 1~8쪽'


def test_derive_matches_the_pilot_packet_shape():
    p = server(scope='memo'); d = mt.derive_packet(p, MAP, POINTS, front())
    assert {k: d[k] for k in ('inputMode', 'sourceAssessmentFormat', 'speedStages', 'conceptMap', 'points', 'derivedFrom', 'revision')} == {
        'inputMode': 'provided', 'sourceAssessmentFormat': 'source-assessment/2', 'speedStages': True, 'conceptMap': MAP, 'points': POINTS,
        'derivedFrom': p['inputHash'], 'revision': 'auto-x'}
    assert 'pipeline' not in d and d['scope'] == mt.lecture_scope(TITLE, {'S1': 2, 'S2': 1}, 'memo') + ' ' + mt.SCOPE_SUFFIX
    assert d['inputHash'] == packet_hash(d) and mt.derive_packet(p, MAP, POINTS, front()) == d


@pytest.mark.parametrize('change', [{'parallelAuthoring': True}, {'inputMode': 'provided'}, {'conceptMap': '{}'}, {'pipeline': 'map-tree/2'},
                                    {'sourceAssessmentFormat': 'source-assessment/2'},
                                    {'sources': [{'id': 'S2', 'kind': 'jokbo', 'filename': 'j.pdf', 'sizeBytes': 1, 'sha256': H}]},
                                    {'sources': [{'id': 'S1', 'kind': 'notes_current', 'filename': 'n.md', 'sizeBytes': 1, 'sha256': H}]}])
def test_only_source_only_cli_requests_with_notes_pdf_are_map_tree(change):
    with pytest.raises(ValueError): mt.require_server_packet(server(**change))


@pytest.mark.parametrize('change', [
    {'pointsSha256': H}, {'pageCounts': {'S1': 2}}, {'pageCounts': {'S1': 1, 'S2': 1}}, {'pointsFrom': 'point-repair'},
    {'audits': [{'stage': 'audit', 'verdict': 'needs_revision', 'issues': 2, 'unreadable': 0}]},
    {'audits': [{'stage': 'audit', 'verdict': 'ready', 'issues': 1, 'unreadable': 0}]},
    {'stages': {'map': stage(), 'point': stage(mt.text_sha256(POINTS)), 'audit': stage()}},
    {'stages': {'point': stage(mt.text_sha256(POINTS)), 'map': stage(mt.text_sha256(MAP)), 'audit': stage()}},
    {'resumes': [{'reason': ' ', 'stages': []}]}, {'policy': 'other'}])
def test_front_evidence_is_checked(change):
    with pytest.raises(ValueError): mt.derive_packet(server(), MAP, POINTS, front(**change))


def test_front_outputs_are_checked_like_the_pilots():
    flat = json.loads(MAP); flat['concepts'][2]['parent_id'] = 'C001'
    other = json.dumps({**json.loads(POINTS), 'title': 'Other'}, ensure_ascii=False)
    late = json.loads(POINTS); late['points'][0]['source_refs'][0]['pages'] = [3]
    for m, p in ((json.dumps(flat), POINTS), (MAP, other), (MAP, json.dumps(late))):
        with pytest.raises(ValueError):
            mt.derive_packet(server(), m, p, front(conceptMapSha256=mt.text_sha256(m), pointsSha256=mt.text_sha256(p),
                                                    stages={'map': stage(mt.text_sha256(m)), 'point': stage(mt.text_sha256(p)), 'audit': stage()}))


def test_resolve_needs_the_derived_packet_from_this_request():
    p = server(); d = mt.derive_packet(p, MAP, POINTS, front())
    assert mt.resolve({'manifest': {'derivedPacket': mt.public(d)}}, p) == d
    with pytest.raises(ValueError): mt.resolve({'manifest': {}}, p)
    other = copy.deepcopy(mt.public(d)); other['examDate'] = '2026-12-01'
    with pytest.raises(ValueError): mt.resolve({'manifest': {'derivedPacket': other}}, p)


def test_the_consumer_rejects_an_unknown_pipeline():
    with pytest.raises(ValueError, match='pipeline'):
        validate_result({'manifest': {}}, server(pipeline='other/1'))

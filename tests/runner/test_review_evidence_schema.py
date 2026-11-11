"""러너는 /4 문항 검토 입력에 evidence_source가 있을 때만 근거 쪽이 있는 출력 스키마를 준다
(docs/changes/2026-11-11-evidence-from-citations)."""
from runner import root_native_json as native
from studyez_contracts.roots import generation_v4 as v4


def test_검토_입력에_필기가_있으면_근거_쪽_스키마():
    ctx = {'evidence_source': {'source_id': 'S1', 'page_count': 41}}
    assert native.schema_for('v4-review-0-0', ctx) is v4.ITEM_REVIEW_EVIDENCE_OUTPUT
    assert 'evidence' in native.schema_for('v4-review-context-1', ctx)['properties']['reviews']['items']['required']


def test_옛_실행과_다른_단계는_지금_스키마():
    assert native.schema_for('v4-review-0-0', {}) is v4.ITEM_REVIEW_OUTPUT
    assert native.schema_for('v4-fix-0-0', {'evidence_source': {'source_id': 'S1', 'page_count': 3}}) is v4.OUTPUTS['fix']
    assert 'evidence' not in native.schema_for('v3-review-0-0', {'evidence_source': {}})['properties']['reviews']['items']['properties']

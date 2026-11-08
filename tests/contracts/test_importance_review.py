"""importance-review/1: only target importance may change, every target once, with evidence for supported."""
import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import generation_v2_fixture as f  # noqa: E402
from studyez_contracts.roots import importance_review as imp, document_hash  # noqa: E402


def output(brief, status='insufficient'):
    ref = {'source_id': brief['sources'][0]['source_id'], 'locator': 'synthetic', 'pages': []}
    row = lambda kind: {'status': status, 'reason': 'Synthetic basis',
                        'evidence': [{'kind': kind, 'reason': 'Synthetic', 'refs': [ref]}] if status == 'supported' else []}
    return {'targets': [{'target_id': t['target_id'], 'importance': {'structural': row('structural_rationale'),
             'exam': row('observed_exam'), 'clinical': row('clinical_rationale')}} for t in brief['targets']]}


def proof(lineage, value):
    return {'policy': imp.POLICY, 'reason': 'approved', 'stage': 'source-2', 'briefBeforeHash': document_hash(lineage),
            'importance': value, 'sourceInputHash': '0' * 64, 'sourceRaw': {}, 'usage': {}, 'toolSha256': '1' * 64, 'modelCalls': 2}


@pytest.mark.parametrize('status', ['insufficient', 'supported'])
def test_apply_replaces_only_importance(status):
    lineage = f.brief()
    after = imp.apply(lineage, output(lineage, status))
    imp.only_importance_changed(lineage, after)
    assert all(t['importance']['exam']['status'] == status for t in after['targets'])
    assert imp.validate(proof(lineage, output(lineage, status)), lineage, after) == after


def test_rejects_missing_target_unreviewed_status_and_other_changes():
    lineage = f.brief()
    partial = output(lineage)
    partial['targets'].pop()
    with pytest.raises(ValueError):
        imp.apply(lineage, partial)
    unreviewed = output(lineage)
    unreviewed['targets'][0]['importance']['exam']['status'] = 'unreviewed'
    with pytest.raises(ValueError):
        imp.apply(lineage, unreviewed)
    after = imp.apply(lineage, output(lineage))
    changed = copy.deepcopy(after)
    changed['targets'][0]['title'] = 'Different goal'
    with pytest.raises(ValueError):
        imp.only_importance_changed(lineage, changed)
    with pytest.raises(ValueError):
        imp.validate(proof(lineage, output(lineage)), lineage, changed)
    with pytest.raises(ValueError):
        imp.validate({**proof(lineage, output(lineage)), 'modelCalls': 1}, lineage, after)

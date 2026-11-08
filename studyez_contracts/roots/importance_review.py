"""Importance completion and one final source re-audit after the correction budget.

When the final source audit cannot confirm any target because every target's importance axes are
still `unreviewed` with no evidence, an explicitly approved continuation (1) writes importance
status/reason/evidence for every target from the original sources and (2) asks for one fresh
source audit of the same bank under that brief. Questions, answers, directions, relations and the
correction budget are unchanged; only `targets[*].importance` differs from the lineage brief.
Pure checks: no model, DB or server use.
"""
import copy
from studyez_contracts.learning_links.schema import obj, arr, enum, TEXT, BASIS
from studyez_contracts.learning_links.validate import require, validate_shape
from .validate import document_hash

POLICY = 'importance-review/1'
AXES = ('structural', 'exam', 'clinical')
FILLED = obj(status=enum('supported', 'insufficient'), reason=TEXT, evidence=arr(BASIS))
OUTPUT = obj(targets=arr(obj(target_id=TEXT, importance=obj(structural=FILLED, exam=FILLED, clinical=FILLED))))


def apply(brief, output):
    """The brief with every target's importance replaced from `output` (nothing else)."""
    validate_shape(output, OUTPUT, 'importance')
    rows = {r['target_id']: r for r in output['targets']}
    require(len(rows) == len(output['targets']) and set(rows) == {t['target_id'] for t in brief['targets']},
            'importance: every target needs exactly one row')
    value = copy.deepcopy(brief)
    for target in value['targets']:
        target['importance'] = copy.deepcopy(rows[target['target_id']]['importance'])
    return value


def only_importance_changed(before, after):
    strip = lambda b: {**b, 'targets': [{k: v for k, v in t.items() if k != 'importance'} for t in b['targets']]}
    require(strip(before) == strip(after), 'importance: a field other than target importance changed')


def validate(proof, lineage_brief, final_brief):
    require(type(proof) is dict and set(proof) == {'policy', 'reason', 'stage', 'briefBeforeHash', 'importance',
                                                   'sourceInputHash', 'sourceRaw', 'usage', 'toolSha256', 'modelCalls'}
            and proof['policy'] == POLICY and type(proof['modelCalls']) is int and proof['modelCalls'] >= 2
            and type(proof['reason']) is str and proof['reason'].strip(),
            'importance: malformed review proof')
    require(proof['briefBeforeHash'] == document_hash(lineage_brief), 'importance: different lineage brief')
    expected = apply(lineage_brief, proof['importance'])
    only_importance_changed(lineage_brief, expected)
    require(final_brief == expected, 'importance: final brief is not the lineage brief with reviewed importance')
    return expected

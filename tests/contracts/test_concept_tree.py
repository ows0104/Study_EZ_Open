"""concept-map-extract/3: parent_id tree checks, preservation in the brief, prompt/schema/example agreement."""
import copy
import json
import re
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from studyez_contracts.learning_links import concept_tree as t

ASSETS = Path(__file__).resolve().parents[2] / 'content/prompts/learning-links'


def concept(cid, parent):
    return {'concept_id': cid, 'parent_id': parent, 'title': 'T' + cid, 'core_facts': ['f'],
            'source_refs': [{'source_id': 'S1', 'pages': [1], 'locator': None}]}


def tree(*pairs):
    return {'schema_version': t.VERSION, 'title': 'x', 'overview': 'o',
            'concepts': [concept(c, p) for c, p in pairs], 'relations': [], 'notes': []}


GOOD = tree(('C001', None), ('C002', 'C001'), ('C003', 'C002'), ('C004', None))


def test_valid_tree_and_depths():
    assert t.tree_findings(GOOD) == []
    assert t.depth_of(GOOD['concepts']) == {'C001': 0, 'C002': 1, 'C003': 2, 'C004': 0}


@pytest.mark.parametrize('pairs,needle', [
    ((('C001', None), ('C002', 'C009')), 'unknown parent_id'),
    ((('C001', 'C001'), ('C002', None)), 'itself'),
    ((('C001', 'C002'), ('C002', 'C001'), ('C003', None), ('C004', 'C003'), ('C005', 'C004')), 'cycle'),
    ((('C001', None), ('C002', 'C001')), 'two levels'),
    (tuple((f'C{i:03d}', None) for i in range(1, 10)) + (('C010', 'C001'), ('C011', 'C010')), 'top-level'),
])
def test_tree_rejections(pairs, needle):
    assert any(needle in e for e in t.tree_findings(tree(*pairs)))


def test_brief_preserves_map_parents():
    brief = {'concepts': [{'concept_id': 'C001', 'label': 'a', 'parent_ids': []},
                          {'concept_id': 'C002', 'label': 'b', 'parent_ids': ['C001', 'C004']},
                          {'concept_id': 'C003', 'label': 'c', 'parent_ids': ['C002']},
                          {'concept_id': 'C004', 'label': 'd', 'parent_ids': []},
                          {'concept_id': 'F003-01', 'label': 'fact', 'parent_ids': ['C003']}]}
    assert t.hierarchy_findings(brief, json.dumps(GOOD)) == []
    flat = copy.deepcopy(brief)
    flat['concepts'][2]['parent_ids'] = []
    del flat['concepts'][3]
    found = t.hierarchy_findings(flat, GOOD)
    assert len(found) == 2 and 'C003' in found[0] and 'C004' in found[1]


def test_older_maps_and_free_text_are_ignored():
    old = copy.deepcopy(GOOD)
    old['schema_version'] = 'concept-map-extract/2'
    for value in (json.dumps(old), '', None, 'not json', '[1,2]'):
        assert t.hierarchy_findings({'concepts': []}, value) == []


def test_prompt_schema_and_example_agree():
    schema = json.loads((ASSETS / 'map-output.schema.json').read_text(encoding='utf-8'))
    example = json.loads((ASSETS / 'map-output.example.json').read_text(encoding='utf-8'))
    prompt = (ASSETS / 'map-extract.md').read_text(encoding='utf-8')
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(example)
    assert t.tree_findings(example) == []
    blocks = re.findall(r'```json\s*([\s\S]*?)```', prompt)
    assert len(blocks) == 1 and json.loads(blocks[0]) == example
    assert 'concept-map-extract/3' in prompt and 'parent_id' in prompt and 'concept-map.json' in prompt
    missing = copy.deepcopy(example)
    del missing['concepts'][0]['parent_id']
    assert list(Draft202012Validator(schema).iter_errors(missing))
    # /2 is preserved for reading older pilots.
    v2 = json.loads((ASSETS / 'map-output-v2.schema.json').read_text(encoding='utf-8'))
    Draft202012Validator(v2).validate(json.loads((ASSETS / 'map-output-v2.example.json').read_text(encoding='utf-8')))

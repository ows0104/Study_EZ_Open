"""Development-only checks for the proposed extraction prompt formats; no model/DB."""
import copy
import json
import re
from pathlib import Path
from jsonschema import Draft202012Validator, ValidationError

ROOT = Path(__file__).resolve().parents[3]
ASSETS = ROOT / 'content/prompts/learning-links'


def unique(rows, key):
    keys = [r[key] for r in rows]
    assert len(keys) == len(set(keys)), 'duplicate ' + key
    return set(keys)


def validate(kind, value):
    schema = json.loads((ASSETS / f'{kind}-output.schema.json').read_text(encoding='utf-8'))
    Draft202012Validator(schema).validate(value)
    unique(value['sources'], 'source_id')
    sources = {s['source_id']: s for s in value['sources']}

    def refs(item):
        if isinstance(item, list):
            for child in item:
                refs(child)
        elif isinstance(item, dict):
            if set(item) == {'source_id', 'pages', 'locator'}:
                assert item['source_id'] in sources, 'unknown source'
                assert item['pages'] or item['locator'], 'missing source location'
                count = sources[item['source_id']]['page_count']
                assert count is None or all(p <= count for p in item['pages']), 'page outside source'
            for child in item.values():
                refs(child)

    refs(value)
    if kind == 'map':
        concepts = unique(value['concepts'], 'concept_id')
        unique(value['sections'], 'section_id')
        unique(value['relations'], 'relation_id')
        members = set()
        for section in value['sections']:
            ids = section['concept_ids']
            assert len(ids) == len(set(ids)) and set(ids) <= concepts, 'bad section member'
            members.update(ids)
        assert members == concepts, 'ungrouped concept'
        edges = []
        signatures = set()
        for r in value['relations']:
            assert {r['from_id'], r['to_id']} <= concepts, 'unknown endpoint'
            assert r['from_id'] != r['to_id'], 'self relation'
            pair = (r['from_id'], r['to_id'])
            if r['direction'] == 'undirected':
                pair = tuple(sorted(pair))
            signature = (pair, r['kind'], r['condition'])
            assert signature not in signatures, 'duplicate relation'
            signatures.add(signature)
            if r['kind'] in ('is_a', 'part_of'):
                edges.append(pair)
        graph = {c: [] for c in concepts}
        for a, b in edges:
            graph[a].append(b)
        done, active = set(), set()

        def visit(node):
            assert node not in active, 'classification cycle'
            if node in done:
                return
            active.add(node)
            for child in graph[node]:
                visit(child)
            active.remove(node)
            done.add(node)

        for c in concepts:
            visit(c)
    else:
        groups = unique(value['groups'], 'group_id')
        unique(value['points'], 'point_id')
        assert {p['group_id'] for p in value['points']} == groups, 'unknown/empty group'
        directions = [d for p in value['points'] for d in p['directions']]
        unique(directions, 'direction_id')
        for d in directions:
            if d['visual_requirement'] == 'required' and not d['visual_refs']:
                assert value['scope']['limitations'], 'missing visual source/limitation'


def main():
    examples = {}
    for kind in ('map', 'point'):
        schema = json.loads((ASSETS / f'{kind}-output.schema.json').read_text(encoding='utf-8'))
        Draft202012Validator.check_schema(schema)
        example = json.loads((ASSETS / f'{kind}-output.example.json').read_text(encoding='utf-8'))
        prompt = (ASSETS / f'{kind}-extract.md').read_text(encoding='utf-8')
        blocks = re.findall(r'```json\s*([\s\S]*?)```', prompt)
        assert len(blocks) == 1 and json.loads(blocks[0]) == example
        validate(kind, example)
        examples[kind] = example

    cases = []

    def reject(kind, name, change):
        item = copy.deepcopy(examples[kind])
        change(item)
        try:
            validate(kind, item)
        except (AssertionError, ValidationError):
            pass
        else:
            raise AssertionError('accepted invalid case: ' + name)
        cases.append(name)

    reject('map', 'extra key', lambda v: v.update(extra=True))
    reject('map', 'missing field', lambda v: v.pop('concepts'))
    reject('map', 'unknown endpoint', lambda v: v['relations'][0].update(to_id='C99'))
    reject('map', 'duplicate concept', lambda v: v['concepts'].append(v['concepts'][0]))
    reject('map', 'unknown source', lambda v: v['relations'][0]['evidence'][0].update(source_id='S99'))
    reject('map', 'outside page', lambda v: v['relations'][0]['evidence'][0].update(pages=[2]))
    reject('map', 'missing locator', lambda v: v['relations'][0]['evidence'][0].update(pages=[], locator=None))
    reject('map', 'wrong direction', lambda v: v['relations'][0].update(direction='undirected'))
    reject('map', 'classification cycle', lambda v: v['relations'].append({**v['relations'][0], 'relation_id':'R2', 'from_id':'C2', 'to_id':'C1'}))
    reject('point', 'unknown group', lambda v: v['points'][0].update(group_id='G99'))
    reject('point', 'duplicate direction', lambda v: v['points'][0]['directions'].append(v['points'][0]['directions'][0]))
    reject('point', 'empty answer elements', lambda v: v['points'][0]['directions'][0].update(answer_elements=[]))
    reject('point', 'unsupported evidence', lambda v: v['points'][0]['importance']['exam'].update(evidence=[]))
    reject('point', 'wrong importance basis', lambda v: v['points'][0]['importance']['exam'].update(basis=['clinical_rationale']))
    reject('point', 'empty successful extraction', lambda v: v.update(points=[], groups=[]))
    reject('point', 'partial without reason', lambda v: (v.update(extraction_status='partial'), v['scope'].update(limitations=[])))

    # Valid multiple memberships, multiple parents and a non-hierarchical feedback loop.
    graph = copy.deepcopy(examples['map'])
    graph['concepts'].append({**graph['concepts'][1], 'concept_id':'C3', 'label':'기타 개념'})
    graph['sections'].append({'section_id':'G2', 'title':'다른 맥락', 'summary':'교차 소속', 'concept_ids':['C1','C3']})
    graph['relations'].append({**graph['relations'][0], 'relation_id':'R2', 'to_id':'C3'})
    graph['relations'].extend([{**graph['relations'][0], 'relation_id':'R3', 'kind':'causal'}, {**graph['relations'][0], 'relation_id':'R4', 'kind':'causal', 'from_id':'C2', 'to_id':'C1'}])
    validate('map', graph)
    for kind, keys in [('map', ['sections','concepts','relations']), ('point', ['groups','points','excluded_candidates'])]:
        v = copy.deepcopy(examples[kind])
        v['extraction_status'] = 'unreadable'
        for key in keys:
            v[key] = []
        v['scope']['limitations'] = ['원본을 읽을 수 없음']
        validate(kind, v)
    print(json.dumps({'schemas':2, 'prompt_examples':2, 'invalid_cases_rejected':len(cases), 'graph_flexibility':True, 'unreadable_cases':2, 'model_calls':0}))


if __name__ == '__main__':
    main()

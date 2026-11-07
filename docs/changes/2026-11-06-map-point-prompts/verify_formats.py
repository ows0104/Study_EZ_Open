"""Development-only /2 prompt format checks; no runtime, model or database calls."""
import copy
import json
import re
from pathlib import Path
from jsonschema import Draft202012Validator, ValidationError
ROOT=Path(__file__).resolve().parents[3]
ASSETS=ROOT/'content/prompts/learning-links'
# 2026-11-08: Map /3 replaced map-extract.md; this pilot check keeps reading the /2 copies.
V={'map':'-v2','point':''}

def pairs(items):
    value={}
    for key,item in items:
        assert key not in value,'duplicate JSON key'
        value[key]=item
    return value

def read(path):return json.loads(path.read_text(encoding='utf-8'),object_pairs_hook=pairs)

def validate(kind,value,sources):
    Draft202012Validator(read(ASSETS/f'{kind}-output{V[kind]}.schema.json')).validate(value)
    def refs(v):
        if isinstance(v,list):
            for x in v:refs(x)
        elif isinstance(v,dict):
            if set(v)=={'source_id','pages','locator'}:
                assert v['source_id'] in sources,'unknown source'
                count=sources[v['source_id']]
                assert count is None or all(p<=count for p in v['pages']),'outside page'
            for x in v.values():refs(x)
    refs(value)
    key='concept_id'if kind=='map'else'point_id'
    rows=value['concepts'if kind=='map'else'points']
    ids=[r[key]for r in rows]
    assert len(ids)==len(set(ids)),'duplicate ID'
    if kind=='map':
        edges=set()
        for r in value['relations']:
            assert {r['from_id'],r['to_id']}<=set(ids),'unknown concept'
            sig=(r['from_id'],r['to_id'],r['relation'])
            assert sig not in edges,'duplicate relation'
            edges.add(sig)

def main():
    sources={'S1':1} # Frozen synthetic INPUT inventory; not model-authored metadata.
    samples={}
    for kind,filename in [('map','concept-map.json'),('point','exam-points.json')]:
        Draft202012Validator.check_schema(read(ASSETS/f'{kind}-output{V[kind]}.schema.json'))
        sample=read(ASSETS/f'{kind}-output{V[kind]}.example.json')
        prompt=(ASSETS/f'{kind}-extract{V[kind]}.md').read_text(encoding='utf-8')
        blocks=re.findall(r'```json\s*([\s\S]*?)```',prompt)
        assert len(blocks)==1 and json.loads(blocks[0],object_pairs_hook=pairs)==sample
        assert filename in prompt and 'UTF-8' in prompt
        validate(kind,sample,sources);samples[kind]=sample
    cases=[]
    def reject(kind,name,change):
        v=copy.deepcopy(samples[kind]);change(v)
        try:validate(kind,v,sources)
        except (AssertionError,ValidationError):pass
        else:raise AssertionError('accepted invalid case: '+name)
        cases.append(name)
    reject('map','extra field',lambda v:v.update(support={}))
    reject('map','wrong version',lambda v:v.update(schema_version='concept-map-extract/1'))
    reject('map','missing concepts',lambda v:v.pop('concepts'))
    reject('map','duplicate concept',lambda v:v['concepts'].append(v['concepts'][0]))
    reject('map','unknown concept',lambda v:v['relations'][0].update(to_id='C999'))
    reject('map','duplicate relation',lambda v:v['relations'].append(v['relations'][0]))
    reject('map','unknown source',lambda v:v['relations'][0]['source_refs'][0].update(source_id='S2'))
    reject('map','outside page',lambda v:v['relations'][0]['source_refs'][0].update(pages=[2]))
    reject('map','missing locator',lambda v:v['relations'][0]['source_refs'][0].update(pages=[],locator=None))
    reject('map','empty core facts',lambda v:v['concepts'][0].update(core_facts=[]))
    reject('map','empty without reason',lambda v:v.update(concepts=[],relations=[]))
    reject('point','duplicate point',lambda v:v['points'].append(v['points'][0]))
    reject('point','empty target',lambda v:v['points'][0].update(point=''))
    reject('point','missing evidence',lambda v:v['points'][0].update(source_refs=[]))
    reject('point','empty without reason',lambda v:v.update(points=[]))
    reject('point','invalid ID',lambda v:v['points'][0].update(point_id='C001'))
    graph=copy.deepcopy(samples['map'])
    graph['concepts'].append({**graph['concepts'][0],'concept_id':'C003','title':'제3의 개념'})
    graph['relations'] += [dict(graph['relations'][0],to_id='C003',relation='추가 맥락'),dict(graph['relations'][0],from_id='C002',to_id='C001',relation='반대 방향의 의미 있는 연결')]
    validate('map',graph,sources)
    for kind,keys in [('map',['concepts','relations']),('point',['points'])]:
        v=copy.deepcopy(samples[kind])
        for key in keys:v[key]=[]
        v['notes']=['원본을 읽을 수 없어 내용을 추출하지 못했다.']
        validate(kind,v,sources)
    located=copy.deepcopy(samples['point']);located['points'][0]['source_refs'][0].update(pages=[],locator='확인 가능한 절 제목')
    validate('point',located,sources)
    try:json.loads('{"title":"a","title":"b"}',object_pairs_hook=pairs)
    except AssertionError:pass
    else:raise AssertionError('duplicate JSON keys accepted')
    print(json.dumps(dict(schemas=2,prompt_examples=2,invalid_cases_rejected=len(cases),duplicate_json_keys_rejected=True,graph_flexibility=True,unreadable_cases=2,locator_only_case=True,model_calls=0)))
if __name__=='__main__':main()
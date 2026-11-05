"""One source-only targeted map correction; exact model-authored delta replay."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import followup as f
from copy import deepcopy
from studyez_contracts.learning_links.schema import obj,arr,TEXT

ITEMS={'concepts':'concept_id','relations':'relation_id','targets':'target_id','points':'point_id'}
SCHEMA=obj(**{k:arr(f.BRIEF_SCHEMA['properties'][k]['items'])for k in ITEMS},
    provenance=f.BRIEF_SCHEMA['properties']['provenance'],
    scope=f.BRIEF_SCHEMA['properties']['scope'],prerequisites=f.BRIEF_SCHEMA['properties']['prerequisites'],
    reasons=arr(TEXT,1))

def replay(previous,patch):
    value=deepcopy(previous)
    for field,key in ITEMS.items():
        ids=[row[key]for row in patch[field]];f.require(len(ids)==len(set(ids)),'Duplicate map patch ID')
        updates={row[key]:row for row in patch[field]};oldids={row[key]for row in previous[field]}
        value[field]=[deepcopy(updates.get(row[key],row))for row in previous[field]]
        value[field]+=[deepcopy(row)for row in patch[field]if row[key]not in oldids]
    for field in ('provenance','scope','prerequisites'):value[field]=deepcopy(patch[field])
    return value

def transition():
    old=f.read(f.OUT/'proof.json');current=f.proof();ledger=f.read(f.OUT/'ledger.json')
    f.require(all(s['status']=='completed'for s in ledger['stages'].values())and set(ledger['stages'])=={'map-1','repair-1','source-1','medical-1','repair-2','medical-2'},'Targeted transition requires completed round1 and repair2/medical2 only')
    f.require(old==f.read(f.OUT/'runtime/proof-before-targeted-map.json')and f.sha(f.OUT/'runtime/followup-before-targeted-map.py')==old['helperHash'],'Prior runtime snapshot changed')
    for key in ('baselineHash','originLedgerHash','sources','runtime','prompts','visualHelperHash','publicationAllowed'):
        f.require(current[key]==old[key],'Unrelated scope/runtime changed')
    f.require(old['limits']['map']==1 and current['limits']=={**old['limits'],'map':2},'Only targeted map-call ceiling may expand')
    f.require(not(f.OUT/'runtime/targeted-map-transition.json').exists(),'Targeted transition already recorded')
    f.g.write(f.OUT/'runtime/targeted-map-transition.json',{'before':old,'after':current,'budgetsReset':False,
        'reason':'Actual source1 findings7/9/11/12/13/14 prove normalization omissions/composite semantic overcredit remain within original20. One source-only targeted correction is necessary for the current explicit20-finding correction request; no question-derived map or original-budget reset.',
        'sourceFindingHash':f.g.document_hash(f.read(f.OUT/'audit-1.json')),'operatorScriptHash':f.sha(Path(__file__)),
        'existingStages':ledger['stages']})
    f.g.write(f.OUT/'proof.json',current)
    ledger['limits']=current['limits'];ledger.setdefault('scopeAdjustments',[]).append({'reason':'Actual normalization omissions within original20 require one source-only targeted map correction','oldMapCeiling':1,'newMapCeiling':2,'consumedMapCalls':1,'budgetsReset':False})
    f.g.write(f.OUT/'ledger.json',ledger)
    print('Targeted source-only correction ceiling2 recorded; all actual prior counts/evidence preserved.',flush=True)

def run():
    packet,_,_=f.verified();previous=f.read(f.OUT/'brief.json');ctx=f.context(packet)
    material=f.OUT/'source-only-material';f.require(not material.exists(),'Refuse source-only material overwrite')
    f.require(f.g.prepare(packet,material)==previous['sources'],'Source-only inventory changed')
    ctx.update(previous_source_only_brief=previous,operatorScriptHash=f.sha(Path(__file__)),
        sourceOnlyFiles=[{'name':p.name,'sha256':f.sha(p)}for p in sorted(material.iterdir())],
        source_completeness_diagnostics=['Basic nomenclature/mediator and general structural-reading relations may remain omitted. Independently inspect the original nervous-system diagrams and nitrogen-classification explanation; do not derive goals from questions.',
        'Some relations combine distinct facts or source-error statements so testing one part can be overcredited. Independently refine condition/cue/answer_scope correspondence and separate facts actually needed by included source points.',
        'Do not encode a reviewer meta-question as a learner factual retrieval goal. Unsupported prescription tables and per-drug exact-time inference remain limited, never fabricated.',
        'Retain actual clinical/disease background only to the degree supported in the lecture and scope. Not every possible reverse question requires a separate optional direction.'])
    prompt='''원본 전용의 한 차례 표적 지도 보완이다. BANK·문항·웹 응답·문항별 검수는 제공되지 않는다. 기존 독립 지도와 원본을 다시 대조한다. 학생이 실제 회상할 기초 관계 누락 및 복합 관계의 일부 회상을 전체 충족으로 잘못 계산할 수 있는 정의를 보완한다. 단순 문항 맞춤 지도나 무제한 방향 목록을 만들지 않는다.
전체 지도를 다시 반환하지 말고 지정 delta 스키마로 바뀌거나 추가된 concepts/relations/targets/points 항목만 완전한 객체로 반환한다. 나머지 항목은 코드가 그대로 보존한다. 원래28개 포인트의 ID/text/scope_status 및 exclusions는 보존한다. 원본의 실제 학습 범위를 늘리거나 줄여 준비율을 맞추지 않는다. 같은 의미 ID를 보존하며 의미가 달라진 정의/대체는 provenance.notes와 reasons에 명시한다. prerequisites/scope/provenance는 완전본을 반환한다. 원본 출처만 중요도 근거이며, 임상 검증을 실제로 수행했다고 주장하지 않는다.
복합 관계를 필요한 독립 사실로 나누되 지나친 원자화나 방향 폭증을 피한다. 모든 방향은 실제 같은 사실의 cue/answer_scope/relation_ids를 가진다. 원본의 오류·불확실한 용량/시간 수치를 안전한 임상 암기 대상으로 복원하지 않는다. 자료에 없는 중추 세부반응 등은 추가하지 않는다. source-only execution/provenance와 제외 범위를 정확히 기록한다.
'''+f.g.PROMPTS.joinpath('extract.md').read_text(encoding='utf-8')+'\n'+f.g.item_quality_guidance()
    patch=f.cli('map-2',ctx,SCHEMA,prompt,material_dir=material);value=replay(previous,patch)
    f.validate_brief(value,previous['sources'],from_sources=True)
    before={p['point_id']:p for p in previous['points']};after={p['point_id']:p for p in value['points']}
    f.require(set(before)<=set(after),'Map patch omitted source point')
    for key,p in before.items():f.require(all(p[k]==after[key][k]for k in ('text','scope_status')),'Map patch changed source text/scope')
    f.require(value['exclusions']==previous['exclusions'],'Map patch changed exclusions')
    f.g.write(f.OUT/'brief-before-map2.json',previous)
    f.g.write(f.OUT/'brief-changes-before-map2.json',f.read(f.OUT/'brief-changes.json'))
    f.g.write(f.OUT/'brief.json',value)
    base=f.read(f.BASE/'assembled-result.json')['brief'];diff={}
    for field,key in ITEMS.items():
        a={r[key]:r for r in base[field]};b={r[key]:r for r in value[field]}
        diff[field]={'added':sorted(b.keys()-a.keys()),'removed':sorted(a.keys()-b.keys()),'changed':[k for k in a.keys()&b.keys()if a[k]!=b[k]]}
    a={d['direction_id']:d for t in base['targets']for d in t['directions']};b={d['direction_id']:d for t in value['targets']for d in t['directions']}
    diff['directions']={'added':sorted(b.keys()-a.keys()),'removed':sorted(a.keys()-b.keys()),'changed':{k:{'before':a[k],'after':b[k],'equivalence':'not-assumed'}for k in a.keys()&b.keys()if a[k]!=b[k]}}
    diff['targetedCorrection']={'operatorScriptHash':f.sha(Path(__file__)),'authoredReasons':patch['reasons'],'beforeHash':f.g.document_hash(previous),'afterHash':f.g.document_hash(value)}
    f.g.write(f.OUT/'brief-changes.json',diff)
    print(f.json.dumps({**{k:len(value[k])for k in ITEMS},'directions':sum(len(t['directions'])for t in value['targets'])},ensure_ascii=False),flush=True)

if __name__=='__main__':
    if sys.argv[1:] ==['transition']:transition()
    elif sys.argv[1:] ==['run']:run()
    else:raise SystemExit('transition/run')

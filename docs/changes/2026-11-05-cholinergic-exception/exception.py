"""Explicit one-correction exception; only separate CLI sessions author medicine.

Old example, budgets and ledgers remain immutable. No production imports or writes.
"""
import sys,json,hashlib,shutil
from pathlib import Path
from copy import deepcopy
from collections import Counter

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
OLD_HERE=HERE.parent/'2026-11-04-cholinergic-findings'
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(OLD_HERE))
import followup as f
import round_patch as p
from studyez_contracts.learning_links.schema import obj,arr,enum,TEXT

OLD=f.OUT
OUT=ROOT/'runs/_examples/cholinergic-exception-20261105'
LIMITS={'repair':1,'source':1,'medical':1,'resolve':1}
ALLOWED={'Q077','Q101','Q142','Q092','Q109','Q130','Q066','Q118','Q136'}
AUTH='2026-11-05 KST 사용자: 추가 1회 예외로 핵심 보완. Q077 비교 목표 재정의, Q101 정답 노출, Q142 원본 그림 오류, D21·D61 회상 누락과 과도한 선행 조건만, 동일 자료, 운영 미게시.'
PATCH=deepcopy(p.PATCH)
PATCH['properties']['question_updates']['items']['properties']['question']['properties']['question_id']=enum(*sorted(ALLOWED))
PATCH['properties']['new_questions']['maxItems']=0
PATCH['properties']['removals']['maxItems']=0
DIR=deepcopy(f.BRIEF_SCHEMA['properties']['targets']['items']['properties']['directions']['items'])
DIR['properties']['direction_id']=enum('D10')
REL=deepcopy(f.BRIEF_SCHEMA['properties']['relations']['items']);REL['properties']['relation_id']=enum('R35')
PATCH['properties'].update(comparison_direction=DIR,comparison_relation=REL,comparison_change_reason=TEXT)
PATCH['required']+=['comparison_direction','comparison_relation','comparison_change_reason']
DECISION=obj(direction_id=TEXT,ready={'type':'boolean'},question_ids=arr(TEXT),reason=TEXT)
FINAL=obj(resolution=f.RESOLUTION,direction_decisions=arr(DECISION,1),
    approved_items=arr(obj(item=enum('comparison','answer_leak','source_image','D21','D61','prerequisites'),
        status=enum('resolved','bounded_limitation','unresolved'),reason=TEXT,evidence=arr(TEXT,1)),6))

def proof():
    packet=f.read(f.ORIGIN/'packet.json')
    return {'schema_version':'root-exception-proof/1','authorization':AUTH,'publicationAllowed':False,
        'priorExample':str(OLD.relative_to(ROOT)),'priorResultHash':f.sha(OLD/'result.json'),
        'priorLedgerHash':f.sha(OLD/'ledger.json'),'priorPresentationHash':f.sha(OLD/'presentation-audit.json'),
        'originLedgerHash':f.sha(f.ORIGIN/'ledger.json'),'priorCorrectionRounds':3,'additionalCorrectionLimit':1,
        'cumulativeCorrectionRound':4,'limits':LIMITS,'allowedQuestionIds':sorted(ALLOWED),
        'sources':[{k:s[k]for k in ('id','filename','sha256','sizeBytes')}for s in packet['sources']],
        'runtime':f.g.identity(packet,None),'helpers':{str(x.relative_to(ROOT)):f.sha(x)for x in
            [Path(__file__),OLD_HERE/'followup.py',OLD_HERE/'round_patch.py',OLD_HERE/'visual_support.py']},
        'prompts':{x.name:f.sha(x)for x in HERE.glob('*.md')if x.name in ('repair.md','resolve.md')},
        'referenceFiles':{x.name:f.sha(x)for x in sorted((OLD/'references').iterdir())if x.is_file()}}

def verified():
    f.require(f.read(OUT/'proof.json')==proof(),'Exception input/runtime drift')
    packet=f.read(f.ORIGIN/'packet.json')
    for s in packet['sources']:
        x=Path(s['localPath']);f.require(f.sha(x)==s['sha256']and x.stat().st_size==s['sizeBytes'],'Original source changed')
    return packet,f.read(f.BASE/'assembled-result.json'),f.read(OUT/'ledger.json')

def configure():
    f.OUT=OUT;f.LIMITS=LIMITS;f.verified=verified

def init():
    f.require(not OUT.exists(),'Never reset an existing exception')
    f.check()
    OUT.mkdir(parents=True)
    packet=f.read(f.ORIGIN/'packet.json');f.g.prepare(packet,OUT/'material')
    shutil.copytree(OLD/'references',OUT/'references')
    # Actual old crops are context only. New final crops are rendered independently.
    for x in (OLD/'material').glob('stimulus-3-*.png'):shutil.copy2(x,OUT/'material'/x.name)
    for name in ('baseline-issues.json','brief.json','brief-changes.json'):shutil.copy2(OLD/name,OUT/name)
    f.g.write(OUT/'proof.json',proof())
    f.g.write(OUT/'ledger.json',{'status':'active','startedAt':f.now(),'published':False,'stages':{},
        'limits':LIMITS,'priorCorrectionRounds':3,'cumulativeCorrectionRound':4,'budgetsReset':False,'authorization':AUTH})
    print('Explicit fourth correction initialized; previous histories unchanged.',flush=True)

def replay_brief(brief,patch):
    value=deepcopy(brief)
    for t in value['targets']:
        t['directions']=[deepcopy(patch['comparison_direction'])if d['direction_id']=='D10'else d for d in t['directions']]
    value['relations']=[deepcopy(patch['comparison_relation'])if r['relation_id']=='R35'else r for r in value['relations']]
    old_d=next(d for t in brief['targets']for d in t['directions']if d['direction_id']=='D10')
    f.require(patch['comparison_direction']['requirement']==old_d['requirement'],'Cannot improve required counts by changing scope')
    f.require(patch['comparison_direction']['relation_ids']==old_d['relation_ids'],'Comparison binding changed')
    old_r=next(r for r in brief['relations']if r['relation_id']=='R35')
    for key in ('from_id','to_id','kind','evidence'):
        f.require(patch['comparison_relation'][key]==old_r[key],'Comparison identity/source changed')
    return value

def enforce(bank,value,patch):
    f.require(not patch['new_questions']and not patch['removals'],'Exception does not authorize bank expansion')
    a={q['question_id']:q for q in bank['questions']};b={q['question_id']:q for q in value['questions']}
    f.require(a.keys()==b.keys(),'Question identity loss')
    changed={k for k in a if a[k]!=b[k]};f.require(changed<=ALLOWED,'Unapproved question edits')
    for key in a.keys()-ALLOWED:f.require(a[key]==b[key],'Unchanged question was rewritten')
    for key in ('Q130','Q066'):
        f.require({k:v for k,v in a[key].items()if k!='prerequisites'}=={k:v for k,v in b[key].items()if k!='prerequisites'},'Prerequisite-only scope exceeded')
    f.require({k:v for k,v in bank.items()if k not in ('questions','audit_summary')}==
        {k:v for k,v in value.items()if k not in ('questions','audit_summary')},'Unapproved bank metadata change')
    old=f.read(OLD/'stimuli-3.json')
    for qid in {s['question_id']for s in old}-{'Q142','Q109','Q136'}:
        keys=('question_id','source_id','page','crop','reason')
        f.require([{k:s[k]for k in keys}for s in old if s['question_id']==qid]==
            [s for s in patch['visual_stimuli']if s['question_id']==qid],'Unapproved stimulus change')
    return sorted(changed)

def repair():
    packet,_,_=verified();bank=f.read(OLD/'bank-3.json');brief=f.read(OLD/'brief.json')
    ctx=f.context(packet,brief,bank)
    ctx.update(authorization=AUTH,priorCorrectionRounds=3,currentCorrectionRound=4,additionalCorrectionLimit=1,
        baselineIssues=f.read(OLD/'baseline-issues.json'),sourceAudit=f.read(OLD/'audit-3.json'),
        medical=f.read(OLD/'medical-3.json'),finalResolution=f.read(OLD/'resolution.json'),
        conservativeAdoption=f.read(OLD/'presentation-audit.json'),previous_visual_stimuli=f.read(OLD/'stimuli-3.json'),
        referenceManifest=f.read(OLD/'references/manifest.json'),allowedQuestionIds=sorted(ALLOWED))
    patch=f.cli('repair-4',ctx,PATCH,(HERE/'repair.md').read_text(encoding='utf-8')+'\n'+f.g.item_quality_guidance())
    value=p.replay(bank,patch);changed=enforce(bank,value,patch);new_brief=replay_brief(brief,patch)
    f.validate_brief(new_brief,brief['sources'],from_sources=True)
    f.g.write(OUT/'bank-4.json',value);f.g.write(OUT/'brief.json',new_brief)
    f.g.write(OUT/'stimuli-4.json',f.visual.render(patch['visual_stimuli'],value,packet,OUT,4))
    f.g.write(OUT/'changes-4.json',{'beforeHash':f.g.document_hash(bank),'afterHash':f.g.document_hash(value),
        'changed':changed,'added':[],'removed':[],'questionCount':len(value['questions']),
        'questionUpdates':patch['question_updates'],'orderChanged':[q['question_id']for q in bank['questions']]!=patch['question_order'],
        'comparisonBefore':{'direction':next(d for t in brief['targets']for d in t['directions']if d['direction_id']=='D10'),
            'relation':next(r for r in brief['relations']if r['relation_id']=='R35')},
        'comparisonAfter':{'direction':patch['comparison_direction'],'relation':patch['comparison_relation']},
        'comparisonChangeReason':patch['comparison_change_reason'],'equivalence':'not-assumed','operatorHash':f.sha(Path(__file__))})
    val=f.g.validate_bank(value,[s['id']for s in packet['sources']]);f.g.write(OUT/'validation-4.json',val)
    f.require(f.g.validate_bank(value,[s['id']for s in packet['sources']],check_quality=False)['pass'],'Structural validation failed')
    print(json.dumps({'changed':changed,'questions':len(value['questions']),'pass':val['pass']},ensure_ascii=False),flush=True)

def resolve():
    packet,_,_=verified();brief=f.read(OUT/'brief.json');bank=f.read(OUT/'bank-4.json')
    ctx=f.context(packet,brief,bank)
    ctx.update(authorization=AUTH,baselineIssues=f.read(OUT/'baseline-issues.json'),
        originalBaseline=f.read(f.BASE/'assembled-result.json'),priorResolution=f.read(OLD/'resolution.json'),
        priorConservativeAdoption=f.read(OLD/'presentation-audit.json'),questionChanges=f.read(OUT/'changes-4.json'),
        sourceAudit=f.read(OUT/'audit-4.json'),medical=f.read(OUT/'medical-4.json'),
        currentTasks=f.read(OUT/'document-4.json')['tasks'],visualStimuli=f.read(OUT/'stimuli-4.json'),
        technicalEvidence=f.read(OLD/'presentation-audit.json')['technicalEvidence'])
    value=f.cli('resolve-4',ctx,FINAL,(HERE/'resolve.md').read_text(encoding='utf-8'))
    dirs={d['direction_id']for t in brief['targets']for d in t['directions']};rows=value['direction_decisions']
    f.require(len(rows)==len(dirs)and {x['direction_id']for x in rows}==dirs,'Each current direction requires one semantic decision')
    f.require(len(value['approved_items'])==6 and len({r['item']for r in value['approved_items']})==6,'Missing approved-item disposition')
    f.require(len(value['resolution']['issues'])==20 and {r['issue_id']for r in value['resolution']['issues']}=={f'I{i:02}'for i in range(1,21)},'Missing original20')
    f.require(len(value['resolution']['directions'])==3 and {r['original_direction_id']for r in value['resolution']['directions']}=={'D10','D15','D17'},'Missing original3')
    known={q['question_id']for q in bank['questions']}
    for r in rows:f.require(set(r['question_ids'])<=known,'Unknown decision question')
    f.g.write(OUT/'adjudication.json',value);f.g.write(OUT/'resolution.json',value['resolution'])
    print(json.dumps({'approvedItems':value['approved_items'],'ready':sum(r['ready']for r in rows)},ensure_ascii=False),flush=True)

def bundle():
    packet,base,ledger=verified();f.require(not(OUT/'result.json').exists(),'Never overwrite result')
    f.require(set(ledger['stages'])=={'repair-4','source-4','medical-4','resolve-4'}and all(v['status']=='completed'for v in ledger['stages'].values()),'Incomplete stages')
    brief=f.read(OUT/'brief.json');bank=f.read(OUT/'bank-4.json');audit=f.read(OUT/'audit-4.json');medical=f.read(OUT/'medical-4.json')
    doc=f.read(OUT/'document-4.json');res=f.read(OUT/'resolution.json');adj=f.read(OUT/'adjudication.json')
    dirs={d['direction_id']:d for t in brief['targets']for d in t['directions']};source={r['question_id']:r for r in audit['question_checks']['reviews']}
    med={r['question_id']:r for r in medical['reviews']};dec={r['direction_id']:r for r in adj['direction_decisions']}
    usable=[t for t in doc['tasks']if dec[t['direction_id']]['ready']and t['question_id']in dec[t['direction_id']]['question_ids']and
        source[t['question_id']]['verdict']=='ok'and med[t['question_id']]['verdict']=='ok']
    ready={t['direction_id']for t in usable}
    summary={'questions':len(bank['questions']),'targets':len(brief['targets']),'directions':len(dirs),'concepts':len(brief['concepts']),
        'points':len(brief['points']),'tasks':len(doc['tasks']),'unreadyDirections':sorted(set(dirs)-ready),
        'sourceVerdicts':dict(Counter(r['verdict']for r in source.values())),'medicalVerdicts':medical['counts'],
        'coverage':dict(Counter(c['status']for c in audit['review']['coverage'])),
        'issueDispositions':dict(Counter(r['status']for r in res['issues'])),
        'originalUnready':{r['original_direction_id']:r['ready']for r in res['directions']},
        'inputIssues':len(audit['input_issues']),'repairRounds':4,'exceptionRepairs':1,'published':False}
    old_result=f.read(OLD/'result.json')
    value={'schema_version':'root-example/2','purpose':'read-only-example','proof':f.read(OUT/'proof.json'),'baselineSummary':old_result['summary'],
        'brief':brief,'bank':bank,'sourceAssessment':f.read(OUT/'assessment-4.json'),'sourceAudit':audit,'medical':medical,
        'document':doc,'resolution':res,'adjudication':adj,'summary':summary,'validation':f.read(OUT/'validation-4.json'),
        'mapChanges':{'prior':old_result['mapChanges'],'exception':f.read(OUT/'changes-4.json')},
        'questionChanges':[f.read(OUT/'changes-4.json')],'finalRound':4,'referenceManifest':f.read(OUT/'references/manifest.json'),
        'visualStimuli':f.read(OUT/'stimuli-4.json'),'technicalRecoveryProof':old_result['technicalRecoveryProof']}
    f.g.write(OUT/'result.json',value);f.g.write(OUT/'summary.json',summary)
    presentation={'schema_version':'root-example-presentation/1','resultHash':f.sha(OUT/'result.json'),
        'resolutionHash':f.g.document_hash(res),'sourceTaskCount':len(doc['tasks']),'reviewedTaskCount':len(usable),
        'reviewHolds':[{'direction_id':r['direction_id'],'question_id':','.join(r['question_ids']),'reason':r['reason'],'basis':'adjudication.direction_decisions'}for r in adj['direction_decisions']if not r['ready']],
        'reviewedTasks':usable,'unreadyDirections':sorted(set(dirs)-ready),
        'requiredDirectionCount':sum(d['requirement']=='required'for d in dirs.values()),
        'readyRequiredDirectionCount':sum(dirs[x]['requirement']=='required'for x in ready),
        'technicalEvidence':f.read(OLD/'presentation-audit.json')['technicalEvidence'],
        'policy':'Require canonical whole-direction task, independent semantic acceptance of that question, source ok and medical ok; preserve raw outputs.',
        'builderHash':f.sha(Path(__file__))}
    f.g.write(OUT/'presentation-audit.json',presentation)
    ledger.update(status='completed',finishedAt=f.now(),resultHash=f.g.document_hash(value));f.g.write(OUT/'ledger.json',ledger)
    check()

def check():
    packet,base,ledger=verified();value=f.read(OUT/'result.json');f.require(ledger['status']=='completed'and not ledger['published'],'Not completed/unpublished')
    f.require(ledger['resultHash']==f.g.document_hash(value),'Result hash mismatch')
    f.require(set(ledger['stages'])=={'repair-4','source-4','medical-4','resolve-4'},'Budget mismatch')
    for name,s in ledger['stages'].items():
        stage=OUT/'stages'/name;f.require(s['status']=='completed','Incomplete stage')
        f.require(f.sha(stage/'raw.txt')==s['rawHash']and f.sha(stage/'usage.json')==s['usageHash'],'Raw stage drift')
        f.require(f.g.document_hash(f.read(stage/'output.json'))==s['outputHash'],'Output drift')
        if not name.startswith('medical'):
            f.require(f.sha(stage/'prompt.txt')==s['promptHash']and f.g.document_hash(f.read(stage/'input.json'))==s['inputHash'],'Input drift')
    patch=f.read(OUT/'stages/repair-4/output.json');old=f.read(OLD/'bank-3.json')
    f.require(p.replay(old,patch)==value['bank'],'Delta replay mismatch');enforce(old,value['bank'],patch)
    f.require(replay_brief(f.read(OLD/'brief.json'),patch)==value['brief'],'Map replay mismatch')
    f.validate_brief(value['brief'],base['brief']['sources'],from_sources=True);f.validate_checks(value['medical'],value['bank'])
    f.require(f.compile_source_assessment(value['brief'],value['bank'],value['sourceAssessment'])==value['sourceAudit'],'Source compile mismatch')
    f.require(f.make_document(value['brief'],value['bank'],value['sourceAudit'],revision='example-findings-4',title=packet['title'],exam_date=packet['examDate'])==value['document'],'Document mismatch')
    f.require(value['validation']['pass'],'Bank quality/structure validation failed')
    actual=f.g.validate_bank(value['bank'],[s['id']for s in packet['sources']])
    f.require({k:v for k,v in actual.items()if k!='checked_at'}=={k:v for k,v in value['validation'].items()if k!='checked_at'},'Bank validation drift')
    for r in value['visualStimuli']:f.require(f.sha(OUT/'material'/r['imageFile'])==r['imageSha256'],'Image drift')
    from studyez_llm import codex
    stage=OUT/'stages/medical-4';parsed=codex.parse_events((stage/'blind-events.jsonl').read_text(encoding='utf-8'),blind=True,model=codex.model_name())
    f.require(json.loads(parsed['text'])==f.read(stage/'output.json'),'Blind transcript mismatch')
    inputs=f.read(stage/'input-images.json');f.require([r['imageSha256']for r in inputs]==[r['imageSha256']for r in value['visualStimuli']],'Blind review images differ')
    source_input=f.read(OUT/'stages/source-4/input.json')
    f.require(set(source_input)==set(f.context(packet,value['brief'],value['bank']))|{'visualStimuli','operatorScriptHash'},'Source reviewer saw prior judgments')
    f.require(value['adjudication']==f.read(OUT/'stages/resolve-4/output.json'),'Adjudication drift')
    pres=f.read(OUT/'presentation-audit.json');dec={r['direction_id']:r for r in value['adjudication']['direction_decisions']}
    src={r['question_id']:r['verdict']for r in value['sourceAudit']['question_checks']['reviews']};med={r['question_id']:r['verdict']for r in value['medical']['reviews']}
    expected=[t for t in value['document']['tasks']if dec[t['direction_id']]['ready']and t['question_id']in dec[t['direction_id']]['question_ids']and src[t['question_id']]=='ok'and med[t['question_id']]=='ok']
    f.require(expected==pres['reviewedTasks']and pres['resultHash']==f.sha(OUT/'result.json'),'Presentation credit mismatch')
    print(json.dumps({'pass':True,**value['summary'],'reviewedTasks':len(expected),'readyRequired':pres['readyRequiredDirectionCount'],'verifierHash':f.sha(Path(__file__))},ensure_ascii=False),flush=True)

if __name__=='__main__':
    mode=sys.argv[1]
    if mode=='init':init()
    else:
        configure()
        if mode=='repair':repair()
        elif mode=='source':p.source(4)
        elif mode=='medical':f.medical(4)
        elif mode=='resolve':resolve()
        elif mode=='bundle':bundle()
        elif mode=='check':check()
        else:raise SystemExit('init/repair/source/medical/resolve/bundle/check')

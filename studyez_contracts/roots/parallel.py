"""Pure progress view; no I/O, models or server imports."""
import copy
from .validate import document_hash
from studyez_contracts.learning_links.validate import require

SOURCE_FORMAT='source-assessment/2-parallel/1'


def is_v2_source(packet):
    return packet.get('sourceAssessmentFormat')in('source-assessment/2',SOURCE_FORMAT)


def validate_schema_recovery(meta,stages):
    row=meta.get('parallelSchemaRecovery')
    if row is None:return
    p=row['proof'];old=p['priorLedger'];before=old['stages']
    require(row['proofHash']==document_hash(p)and p['priorLedgerHash']==document_hash(old),'parallel recovery: changed original failure')
    require(set(before)=={'normalize','generate'}and before['normalize']['status']=='completed'
        and before['generate']['status']=='failed'and old['repairRounds']==0
        and not old.get('parallelSchemaRecovery')and not old.get('authoringRecoveries')
        and not old.get('formatRecoveries'),'parallel recovery: only initial host schema mismatch')
    require(document_hash({'input':p['packetHash'],'model':p['model'],'code':p['oldCode']})==old['identity'],'parallel recovery: wrong original runtime')
    require(p['packetHash']==meta['inputHash']and p['currentRuntimeHash']==meta['runtimeHash']
        and p['modelReplay']is False and p['reason'].strip(),'parallel recovery: changed scope/runtime')
    require(p['parallelProof']==meta['parallelAuthoring'],'parallel recovery: different independent outputs')
    require(stages['normalize']=={'name':'normalize',**before['normalize']},'parallel recovery: changed completed extraction')
    expected={**before['generate'],'name':'generate','status':'completed','outputHash':p['acceptedHash'],'briefHash':p['briefHash']}
    require(stages['generate']==expected,'parallel recovery: altered file/input/usage')


def progress_state(value,phase=None,error=None,pid=None):
    value=copy.deepcopy(value);states={}
    for kind,row in value['branches'].items():
        states[kind]={'title':value['title']+' · '+row['label'],'subject':value['subject'],
            'stage':'applied'if row['state']=='completed'else row['state'],'error':row.get('error','')}
    prior=value.get('states',{}).get('pipeline',{})
    stage=phase or prior.get('stage','queued');title=value['title']+' · 통합·검수'
    if stage=='local-ready':title+=' (격리 결과·운영 미게시)';stage='applied'
    if stage=='published':title+=' (업로드 완료)';stage='applied'
    states['pipeline']={'title':title,'subject':value['subject'],'stage':stage,'error':error or prior.get('error','')}
    value.update(states=states)
    if pid is not None:value['pid']=pid
    return value

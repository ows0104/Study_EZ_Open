"""Interrupted initial authoring: synthetic files and fake provider only."""
import copy
import json
from pathlib import Path
import sys
import pytest
import jsonschema
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'contracts'))
import generation_v2_fixture as f
from quizbank import connection_generate as g
from runner import root_authoring_resume as r, connection_generation as worker
from studyez_contracts.roots import generation_v2 as c
from studyez_contracts.roots.automation import packet_hash


@pytest.fixture
def pending(tmp_path,monkeypatch):
    out=tmp_path/'runs/_root-generation'/('a'*32);out.mkdir(parents=True)
    packet=f.packet(tmp_path/'source.txt');packet.update(inputMode='source',conceptMap='',points='')
    packet['inputHash']=packet_hash(packet);g.write(out/'packet.json',packet)
    def initial(stage,ctx,*args):
        if stage=='generate':raise TimeoutError('interrupted')
        b,info=f.model(stage,ctx,*args)
        b['prerequisites']=[{'before_target':'T1','after_target':'missing','relation_id':'R1'}]
        return b,info
    with pytest.raises(TimeoutError):g.run(packet,out,invoke=initial)
    ledger=r.read(out/'ledger.json');ctx=r.read(out/'generate.input.json')
    sid='11111111-1111-1111-1111-111111111111';work=tmp_path/'studyez-root-v2-fixture'
    events=[{'type':'session_meta','timestamp':'2026-11-05T00:00:00Z','payload':{'id':sid,'cwd':str(work)}},
        {'type':'turn_context','payload':{'model':g.codex.model_name(),'cwd':str(work),'sandbox_policy':{'type':'workspace-write','network_access':False}}},
        {'type':'response_item','payload':{'type':'message','role':'user','content':[{'text':r.prompt(ctx).replace('\n','\r\n')}]}},
        {'type':'event_msg','payload':{'type':'token_count','info':{'total_token_usage':{'input_tokens':100,'cached_input_tokens':40,'output_tokens':5}}}}]
    session=tmp_path/'rollout.jsonl';session.write_text('\n'.join(json.dumps(e)for e in events),encoding='utf-8')
    monkeypatch.setattr(r.tempfile,'gettempdir',lambda:str(tmp_path))
    monkeypatch.setattr(r,'process_check',lambda *_:{'matchingProcesses':[]})
    return out,session,packet,ledger,ctx,events,work,sid


def provider(ctx):
    def invoke(prompt,**kwargs):
        assert prompt==r.FOLLOWUP and kwargs['blind']is False
        assert kwargs['model']==g.codex.model_name() and kwargs['previous_usage']=={'input_tokens':60,'cache_read_input_tokens':40,'cache_creation_input_tokens':0,'output_tokens':5}
        b=copy.deepcopy(ctx['brief']);b['prerequisites']=[];b['provenance']['independent_points']='derived'
        value=f.author(b);value['map_change_reason']='Remove invalid missing-target prerequisite; original points and scope preserved'
        total={k:v+1 for k,v in kwargs['previous_usage'].items()}
        return {'text':json.dumps(value),'session_id':kwargs['resume'],'turns':1,'session_usage':total,
            'usage':{k:1 for k in total},'models':{g.codex.model_name():1},'cost_usd':None,'duration_ms':1}
    return invoke


def test_original_prompt_matches_actual_producer(tmp_path,monkeypatch):
    monkeypatch.setattr(r.tempfile,'gettempdir',lambda:str(tmp_path))
    material=tmp_path/'material';material.mkdir();ctx={'brief':f.brief(),'png_base64':'excluded','_pipeline_version':c.POLICY};seen=[]
    def capture(prompt,**kw):seen.append(prompt);raise TimeoutError()
    monkeypatch.setattr(g.codex,'run',capture)
    with pytest.raises(TimeoutError):g.call_model('generate',ctx,material,None)
    assert seen==[r.prompt(ctx)]


def test_continue_same_session_then_only_remaining_reviews(pending):
    out,session,packet,old,ctx,events,work,sid=pending
    preserved={p.name:p.read_bytes()for p in out.glob('*')if p.is_file()};calls=[]
    def invoke(prompt,**kw):calls.append(kw);return provider(ctx)(prompt,**kw)
    value=r.continue_session(out,session,old['identity'],sid,invoke=invoke)
    ledger=r.read(out/'ledger.json');assert len(calls)==1 and calls[0]['cwd']==work
    assert ledger['repairRounds']==1 and ledger['identity']==old['identity']
    assert ledger['stages']['generate']['continuationProof']['priorLedger']==old
    assert r.material_hashes(work/'material')==r.material_hashes(out/'material')
    for name,body in preserved.items():
        if name!='ledger.json':assert(out/name).read_bytes()==body
    assert r.read(out/'generate.continuation.json')['status']=='completed'
    with pytest.raises(ValueError):r.continue_session(out,session,old['identity'],sid,invoke=lambda *a,**k:pytest.fail('must not repeat'))
    stages=[]
    def reviews(stage,*args):stages.append(stage);return f.model(stage,*args)
    result=g.run(packet,out,invoke=reviews)
    assert stages==['source-0','medical-0'] and result['manifest']['repairRounds']==1
    c.validate_result(result,packet);assert worker.completed_result(out,packet)==result
    assert result['manifest']['initialBrief']!=value['brief']


@pytest.mark.parametrize('change',['identity','session','cache','source','material','input','ledger','prompt','model','network','outside','final','aborted','error','usage','repeat','process','workspace'])
def test_preflight_blocks_changed_or_terminal_work_before_call(pending,change):
    out,session,packet,old,ctx,events,work,sid=pending;identity=old['identity']
    if change=='identity':identity='other'
    if change=='session':sid='22222222-2222-2222-2222-222222222222'
    if change=='cache':g.write(out/'normalize.json',{})
    if change=='source':Path(packet['sources'][0]['localPath']).write_bytes(b'changed')
    if change=='material':(out/'material/S1.md').write_text('changed')
    if change=='input':g.write(out/'generate.input.json',{})
    if change=='ledger':old['repairRounds']=0;g.write(out/'ledger.json',old)
    if change=='prompt':events[2]['payload']['content'][0]['text']='changed'
    if change=='model':events[1]['payload']['model']='other'
    if change=='network':events[1]['payload']['sandbox_policy']['network_access']=True
    if change=='outside':events[0]['payload']['cwd']=str(work.parent.parent/'other')
    if change=='final':events.append({'type':'response_item','payload':{'role':'assistant','channel':'final'}})
    if change in('aborted','error'):events.append({'type':'event_msg','payload':{'type':'turn_aborted'if change=='aborted'else'error'}})
    if change=='usage':events[-1]['payload']['info']['total_token_usage']['cached_input_tokens']=200
    if change=='repeat':g.write(out/'generate.continuation.json',{'status':'started'})
    if change=='workspace':work.mkdir();(work/'unexpected').write_text('preserve')
    session.write_text('\n'.join(json.dumps(e)for e in events),encoding='utf-8')
    def process(_):
        if change=='process':raise ValueError('Original process still alive')
        return {'matchingProcesses':[]}
    before=(out/'ledger.json').read_bytes()
    with pytest.raises(ValueError):r.continue_session(out,session,identity,sid,check_process=process,invoke=lambda *a,**k:pytest.fail('must not call'))
    assert(out/'ledger.json').read_bytes()==before
    assert not(out/'generate.before-continuation.jsonl').exists()


@pytest.mark.parametrize('failure',['interrupted','session','usage','scope','schema','turns'])
def test_failed_continuation_retains_failure_and_never_repeats(pending,failure):
    out,session,packet,old,ctx,events,work,sid=pending;calls=[]
    def invoke(prompt,**kw):
        calls.append(kw)
        if failure=='interrupted':raise TimeoutError('interrupted')
        value=provider(ctx)(prompt,**kw)
        if failure=='session':value['session_id']='other'
        if failure=='usage':value['session_usage']['input_tokens']=0
        if failure=='turns':value['turns']=0
        if failure in('scope','schema'):
            raw=json.loads(value['text'])
            if failure=='scope':raw['brief']['points'][0]['text']='changed original point'
            else:raw.pop('brief')
            value['text']=json.dumps(raw)
        return value
    with pytest.raises((ValueError,TimeoutError,jsonschema.ValidationError)):
        r.continue_session(out,session,old['identity'],sid,invoke=invoke)
    assert r.read(out/'generate.continuation.json')['status']=='failed'
    with pytest.raises(ValueError):r.continue_session(out,session,old['identity'],sid,invoke=invoke)
    assert len(calls)==1 and r.read(out/'ledger.json')['repairRounds']==1
    assert r.read(out/'generate.continuation.json')['proof']['priorLedger']==old


@pytest.mark.parametrize('artifact',['journal','response','archive','tool','usage','input','raw','output','proof'])
def test_completed_proof_tampering_blocks_publication(pending,artifact):
    out,session,packet,old,ctx,events,work,sid=pending
    r.continue_session(out,session,old['identity'],sid,invoke=provider(ctx))
    entry=r.read(out/'ledger.json')['stages']['generate']
    paths={'journal':'generate.continuation.json','response':'generate.continuation-response.json','archive':'generate.before-continuation.jsonl',
        'tool':'generate.continuation-tool.py','usage':'generate.usage.json','input':'generate.input.json','raw':'generate.raw.json','output':'generate.json'}
    if artifact=='proof':entry['continuationProof']['previousPartialUsageUnknown']=False
    else:(out/paths[artifact]).write_text('{}',encoding='utf-8')
    with pytest.raises(ValueError):r.validate_cached_continuation(out,entry)


@pytest.mark.parametrize('state',['failed','canceled','running','stopped','occupied'])
def test_driver_keeps_terminal_remote_state_and_honors_stops(pending,monkeypatch,state):
    from runner import agent,cycle,publish,desktop_control,gate
    out,session,packet,old,ctx,events,work,sid=pending;requests=[];runs=[]
    class Client:
        base='https://synthetic.invalid';token='synthetic'
        def call(self,method,path,payload):
            requests.append((method,path,payload))
            return {'job':{'id':544,'subject':packet['subject'],'runId':packet['runId'],'kind':agent.BANK,'state':state if state in('canceled','running')else'failed'}}
    monkeypatch.setattr(publish,'Client',lambda *a:Client());monkeypatch.setattr(cycle,'runner_token',lambda *_:'synthetic')
    monkeypatch.setattr(desktop_control,'decision',lambda *a:'held'if state=='stopped'else'')
    def run(self,*args):
        runs.append(args);r.continue_session(out,session,old['identity'],sid,invoke=provider(ctx));return 0,[]
    monkeypatch.setattr(agent.Agent,'_run',run)
    building=out.parent.parent/packet['runId']/gate.BUILDING_FILE
    if state=='occupied':building.parent.mkdir();building.write_text('other worker')
    if state=='failed':assert r.drive(out,session,old['identity'],sid,544)==0
    else:
        with pytest.raises(ValueError):r.drive(out,session,old['identity'],sid,544)
    assert len(runs)==int(state=='failed') and all(payload=={}for _,_,payload in requests)
    if state=='occupied':assert building.read_text()=='other worker'
    else:assert not building.exists()

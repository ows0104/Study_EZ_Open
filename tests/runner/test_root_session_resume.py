"""Same-session continuation uses owned fixtures, no real model or production API."""
import copy
import json
from pathlib import Path
import shutil
import sys
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'contracts'))
import automation_fixture as f
from quizbank import connection_generate as g
from runner import root_session_resume as r
from studyez_contracts.roots.automation import packet_hash


@pytest.fixture
def pending(tmp_path):
    out=tmp_path/'runs/_root-generation'/('a'*32);out.mkdir(parents=True)
    packet=f.packet(tmp_path/'source.txt');packet.update(authoring='web',webResponse=f.web_response('a'*32))
    packet['webResponseHash']=g.document_hash(packet['webResponse']);packet['inputHash']=packet_hash(packet)
    sources=g.prepare(packet,out/'material');brief=f.brief(sources);bank=f.web_bank();bank['build_meta']['schema_version']='unsupported'
    raw=g.envelope(brief,bank,f.assessment(brief,bank))
    repaired=f.web_bank();values={'normalize':brief,'generate':bank,'source-0':g.compile_source_assessment(brief,bank,raw),'medical-0':f.checks(bank),'repair-1':repaired}
    ledger={'identity':g.identity(packet,None),'repairRounds':1,'stages':{}}
    for name,value in values.items():
        g.write(out/(name+'.json'),value);g.write(out/(name+'.usage.json'),{})
        ledger['stages'][name]={'status':'completed','outputHash':g.document_hash(value)}
    g.write(out/'source-0.raw.json',raw)
    ledger['stages']['source-0'].update(rawOutputHash=g.document_hash(raw),sourceFormat=g.SOURCE_FORMAT)
    ledger['stages']['source-1']={'status':'started'}
    g.write(out/'ledger.json',ledger);g.write(out/'packet.json',packet)
    context={k:packet[k]for k in ('title','scope','conceptMap','points','examDate')}
    context.update(lecture_id='test/demo',sources=sources,preserved_scope=g.lecture_scope(packet['title'],packet['sources']),webResponse=packet['webResponse'])
    context.update(brief=brief,bank=repaired,bank_sha256=g.document_hash(repaired),question_hashes={q['question_id']:r.question_hash(q,repaired)for q in repaired['questions']})
    work=tmp_path/'studyez-root-stage-fixture';shutil.copytree(out/'material',work/'material')
    sid='11111111-1111-1111-1111-111111111111'
    events=[{'type':'session_meta','payload':{'id':sid,'cwd':str(work)}},
        {'type':'turn_context','payload':{'model':g.codex.model_name(),'cwd':str(work),'sandbox_policy':{'type':'workspace-write','network_access':False}}},
        {'type':'response_item','payload':{'type':'message','role':'user','content':[{'text':r.source_prompt(context).replace('\n','\r\n')}]}},
        {'type':'event_msg','payload':{'type':'token_count','info':{'total_token_usage':{'input_tokens':100,'cached_input_tokens':40,'output_tokens':5}}}}]
    session=tmp_path/'rollout.jsonl';session.write_text('\n'.join(json.dumps(e)for e in events),encoding='utf-8')
    return out,session,packet,ledger,context,events,work


def test_prompt_binding_matches_real_source_call(tmp_path,monkeypatch):
    material=tmp_path/'material';material.mkdir();context={'brief':f.brief(),'bank':f.bank()};captured={}
    class Captured(Exception):pass
    def invoke(prompt,**kwargs):captured['prompt']=prompt;raise Captured()
    monkeypatch.setattr(g.codex,'run',invoke)
    with pytest.raises(Captured):g.call_model('source-1',context,material,None)
    assert captured['prompt']==r.source_prompt(context)


def test_same_session_continuation_restores_only_pending_review_without_reset(pending):
    out,session,packet,old,context,events,work=pending
    preserved={p.name:p.read_bytes()for p in out.glob('*.json')};calls=[]
    def invoke(prompt,**kwargs):
        calls.append(kwargs)
        assert kwargs['cwd']==work and kwargs['resume']==events[0]['payload']['id']
        assert kwargs['previous_usage']=={'input_tokens':60,'cache_read_input_tokens':40,'cache_creation_input_tokens':0,'output_tokens':5}
        assert kwargs['blind'] is False and kwargs['model']==g.codex.model_name()
        total={k:v+1 for k,v in kwargs['previous_usage'].items()}
        return {'text':json.dumps(f.assessment(context['brief'],context['bank'])),'session_id':kwargs['resume'],
            'session_usage':total,'usage':{k:1 for k in total},'cost_usd':None,'duration_ms':1}
    value=r.continue_session(out,session,old['identity'],invoke=invoke)
    assert len(calls)==1 and value==g.compile_source_assessment(context['brief'],context['bank'],
        g.envelope(context['brief'],context['bank'],f.assessment(context['brief'],context['bank'])))
    ledger=r.read(out/'ledger.json');assert ledger['repairRounds']==1 and ledger['identity']==old['identity']
    assert ledger['stages']['source-1']['status']=='completed' and len(ledger['continuations'])==1
    for name,body in preserved.items():
        if name!='ledger.json':assert (out/name).read_bytes()==body
    assert r.read(out/'source-1.usage.json')['continuation']['previousPartialUsageUnknown'] is True
    with pytest.raises(ValueError):r.continue_session(out,session,old['identity'],invoke=lambda *a,**k:pytest.fail('must not repeat'))
    invoked=[]
    def next_stage(stage,*args):invoked.append(stage);return f.model(stage,*args)
    result=g.run(packet,out,invoke=next_stage)
    assert invoked==['medical-1'] and result['manifest']['repairRounds']==1


@pytest.mark.parametrize('change',['identity','cache','source','material','prompt','context','model','final','aborted','usage','repeat'])
def test_continuation_refuses_unbound_or_completed_work(pending,change):
    out,session,packet,old,context,events,work=pending;expected=old['identity']
    if change=='identity':expected='other'
    if change=='cache':g.write(out/'repair-1.json',{})
    if change=='source':Path(packet['sources'][0]['localPath']).write_bytes(b'changed')
    if change=='material':(work/'material/S1.md').write_text('changed')
    if change=='prompt':events[2]['payload']['content'][0]['text']='changed '+r.source_prompt(context)
    if change=='context':
        context['bank_sha256']='0'*64;events[2]['payload']['content'][0]['text']=r.source_prompt(context)
    if change=='model':events[1]['payload']['model']='different'
    if change=='final':events.append({'type':'response_item','payload':{'type':'message','role':'assistant','channel':'final','content':[{'text':'{}'}]}})
    if change=='aborted':events.append({'type':'event_msg','payload':{'type':'turn_aborted'}})
    if change=='usage':events[-1]['payload']['info']['total_token_usage']['cached_input_tokens']=200
    if change=='repeat':g.write(out/'source-1-continuation.json',{'status':'started'})
    session.write_text('\n'.join(json.dumps(e)for e in events),encoding='utf-8')
    before=(out/'ledger.json').read_bytes()
    with pytest.raises(ValueError):r.continue_session(out,session,expected,invoke=lambda *a,**k:pytest.fail('must not call'))
    assert (out/'ledger.json').read_bytes()==before


def test_failed_continuation_preserves_unknown_status_and_cannot_repeat(pending):
    out,session,packet,old,*_=pending;calls=[]
    def fail(*a,**k):calls.append(k);raise RuntimeError('interrupted')
    before=(out/'ledger.json').read_bytes()
    with pytest.raises(RuntimeError):r.continue_session(out,session,old['identity'],invoke=fail)
    assert (out/'ledger.json').read_bytes()==before and r.read(out/'source-1-continuation.json')['status']=='failed'
    with pytest.raises(ValueError):r.continue_session(out,session,old['identity'],invoke=fail)
    assert len(calls)==1


@pytest.mark.parametrize('cancel',[False,True])
def test_driver_requeues_only_successful_uncanceled_result(pending,monkeypatch,cancel):
    from runner import agent,cycle,publish,desktop_control
    out,session,packet,old,*_=pending;packet['generationId']='f0a8f3b68e3642598f85bbf462e1dc55';g.write(out/'packet.json',packet)
    updates=[];marks=[]
    class Client:
        def call(self,*args):return {'published':False,'packet':packet}
    class Worker:
        def __init__(self,*a):pass
        def mark_building(self,job):marks.append('start')
        def clear_building(self,job):marks.append('clear')
        def _run(self,*a):return 0,[]
        def report(self,job,**fields):updates.append(fields);return {'job':{'cancelRequested':cancel}}
        stop_asked=staticmethod(agent.Agent.stop_asked)
    monkeypatch.setattr(agent,'Agent',Worker);monkeypatch.setattr(cycle,'runner_token',lambda *_:'synthetic')
    monkeypatch.setattr(publish,'Client',lambda *a:Client());monkeypatch.setattr(desktop_control,'decision',lambda *a:'')
    assert r.drive(out,session,old['identity'])==0
    assert updates[-1]['state']==('canceled' if cancel else 'queued') and marks==['start','clear']

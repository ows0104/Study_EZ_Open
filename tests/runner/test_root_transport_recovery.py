"""Explicit fixed transport accepts model files; old failed calls stay immutable."""
import copy
import json
from pathlib import Path
import pytest
import jsonschema
from test_root_authoring_resume import pending
from test_root_native_json import provider
from quizbank import connection_generate as g,connection_generate_v2 as producer
from runner import root_transport_recovery as r,root_native_json as n,root_authoring_resume as old,connection_generation as worker
from studyez_contracts.roots import generation_v2 as c


@pytest.fixture
def failed(pending):
    out,session,packet,ledger,ctx,events,work,sid=pending
    def fail(*args,**kwargs):raise TimeoutError('prior failure')
    with pytest.raises(TimeoutError):old.continue_session(out,session,ledger['identity'],sid,invoke=fail)
    return pending


def test_fixed_transport_keeps_original_failure_cache_and_allowance(failed,monkeypatch):
    out,session,packet,prior,ctx,events,work,sid=failed
    preserved={p.name:p.read_bytes()for p in out.glob('*')if p.is_file()};calls=[]
    r.recover(out,session,prior['identity'],'User explicitly requested common fix and reuse',invoke=provider(out,calls),check_process=lambda _:[])
    ledger=n.read(out/'ledger.json');assert calls==['generate']and ledger['repairRounds']==1 and ledger['identity']==prior['identity']
    entry={'name':'generate',**ledger['stages']['generate']};r.validate_recovery(out,entry);n.validate_stage(out,entry,model=g.codex.model_name())
    assert entry['transportRecovery']['proof']['priorLedger']==prior
    for name,body in preserved.items():
        if name!='ledger.json':assert(out/name).read_bytes()==body
    with pytest.raises(ValueError):r.recover(out,session,prior['identity'],'Repeat',invoke=lambda *a,**k:pytest.fail('must not repeat'),check_process=lambda _:[])
    monkeypatch.setattr(producer,'call_model',lambda *args:calls.append(args[0])or producer_fixture(*args))
    result=g.run(packet,out,invoke=n.NativeJson(out,invoke=provider(out,calls)))
    assert calls==['generate','source-0','medical-0']and result['manifest']['repairRounds']==1
    c.validate_result(result,packet);assert worker.completed_result(out,packet)==result


def producer_fixture(*args):
    import generation_v2_fixture as f
    return f.model(*args)


@pytest.mark.parametrize('problem',['identity','source','normalize','budget','old_journal','old_archive','material','original_prompt','completed_author','repeat','active_process'])
def test_fixed_execution_preflight_never_replays_changed_or_completed_work(failed,problem):
    out,session,packet,prior,ctx,events,work,sid=failed;identity=prior['identity']
    if problem=='identity':identity='changed'
    if problem=='source':Path(packet['sources'][0]['localPath']).write_text('changed')
    if problem=='normalize':g.write(out/'normalize.raw.json',{})
    if problem=='budget':prior['repairRounds']=0;g.write(out/'ledger.json',prior)
    if problem=='old_journal':g.write(out/'generate.continuation.json',{})
    if problem=='old_archive':(out/'generate.before-continuation.jsonl').write_text('changed')
    if problem=='material':(out/'material/S1.md').write_text('changed')
    if problem=='original_prompt':events[2]['payload']['content'][0]['text']='changed'
    if problem=='completed_author':events.append({'type':'response_item','payload':{'role':'assistant','channel':'final','content':[{'text':'{"bank":{},"brief":{}}'}]}})
    if problem=='repeat':g.write(out/r.JOURNAL,{'status':'failed'})
    session.write_text('\n'.join(json.dumps(e)for e in events),encoding='utf-8')
    def process(_):
        if problem=='active_process':raise ValueError('active native process')
        return []
    before=(out/'ledger.json').read_bytes()
    with pytest.raises((ValueError,KeyError,OSError)):r.recover(out,session,identity,'User request',invoke=lambda *a,**k:pytest.fail('must not call'),check_process=process)
    assert(out/'ledger.json').read_bytes()==before


def test_prior_diagnostic_minimal_final_is_not_an_authoring_result(failed):
    out,session,packet,prior,ctx,events,work,sid=failed
    events.append({'type':'response_item','payload':{'role':'assistant','channel':'final','content':[{'text':'{"ok":true}'}]}})
    session.write_text('\n'.join(json.dumps(e)for e in events),encoding='utf-8')
    r.recover(out,session,prior['identity'],'User request after diagnostic',invoke=provider(out),check_process=lambda _:[])
    assert n.read(out/r.JOURNAL)['status']=='completed'


@pytest.mark.parametrize('problem',['timeout','point_change'])
def test_failed_fixed_execution_preserves_new_evidence_and_cannot_repeat(failed,problem):
    out,session,packet,prior,ctx,events,work,sid=failed;calls=[]
    def mutate(work,result,receipt):
        path=work/'result.json';value=n.read(path);value['brief']['points'][0]['text']='Changed original point'
        path.write_text(json.dumps(value),encoding='utf-8');receipt['sha256']=n.sha(path);result['text']=json.dumps(receipt)
    def invoke(*args,**kwargs):
        calls.append(1)
        if problem=='timeout':raise TimeoutError('synthetic timeout')
        return provider(out,mutate=mutate)(*args,**kwargs)
    with pytest.raises((ValueError,TimeoutError,jsonschema.ValidationError)):r.recover(out,session,prior['identity'],'User request',invoke=invoke,check_process=lambda _:[])
    ledger=n.read(out/'ledger.json');assert ledger['repairRounds']==1 and ledger['stages']['generate']['status']=='failed'
    assert n.read(out/r.JOURNAL)['status']=='failed'and ledger['stages']['generate']['transportRecovery']['proof']['priorLedger']==prior
    with pytest.raises(ValueError):r.recover(out,session,prior['identity'],'Repeat',invoke=invoke,check_process=lambda _:[])
    assert len(calls)==1


@pytest.mark.parametrize('target',['old_artifact','retired_session','tool','journal','prior_proof','allowance'])
def test_recovery_evidence_tampering_blocks_acceptance(failed,target):
    out,session,packet,prior,ctx,events,work,sid=failed
    r.recover(out,session,prior['identity'],'User request',invoke=provider(out),check_process=lambda _:[])
    entry={'name':'generate',**n.read(out/'ledger.json')['stages']['generate']};seat=out/'.transport-recovery'
    files={'old_artifact':'old/generate.input.json','retired_session':'retired-session.jsonl','tool':'recovery.py'}
    if target in files:(seat/files[target]).write_text('{}')
    if target=='journal':g.write(out/r.JOURNAL,{})
    if target=='prior_proof':entry['transportRecovery']['proof']['normalizationReplay']=True
    if target=='allowance':
        ledger=n.read(out/'ledger.json');ledger['repairRounds']=0;g.write(out/'ledger.json',ledger)
    with pytest.raises(ValueError):r.validate_recovery(out,entry)


@pytest.mark.parametrize('state',['failed','canceled','running','stopped','occupied','cancel_after'])
def test_driver_keeps_terminal_remote_state_and_honors_cancel(failed,monkeypatch,state):
    from runner import agent,cycle,publish,desktop_control,gate
    out,session,packet,prior,ctx,events,work,sid=failed;requests=[];runs=[]
    monkeypatch.setattr(r,'processes',lambda _:[])
    class Client:
        base='https://synthetic.invalid';token='synthetic'
        def call(self,method,path,payload):
            requests.append(payload);remote=state if state in('canceled','running')else'failed'
            if state=='cancel_after'and len(requests)>1:remote='canceled'
            return {'job':{'id':544,'subject':packet['subject'],'runId':packet['runId'],'kind':agent.BANK,'state':remote}}
    monkeypatch.setattr(publish,'Client',lambda *a:Client());monkeypatch.setattr(cycle,'runner_token',lambda *_:'synthetic')
    monkeypatch.setattr(desktop_control,'decision',lambda *a:'held'if state=='stopped'else'')
    def run(self,*args):
        runs.append(args);r.recover(out,session,prior['identity'],'User request',invoke=provider(out),check_process=lambda _:[]);return 0,[]
    monkeypatch.setattr(agent.Agent,'_run',run)
    building=out.parent.parent/packet['runId']/gate.BUILDING_FILE
    if state=='occupied':building.parent.mkdir();building.write_text('other worker')
    if state in('failed','cancel_after'):
        assert r.drive(out,session,prior['identity'],'User request',544)==(0 if state=='failed'else agent.KILLED_BY_HUMAN)
    else:
        with pytest.raises(ValueError):r.drive(out,session,prior['identity'],'User request',544)
    assert len(runs)==int(state in('failed','cancel_after'))and all(v=={}for v in requests)
    if state=='occupied':assert building.read_text()=='other worker'
    else:assert not building.exists()


def test_fixed_execution_leaves_only_two_content_repairs(failed,monkeypatch):
    out,session,packet,prior,ctx,events,work,sid=failed;calls=[]
    r.recover(out,session,prior['identity'],'User request',invoke=provider(out,calls),check_process=lambda _:[])
    def gap(work,result,receipt):
        if not work.parent.name.startswith('source-'):return
        path=work/'result.json';value=n.read(path);value['direction_evidence'][0]['components'][0].update(location='missing',answer_unit_indices=[])
        path.write_text(json.dumps(value),encoding='utf-8');receipt['sha256']=n.sha(path);result['text']=json.dumps(receipt)
    monkeypatch.setattr(producer,'call_model',lambda *args:calls.append(args[0])or producer_fixture(*args))
    result=g.run(packet,out,invoke=n.NativeJson(out,invoke=provider(out,calls,gap)))
    assert result['manifest']['repairRounds']==3 and [s for s in calls if s.startswith('repair-')]==['repair-1','repair-2']
    c.validate_result(result,packet);worker.completed_result(out,packet)

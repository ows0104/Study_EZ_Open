"""Canonical alias projection, real files and a prior bounded authoring recovery."""
import copy
import json
import sys
from pathlib import Path
import pytest
import jsonschema
sys.path[:0]=[str(Path(__file__).resolve().parents[1]/'contracts'),str(Path(__file__).resolve().parents[1]/'quizbank')]
import generation_v2_fixture as f
import test_authoring_recovery as ar
from quizbank import connection_generate as g,connection_generate_v2 as producer
from runner import root_native_json as n
from runner.root_tier_recovery import recover
from studyez_contracts.roots import generation_v2 as c
from studyez_contracts.bank.authored_json import canonical_tier


def provider(out,calls,tier='Must-Know'):
    def run(prompt,**kw):
        work=kw['cwd'];stage=work.parent.name;ctx=n.read(Path(out)/(stage+'.input.json'))
        calls.append(stage);value,_=f.model(stage,ctx,work/'material',kw['model'])
        if stage=='generate':value['bank']['questions'][0].update(tier=tier,importance=5)
        g.write(work/'result.json',value)
        return {'text':json.dumps({'path':'result.json','sha256':n.sha(work/'result.json')}),
            'turns':1,'session_id':'synthetic-tier-completion','duration_ms':5,'cost_usd':None,
            'models':{kw['model']:20},'usage':{'input_tokens':100,'output_tokens':20,
                'cache_read_input_tokens':0,'cache_creation_input_tokens':0}}
    return run


def completed_rejection(tmp_path,monkeypatch,tier='Must-Know'):
    packet=f.packet(tmp_path/'source.txt');out=tmp_path/'out';calls=[]
    monkeypatch.setattr(producer,'call_model',lambda *args:f.model(*args))
    decode=n.decode_for
    monkeypatch.setattr(n,'decode_for',lambda stage,value,schema:(g.decode_optional_fields(value,schema),None))
    transport=n.NativeJson(out,invoke=provider(out,calls,tier))
    with pytest.raises(jsonschema.ValidationError):g.run(packet,out,invoke=transport)
    monkeypatch.setattr(n,'decode_for',decode);g.write(out/'packet.json',packet)
    return packet,out,calls,transport


def test_alias_is_the_existing_canonical_rule_and_preserves_every_other_field():
    raw=f.author();raw['bank']['questions'][0].update(tier='Must-Know',importance=5)
    decoded,projection=c.tier_projection(raw)
    assert canonical_tier('Must-Know')=='Essential'and canonical_tier('Critical')=='Critical'
    assert decoded['bank']['questions'][0]['importance']==raw['bank']['questions'][0]['importance']
    back=copy.deepcopy(decoded);back['bank']['questions'][0]['tier']='Must-Know';assert back==raw
    assert projection['changes']==[{'question_id':raw['bank']['questions'][0]['question_id'],'from':'Must-Know','to':'Essential'}]
    assert c.tier_projection(decoded)==(decoded,None)


def test_native_accepts_canonical_alias_with_an_explicit_original_file_projection(tmp_path,monkeypatch):
    packet=f.packet(tmp_path/'source.txt');out=tmp_path/'out';calls=[]
    monkeypatch.setattr(producer,'call_model',lambda *args:f.model(*args))
    result=g.run(packet,out,invoke=n.NativeJson(out,invoke=provider(out,calls)))
    assert result['document']['bank_snapshot']['questions'][0]['tier']=='Essential'
    assert n.read(out/'.native/generate/output.json')['bank']['questions'][0]['tier']=='Must-Know'
    assert n.read(out/'generate.raw.json')['bank']['questions'][0]['tier']=='Essential'
    assert n.read(out/'.native/generate/receipt.json')['proof']['tierProjection']['policy']==c.TIER_POLICY
    c.validate_result(result,packet);n.validate_all(out,result)


def test_completed_tier_recovery_makes_no_model_call_and_keeps_original_failure(tmp_path,monkeypatch):
    packet,out,calls,transport=completed_rejection(tmp_path,monkeypatch)
    old=n.read(out/'ledger.json');body=(out/'.native/generate/output.json').read_bytes()
    recovered=recover(packet,out,stage='generate',expected_identity=old['identity'],reason='Explicit synthetic recovery')
    assert recovered['modelCalls']==0 and calls==['normalize','generate']
    assert recovered['repairRounds']==0 and (out/'.native/generate/output.json').read_bytes()==body
    assert n.read(out/'.tier-recovery/ledger-before.json')==old
    result=g.run(packet,out,invoke=transport)
    assert calls==['normalize','generate','source-0']and result['manifest']['repairRounds']==0
    c.validate_result(result,packet);n.validate_all(out,result)
    with pytest.raises(ValueError):recover(packet,out,stage='generate',expected_identity=n.read(out/'ledger.json')['identity'],reason='Repeat')


def test_tier_recovery_chains_a_prior_structural_recovery_without_a_fourth_round(tmp_path,monkeypatch):
    actual_identity=g.identity
    monkeypatch.setattr(g,'identity',lambda *args:'a'*64)
    packet,out,calls,transport=ar.rejected(tmp_path,monkeypatch,bad_initial=True)
    ar.approve_recovery(packet,out,'brief-repair')
    decode=n.decode_for
    monkeypatch.setattr(n,'decode_for',lambda stage,value,schema:(g.decode_optional_fields(value,schema),None))
    inner=transport.invoke
    def failed_last_round(prompt,**kw):
        response=inner(prompt,**kw);stage=kw['cwd'].parent.name;p=kw['cwd']/'result.json'
        if stage in('source-1','repair-2'):
            value=n.read(p)
            if stage=='source-1':value['direction_evidence'][0]['components'][0].update(location='missing',answer_unit_indices=[])
            else:value['bank']['questions'][0].update(tier='Must-Know',importance=5)
            g.write(p,value);response['text']=json.dumps({'path':'result.json','sha256':n.sha(p)})
        return response
    transport.invoke=failed_last_round
    with pytest.raises(jsonschema.ValidationError):g.run(packet,out,invoke=transport)
    assert n.read(out/'ledger.json')['repairRounds']==3
    old_recovery=copy.deepcopy(n.read(out/'ledger.json')['authoringRecoveries'])
    monkeypatch.setattr(n,'decode_for',decode);monkeypatch.setattr(g,'identity',actual_identity)
    recovered=recover(packet,out,stage='repair-2',expected_identity='a'*64,reason='Explicit canonical alias recovery')
    assert recovered['repairRounds']==3 and recovered['modelCalls']==0
    result=g.run(packet,out,invoke=transport)
    assert calls==['normalize','generate','repair-1','source-1','repair-2','source-2']
    assert result['manifest']['repairRounds']==3 and result['manifest']['authoringRecoveries']==old_recovery
    assert result['manifest']['formatRecoveries'][0]['proof']['priorLedger']['identity']=='a'*64
    c.validate_result(result,packet);n.validate_all(out,result)
    for mistake in('budget','prior','projection','missing-review'):
        broken=copy.deepcopy(result)
        if mistake=='budget':broken['manifest']['repairRounds']=0
        elif mistake=='prior':broken['manifest']['authoringRecoveries'][0]['proof']['currentRuntimeHash']='b'*64
        elif mistake=='projection':broken['manifest']['formatRecoveries'][0]['proof']['projection']['changes']=[]
        else:broken['manifest']['stages']=[s for s in broken['manifest']['stages']if s['name']!='medical-2']
        with pytest.raises(ValueError):c.validate_result(broken,packet)


@pytest.mark.parametrize('problem',['unknown','provider','output','input','material','started','restricted'])
def test_tier_recovery_rejects_changed_or_uncompleted_data(tmp_path,monkeypatch,problem):
    packet,out,calls,_=completed_rejection(tmp_path,monkeypatch,'Critical'if problem=='unknown'else'Must-Know')
    identity=n.read(out/'ledger.json')['identity'];seat=out/'.native/generate'
    if problem=='provider':
        value=n.read(seat/'provider.json');value['turns']=0;g.write(seat/'provider.json',value)
    elif problem=='output':(seat/'work/result.json').write_text('{}')
    elif problem=='input':(seat/'work/input.json').write_text('{}')
    elif problem=='material':(seat/'work/material/S1.md').write_text('Changed')
    elif problem=='started':
        value=n.read(seat/'journal.json');value['status']='started';g.write(seat/'journal.json',value)
    elif problem=='restricted':n.remember_restriction(out,'generate','limited access to this content for safety reasons')
    with pytest.raises((ValueError,jsonschema.ValidationError)):
        recover(packet,out,stage='generate',expected_identity=identity,reason='Synthetic check')
    assert calls==['normalize','generate']and not(out/'tier.recovery.json').exists()

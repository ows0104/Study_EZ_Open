"""Completed file receipts, failed acceptance and cumulative repair boundaries."""
import copy
import json
import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'contracts'))
import generation_v2_fixture as f
from quizbank import connection_generate as g,connection_generate_v2 as producer
from quizbank.connection_authoring_recovery import recover
from runner import root_native_json as n
from studyez_contracts.roots import generation_v2 as c


def provider(out,calls,*,bad_generate=False,notes_repair=False,bad_initial=False):
    def invoke(prompt,**kw):
        work=kw['cwd'];stage=work.parent.name;ctx=n.read(Path(out)/(stage+'.input.json'))
        calls.append(stage);value,_=f.model(stage,ctx,work/'material',kw['model'])
        if bad_initial and stage=='normalize':
            value['targets'][0]['importance']['structural'].update(status='supported',evidence=[{
                'kind':'teaching_emphasis','reason':'Wrong synthetic initial axis','refs':value['targets'][0]['evidence']}])
        if bad_initial and stage=='generate':
            value['brief']['targets'][0]['importance']['structural'].update(status='insufficient',evidence=[])
            value['brief']['provenance']['independent_points']='derived'
            value['map_change_reason']='Correct initial structural classification'
        if bad_generate and stage=='generate':
            imp=value['brief']['targets'][0]['importance']['clinical']
            imp.update(status='supported',reason='Synthetic clinical need',evidence=[{
                'kind':'teaching_emphasis','reason':'Wrong axis in a synthetic completed draft',
                'refs':value['brief']['targets'][0]['evidence']}])
        if ctx.get('rejectedAuthoring'):
            value=copy.deepcopy(ctx['previousAuthoring'])
            value['brief']['targets'][0]['importance']['clinical'].update(
                status='insufficient',reason='No clinical evidence in the source',evidence=[])
            value['brief']['provenance']['independent_points']='derived'
            value['map_change_reason']='Correct unsupported clinical classification; preserve questions'
        if notes_repair and stage=='repair-1':
            value['brief']['scope']['reviewed']=['Corrected synthetic source inspection note']
            value['brief']['scope']['limitations']=['Corrected synthetic source limitation']
            value['brief']['provenance']['independent_points']='derived'
            value['map_change_reason']='Correct source inspection notes, without changing lesson boundaries'
        path=work/'result.json';g.write(path,value)
        return {'text':json.dumps({'path':'result.json','sha256':n.sha(path)}),'turns':1,
            'session_id':'synthetic-completed-native','duration_ms':5,'cost_usd':None,
            'models':{kw['model']:20},'usage':{'input_tokens':100,'output_tokens':20,
                'cache_read_input_tokens':0,'cache_creation_input_tokens':0}}
    return invoke


def rejected(tmp_path,monkeypatch,*,notes=False,bad_initial=False):
    packet=f.packet(tmp_path/'source.txt');out=tmp_path/'out';calls=[]
    def model(stage,ctx,*args):
        value,info=f.model(stage,ctx,*args)
        return value,info
    monkeypatch.setattr(producer,'call_model',model)
    transport=n.NativeJson(out,invoke=provider(out,calls,bad_generate=not notes,notes_repair=notes,bad_initial=bad_initial))
    if notes:
        preserve=c.preserve_map_inputs
        def legacy(before,after):
            preserve(before,after)
            c.require(before['scope']==after['scope'],'authoring: source point/scope preservation: scope')
        monkeypatch.setattr(c,'preserve_map_inputs',legacy)
        inner=transport.invoke
        def gap_provider(prompt,**kw):
            result=inner(prompt,**kw)
            if kw['cwd'].parent.name=='source-0':
                p=kw['cwd']/'result.json';value=n.read(p)
                value['direction_evidence'][0]['components'][0].update(location='missing',answer_unit_indices=[])
                g.write(p,value);result['text']=json.dumps({'path':'result.json','sha256':n.sha(p)})
            return result
        transport.invoke=gap_provider
    with pytest.raises(ValueError):g.run(packet,out,invoke=transport)
    if notes:monkeypatch.setattr(c,'preserve_map_inputs',preserve)
    g.write(out/'packet.json',packet)
    return packet,out,calls,transport


def approve_recovery(packet,out,mode):
    old=n.read(out/'ledger.json')
    return recover(packet,out,expected_identity=old['identity'],mode=mode,
                   reason='Explicit synthetic operator approval')


def test_rejected_completed_generate_is_repaired_once_and_all_reviews_are_real(tmp_path,monkeypatch):
    packet,out,calls,transport=rejected(tmp_path,monkeypatch)
    failed=copy.deepcopy(n.read(out/'ledger.json'));raw=(out/'generate.raw.json').read_bytes()
    proof=approve_recovery(packet,out,'brief-repair')
    assert calls==['normalize','generate']and proof['originalModelReplayed']is False
    result=g.run(packet,out,invoke=transport)
    assert calls==['normalize','generate','repair-1','source-1']
    assert result['manifest']['repairRounds']==1
    assert (out/'generate.raw.json').read_bytes()==raw
    assert n.read(out/'ledger.json')['stages']['generate']==failed['stages']['generate']
    assert result['manifest']['authoringRecoveries'][0]['proof']['priorLedger']==failed
    c.validate_result(result,packet);n.validate_all(out,result)
    assert g.run(packet,out,invoke=lambda *args:pytest.fail('No repeated calls'))==result
    for bad in ('medical-1','source-1'):
        broken=copy.deepcopy(result)
        broken['manifest']['stages']=[s for s in broken['manifest']['stages']if s['name']!=bad]
        with pytest.raises(ValueError):c.validate_result(broken,packet)


def test_completed_note_correction_rechecks_without_a_model_call_or_budget_reset(tmp_path,monkeypatch):
    packet,out,calls,transport=rejected(tmp_path,monkeypatch,notes=True)
    old=copy.deepcopy(n.read(out/'ledger.json'));before=list(calls)
    proof=approve_recovery(packet,out,'acceptance-recheck')
    assert calls==before and proof['repairRounds']==1
    result=g.run(packet,out,invoke=transport)
    assert calls==before+['source-1']and result['manifest']['repairRounds']==1
    assert result['manifest']['authoringRecoveries'][0]['proof']['priorLedger']==old
    c.validate_result(result,packet);n.validate_all(out,result)


def test_initial_correction_and_recovery_share_the_same_three_round_limit(tmp_path,monkeypatch):
    packet,out,calls,transport=rejected(tmp_path,monkeypatch,bad_initial=True)
    assert n.read(out/'ledger.json')['repairRounds']==1
    approve_recovery(packet,out,'brief-repair')
    with pytest.raises(ValueError):approve_recovery(packet,out,'brief-repair')
    inner=transport.invoke
    def required_gap(prompt,**kw):
        response=inner(prompt,**kw)
        if kw['cwd'].parent.name=='source-1':
            p=kw['cwd']/'result.json';value=n.read(p)
            value['direction_evidence'][0]['components'][0].update(location='missing',answer_unit_indices=[])
            g.write(p,value);response['text']=json.dumps({'path':'result.json','sha256':n.sha(p)})
        return response
    transport.invoke=required_gap
    result=g.run(packet,out,invoke=transport)
    assert result['manifest']['repairRounds']==3
    assert calls==['normalize','generate','repair-1','source-1','repair-2','source-2']
    assert result['manifest']['initialMapCorrection']['consumedRounds']==1
    c.validate_result(result,packet);n.validate_all(out,result)
    for mutate in ('budget','proof','failure'):
        broken=copy.deepcopy(result)
        if mutate=='budget':broken['manifest']['repairRounds']=1
        elif mutate=='proof':broken['manifest']['authoringRecoveries'][0]['proofHash']='0'*64
        else:next(s for s in broken['manifest']['stages']if s['name']=='generate')['status']='completed'
        with pytest.raises(ValueError):c.validate_result(broken,packet)


@pytest.mark.parametrize('problem',['raw','input','usage','receipt','source','started','budget','model-block','identity'])
def test_recovery_rejects_ambiguous_or_changed_evidence(tmp_path,monkeypatch,problem):
    packet,out,calls,_=rejected(tmp_path,monkeypatch)
    old=n.read(out/'ledger.json');identity=old['identity']
    if problem in('raw','input','usage'):
        p=out/('generate.'+problem+'.json');value=n.read(p);value['tampered']=True;g.write(p,value)
    elif problem=='receipt':
        p=out/'.native/generate/provider.json';value=n.read(p);value['text']='{}';g.write(p,value)
    elif problem=='source':Path(packet['sources'][0]['localPath']).write_text('Changed source')
    elif problem=='started':old['stages']['generate']['status']='started';g.write(out/'ledger.json',old)
    elif problem=='budget':old['repairRounds']=3;g.write(out/'ledger.json',old)
    elif problem=='model-block':n.remember_restriction(out,'generate','limited access to this content for safety reasons')
    else:identity='f'*64
    with pytest.raises((ValueError,KeyError)):
        recover(packet,out,expected_identity=identity,mode='brief-repair',reason='Approved synthetic check')
    assert calls==['normalize','generate']and not(out/'authoring.recovery.json').exists()


def test_only_review_notes_may_change_and_questions_cannot_change_in_structure_repair():
    before=f.author();after=copy.deepcopy(before)
    after['brief']['scope']['reviewed']=['Corrected source note'];after['brief']['provenance']['independent_points']='derived'
    c.validate_transition(before['brief'],after['brief'],'Correction of reviewed metadata')
    for key in ('label','included','excluded'):
        bad=copy.deepcopy(after);bad['brief']['scope'][key]='Changed'if key=='label'else['Changed']
        with pytest.raises(ValueError):c.validate_transition(before['brief'],bad['brief'],'Changed scope')
    rejected=copy.deepcopy(before)
    rejected['brief']['targets'][0]['importance']['clinical'].update(status='supported',evidence=[{
        'kind':'teaching_emphasis','reason':'Wrong axis','refs':rejected['brief']['targets'][0]['evidence']}])
    c.validate_recovered_authoring(rejected,after)
    after['bank']['questions'][0]['answer']='Changed answer'
    with pytest.raises(ValueError,match='completed authoring content changed'):
        c.validate_recovered_authoring(rejected,after)

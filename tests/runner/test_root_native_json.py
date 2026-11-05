"""Native file transport with real owned files and synthetic provider completions."""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import pytest
import jsonschema
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'contracts'))
import generation_v2_fixture as f
from quizbank import connection_generate as g,connection_generate_v2 as producer
from runner import root_native_json as n,connection_generation as worker


def provider(out,calls=None,mutate=None):
    def run(prompt,**kwargs):
        work=kwargs['cwd'];stage=work.parent.name;ctx=n.read(Path(out)/(stage+'.input.json'))
        assert kwargs['blind']is False and kwargs['schema']==n.RECEIPT and 'Read task.md'in prompt
        assert n.read(work/'input.json')==n.clean(ctx)and n.read(work/'acceptance.schema.json')==n.schema_for(stage,ctx)
        if calls is not None:calls.append(stage)
        value,_=f.model(stage,ctx,work/'material',kwargs['model'])
        if ctx.get('initialBriefErrors'):
            value['brief']['prerequisites']=[];value['brief']['provenance']['independent_points']='derived';value['map_change_reason']='Remove invalid synthetic prerequisite, preserving original points and scope'
        path=work/'result.json';path.write_text(json.dumps(value,ensure_ascii=False),encoding='utf-8')
        receipt={'path':'result.json','sha256':n.sha(path)}
        result={'text':json.dumps(receipt),'turns':1,'session_id':'synthetic-native','usage':{'input_tokens':100,'output_tokens':20,'cache_read_input_tokens':10,'cache_creation_input_tokens':0},
            'models':{kwargs['model']:20},'cost_usd':None,'duration_ms':5}
        if mutate:mutate(work,result,receipt)
        return result
    return run


def setup(tmp_path):
    out=tmp_path/'out';out.mkdir();packet=f.packet(tmp_path/'source.txt');sources=g.prepare(packet,out/'material')
    ctx={'brief':f.brief(sources),'initialBriefErrors':[],'_pipeline_version':'root-generation/2'}
    g.write(out/'generate.input.json',ctx);return out,packet,ctx


def test_file_transport_preserves_real_source_review_and_budget(tmp_path,monkeypatch):
    packet=f.packet(tmp_path/'source.txt');out=tmp_path/'out';calls=[];medical=[]
    def blind(stage,ctx,material,model):medical.append(copy.deepcopy(ctx));return f.model(stage,ctx,material,model)
    monkeypatch.setattr(producer,'call_model',blind)
    result=g.run(packet,out,invoke=n.NativeJson(out,invoke=provider(out,calls)))
    assert calls==['normalize','generate','source-0']and len(medical)==1 and result['manifest']['repairRounds']==0
    assert 'clinicalInput'in medical[0]and 'sourceAudit'not in medical[0]
    for stage in calls:n.check_file(stage,out/'.native'/stage/'work')
    n.validate_all(out,result);assert worker.completed_result(out,packet)==result
    assert g.run(packet,out,invoke=lambda *a:pytest.fail('must reuse completed stages'))==result


@pytest.mark.parametrize('problem',['receipt_path','receipt_hash','no_file','too_large','duplicate_key','nonfinite','turns','protected','material','schema','hardlink'])
def test_native_completion_never_accepts_unsafe_or_wrong_files(tmp_path,problem):
    out,packet,ctx=setup(tmp_path)
    def mutate(work,result,receipt):
        path=work/'result.json'
        if problem=='receipt_path':receipt['path']='../input.json'
        if problem=='receipt_hash':receipt['sha256']='0'*64
        if problem=='no_file':path.unlink()
        if problem=='too_large':path.write_bytes(b' '*(n.LIMIT+1));receipt['sha256']=n.sha(path)
        if problem=='duplicate_key':path.write_text('{"bank":{},"bank":{}}');receipt['sha256']=n.sha(path)
        if problem=='nonfinite':path.write_text('{"x":NaN}');receipt['sha256']=n.sha(path)
        if problem=='turns':result['turns']=0
        if problem=='protected':(work/'input.json').write_text('{}')
        if problem=='material':(work/'material/S1.md').write_text('changed')
        if problem=='schema':path.write_text('{}');receipt['sha256']=n.sha(path)
        if problem=='hardlink':
            path.unlink();os.link(work/'input.json',path);receipt['sha256']=n.sha(path)
        result['text']=json.dumps(receipt)
    native=n.NativeJson(out,invoke=provider(out,mutate=mutate))
    with pytest.raises((ValueError,OSError,jsonschema.ValidationError)):native('generate',ctx,out/'material',None)
    assert n.read(out/'.native/generate/journal.json')['status']=='failed'
    with pytest.raises(FileExistsError):native('generate',ctx,out/'material',None)


def test_timeout_keeps_partial_diagnostics_and_unknown_usage(tmp_path):
    out,packet,ctx=setup(tmp_path);calls=[]
    def fail(*args,**kwargs):
        calls.append(1)
        try:raise subprocess.TimeoutExpired('synthetic',1,output='{"type":"thread.started","thread_id":"synthetic"}\n{"type":"error","message":"Reconnecting..."}\n',stderr='Authorization: Bearer SECRET_VALUE access_token=SECRET_TWO sk-12345678901234')
        except subprocess.TimeoutExpired as cause:raise g.codex.SessionError('timeout')from cause
    native=n.NativeJson(out,invoke=fail)
    with pytest.raises(g.codex.SessionError):native('generate',ctx,out/'material',None)
    summary=n.read(out/'.native/generate/failure.json')
    assert summary['eventCounts']=={'thread.started':1,'error':1}and summary['partialUsageUnknown']is True
    log=(out/'.native/generate/stderr.log').read_text();assert 'SECRET_VALUE'not in log and 'SECRET_TWO'not in log and 'sk-12345678901234'not in log
    with pytest.raises(FileExistsError):native('generate',ctx,out/'material',None)
    assert len(calls)==1


@pytest.mark.parametrize('target',['provider','output','adapter','input','schema','receipt','journal','material','usage','remove_receipt'])
def test_changed_native_evidence_blocks_completed_publication(tmp_path,monkeypatch,target):
    packet=f.packet(tmp_path/'source.txt');out=tmp_path/'out';monkeypatch.setattr(producer,'call_model',f.model)
    result=g.run(packet,out,invoke=n.NativeJson(out,invoke=provider(out)))
    seat=out/'.native/generate';files={'provider':'provider.json','output':'output.json','adapter':'adapter.py','input':'work/input.json','schema':'work/acceptance.schema.json','receipt':'receipt.json','journal':'journal.json','material':'work/material/S1.md'}
    if target in files:(seat/files[target]).write_text('{}')
    else:
        usage=n.read(out/'generate.usage.json')
        if target=='remove_receipt':usage.pop('fileReceipt')
        else:usage['usage']['output_tokens']+=1
        g.write(out/'generate.usage.json',usage)
    with pytest.raises((ValueError,OSError,jsonschema.ValidationError)):worker.completed_result(out,packet)


def test_blind_medical_uses_existing_adapter_without_file_tools(tmp_path,monkeypatch):
    seen=[];ctx={'bank':f.old.bank(),'clinicalInput':{'questions':[]}}
    monkeypatch.setattr(producer,'call_model',lambda *args:seen.append(args)or({'synthetic':True},{}))
    value=n.NativeJson(tmp_path,invoke=lambda *a,**k:pytest.fail('blind stage must not use workspace file transport'))('medical-0',ctx,tmp_path,None)
    assert value==({'synthetic':True},{})and seen[0][1]is ctx and not(tmp_path/'.native').exists()


def test_real_png_bytes_match_file_review_blind_and_learning(tmp_path,monkeypatch):
    import base64,fitz
    from studyez_contracts.roots.automation import packet_hash
    packet=f.packet();path=tmp_path/'shape.pdf'
    with fitz.open()as pdf:
        page=pdf.new_page(width=240,height=240);page.draw_rect(fitz.Rect(20,20,80,80),color=(0,0,1),fill=(0,0,1));pdf.save(path)
    packet['sources'][0].update(filename=path.name,localPath=str(path),sizeBytes=path.stat().st_size,sha256=n.sha(path));packet['inputHash']=packet_hash(packet)
    out=tmp_path/'out';clinical=[]
    def blind(stage,ctx,*args):clinical.append(ctx);return f.model(stage,ctx,*args)
    monkeypatch.setattr(producer,'call_model',blind)
    result=g.run(packet,out,invoke=n.NativeJson(out,invoke=provider(out)))
    image=result['document']['bank_snapshot']['questions'][0]['stimuli'][0];body=base64.b64decode(image['png_base64'])
    assert (out/'.native/source-0/work/material'/('stimulus-'+image['sha256']+'.png')).read_bytes()==body
    assert clinical[0]['bank']['questions'][0]['stimuli'][0]==image
    n.check_file('source-0',out/'.native/source-0/work')
    n.validate_all(out,result)


def test_repair_checker_permits_producer_accepted_new_required_question(tmp_path):
    out,packet,ctx=setup(tmp_path);brief=ctx['brief']
    ctx.update(sources=brief['sources'],lecture_id=brief['lecture_id'],previousAuthoring=f.author(brief,True),webResponse=f.old.web_response(packet['generationId']))
    value=f.author(brief,True);extra=copy.deepcopy(value['bank']['questions'][-1]);extra['question_id']='Q003';extra['question']='Additional synthetic recall?';value['bank']['questions'].append(extra)
    work=tmp_path/'repair-work';work.mkdir();g.write(work/'input.json',ctx);g.write(work/'acceptance.schema.json',n.c.AUTHOR);g.write(work/'result.json',value)
    n.check_file('repair-1',work)

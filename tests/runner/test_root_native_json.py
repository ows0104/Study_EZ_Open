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


def test_failed_check_is_sent_back_once_into_the_same_session_and_stays_verifiable(tmp_path,monkeypatch):
    """26110803 source-2 claimed one relation twice; the enforced checker now catches it in the call."""
    packet=f.packet(tmp_path/'source.txt');out=tmp_path/'out';prompts=[]
    monkeypatch.setattr(producer,'call_model',lambda stage,ctx,material,model:f.model(stage,ctx,material,model))
    base=provider(out)
    def run(prompt,**kwargs):
        work=kwargs['cwd'];stage=work.parent.name;prompts.append((stage,kwargs.get('resume')))
        if kwargs.get('resume'):  # the follow-up: remove the duplicate claim in the same files
            value=n.read(work/'result.json')
            for review in value['question_reviews']:review['relations']=review['relations'][:1]
            path=work/'result.json';path.write_text(json.dumps(value,ensure_ascii=False),encoding='utf-8')
            return {'text':json.dumps({'path':'result.json','sha256':n.sha(path)}),'turns':2,'session_id':kwargs['resume'],
                    'usage':{'input_tokens':7,'output_tokens':3,'cache_read_input_tokens':0,'cache_creation_input_tokens':0},
                    'models':{kwargs['model']:3},'cost_usd':None,'duration_ms':2}
        result=base(prompt,**kwargs)
        if stage=='source-0':
            path=work/'result.json';value=n.read(path)
            review=value['question_reviews'][0];review['relations'].append({**review['relations'][0],'role':'provided','direction_ids':[]})
            path.write_text(json.dumps(value,ensure_ascii=False),encoding='utf-8')
            result['text']=json.dumps({'path':'result.json','sha256':n.sha(path)})
        return result
    native=n.NativeJson(out,invoke=run);native.followups=True
    result=g.run(packet,out,invoke=native)
    assert ('source-0','synthetic-native')in prompts and sum(1 for s,r in prompts if r)==1
    seat=out/'.native'/'source-0'
    assert (seat/'provider-followup.json').exists() and 'duplicate'in n.read(seat/'check-failure.json')['error']
    assert n.read(out/'source-0.usage.json')['usage']['input_tokens']==107
    n.validate_all(out,result)


def test_speed_path_context_stage_runs_through_native_files_and_stays_verifiable(tmp_path,monkeypatch):
    from studyez_contracts.roots.automation import packet_hash
    packet=f.packet(tmp_path/'source.txt');packet['speedStages']=True;packet['inputHash']=packet_hash(packet);out=tmp_path/'out';calls=[]
    monkeypatch.setattr(producer,'call_model',lambda stage,ctx,material,model:f.model(stage,ctx,material,model))
    base=provider(out,calls)
    def run(prompt,**kwargs):
        work=kwargs['cwd'];stage=work.parent.name
        if stage.startswith('context-'):
            calls.append(stage);path=work/'result.json'
            path.write_text(json.dumps({'clinical_context_status':'consistent','clinical_context_reason':'synthetic'}),encoding='utf-8')
            return {'text':json.dumps({'path':'result.json','sha256':n.sha(path)}),'turns':1,'session_id':'synthetic-native',
                    'usage':{'input_tokens':5,'output_tokens':2,'cache_read_input_tokens':0,'cache_creation_input_tokens':0},
                    'models':{kwargs['model']:2},'cost_usd':None,'duration_ms':3}
        return base(prompt,**kwargs)
    result=g.run(packet,out,invoke=n.NativeJson(out,invoke=run))
    assert 'context-0'in calls and result['manifest']['contextStages']is True
    n.check_file('context-0',out/'.native'/'context-0'/'work')
    n.validate_all(out,result)


def image_packet(tmp_path):
    import fitz
    from studyez_contracts.roots.automation import packet_hash
    packet=f.packet();path=tmp_path/'shape.pdf'
    with fitz.open()as pdf:
        page=pdf.new_page(width=240,height=240);page.draw_rect(fitz.Rect(20,20,80,80),color=(0,0,1),fill=(0,0,1));pdf.save(path)
    packet['sources'][0].update(filename=path.name,localPath=str(path),sizeBytes=path.stat().st_size,sha256=n.sha(path));packet['inputHash']=packet_hash(packet)
    return packet


def test_repair_input_holds_authored_questions_not_rendered_images(tmp_path,monkeypatch):
    """26110901 사슬알균 repair-1: the input bank carried the renderer's `stimuli`; a model that copies unchanged
    questions verbatim (as told) wrote them back and the authoring schema rejected the whole repair."""
    packet=image_packet(tmp_path);out=tmp_path/'out';rounds=[]
    def blind(stage,ctx,*args):return f.model(stage,ctx,*args)
    monkeypatch.setattr(producer,'call_model',blind)
    base=provider(out)
    def run(prompt,**kwargs):
        work=kwargs['cwd'];stage=work.parent.name;result=base(prompt,**kwargs)
        path=work/'result.json';value=n.read(path)
        if stage=='source-0':value['question_reviews'][0]['verdict']='wrong'  # one real finding → repair-1
        if stage.startswith('repair-'):
            rounds.append(stage);given={q['question_id']:q for q in n.read(work/'input.json')['bank']['questions']}
            for q in value['bank']['questions']:  # copy unchanged questions verbatim, as the task instructs
                if 'stimuli'in given.get(q['question_id'],{}):q['stimuli']=copy.deepcopy(given[q['question_id']]['stimuli'])
        path.write_text(json.dumps(value,ensure_ascii=False),encoding='utf-8')
        result['text']=json.dumps({'path':'result.json','sha256':n.sha(path)});return result
    result=g.run(packet,out,invoke=n.NativeJson(out,invoke=run))
    assert rounds and result['manifest']['repairRounds']>=1
    ctx=n.read(out/'repair-1.input.json')
    assert not any('stimuli'in q for q in ctx['bank']['questions']+ctx['previousAuthoring']['bank']['questions'])
    assert ctx['previousAuthoring']['visual_stimuli']  # the authored image choice still travels with the repair
    assert result['document']['bank_snapshot']['questions'][0]['stimuli']  # and the renderer still attaches it
    n.validate_all(out,result)


def test_schema_rejected_first_output_is_also_sent_back_once_into_the_same_session(tmp_path,monkeypatch):
    """26110901 repair-1: the schema check ran before the follow-up, so a schema-level error skipped it."""
    packet=f.packet(tmp_path/'source.txt');out=tmp_path/'out';prompts=[]
    monkeypatch.setattr(producer,'call_model',lambda stage,ctx,material,model:f.model(stage,ctx,material,model))
    base=provider(out)
    def run(prompt,**kwargs):
        work=kwargs['cwd'];stage=work.parent.name;prompts.append((stage,kwargs.get('resume')));path=work/'result.json'
        if kwargs.get('resume'):  # the follow-up removes the field the schema rejected
            value=n.read(path)
            for q in value['bank']['questions']:q.pop('stimuli',None)
            path.write_text(json.dumps(value,ensure_ascii=False),encoding='utf-8')
            return {'text':json.dumps({'path':'result.json','sha256':n.sha(path)}),'turns':2,'session_id':kwargs['resume'],
                    'usage':{'input_tokens':7,'output_tokens':3,'cache_read_input_tokens':0,'cache_creation_input_tokens':0},
                    'models':{kwargs['model']:3},'cost_usd':None,'duration_ms':2}
        result=base(prompt,**kwargs)
        if stage=='generate':
            value=n.read(path);value['bank']['questions'][0]['stimuli']=[{'source_id':'S1'}]
            path.write_text(json.dumps(value,ensure_ascii=False),encoding='utf-8')
            result['text']=json.dumps({'path':'result.json','sha256':n.sha(path)})
        return result
    native=n.NativeJson(out,invoke=run);native.followups=True
    result=g.run(packet,out,invoke=native)
    assert ('generate','synthetic-native')in prompts and sum(1 for s,r in prompts if r)==1
    assert 'stimuli'in n.read(out/'.native/generate/check-failure.json')['error']
    n.validate_all(out,result)

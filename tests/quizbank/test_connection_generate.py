import json
import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'contracts'))
import automation_fixture as f
from quizbank import connection_generate as g


def schema_rejection_log(path,message='uniqueItems not permitted'):
    error=json.dumps({'status':400,'error':{'code':'invalid_json_schema','param':'text.format.schema','message':message}})
    events=[{'type':'thread.started','thread_id':'synthetic'},{'type':'turn.started'},
        {'type':'error','message':error},{'type':'turn.failed','error':{'message':error}}]
    path.write_text('\n'.join(json.dumps(e)for e in events),encoding='utf-8')
    return path


def test_all_root_wire_schemas_are_closed_and_require_every_property():
    import jsonschema
    def visit(node):
        if isinstance(node,list):
            for value in node:visit(value)
        elif isinstance(node,dict):
            if node.get('type')=='object':
                assert node['additionalProperties'] is False
                assert set(node['required'])==set(node['properties'])
            assert not {'uniqueItems','minLength','maxLength'}&node.keys()
            for value in node.values():visit(value)
    for schema in (g.BRIEF_SCHEMA,g.BANK,g.AUDIT_SCHEMA,g.source_assessment_schema(f.brief(),f.bank())):
        wire=g.output_schema(schema);jsonschema.Draft202012Validator.check_schema(wire);visit(wire)
    wire=g.output_schema(g.BANK)
    assert 'learning_page' in wire['properties']['questions']['items']['required']
    assert {'type':'null'} in wire['properties']['questions']['items']['properties']['learning_page']['anyOf']
    def previous(value):
        if isinstance(value,list):return [previous(v)for v in value]
        if isinstance(value,dict):return {k:previous(v)for k,v in value.items()if k not in ('uniqueItems','minLength','maxLength')}
        return value
    assert g.output_schema(g.BRIEF_SCHEMA)==previous(g.BRIEF_SCHEMA)


def test_wire_optional_null_decodes_only_absence_and_preserves_explicit_values(tmp_path,monkeypatch):
    import copy,jsonschema
    material=tmp_path/'material';material.mkdir();value=f.bank()
    value['questions'][0]['learning_page']=None
    value['questions'][1]['learning_page']=7
    jsonschema.validate(value,g.output_schema(g.BANK))
    def run(*args,**kwargs):return {'text':json.dumps(value),'usage':{},'cost_usd':0,'duration_ms':1,'models':{}}
    monkeypatch.setattr(g.codex,'run',run)
    decoded,_=g.call_model('generate',{},material,None)
    assert 'learning_page' not in decoded['questions'][0] and decoded['questions'][1]['learning_page']==7
    assert value['questions'][0]['learning_page'] is None
    value['questions'][0]['answer']=None
    with pytest.raises(jsonschema.ValidationError):g.call_model('generate',{},material,None)
    value['questions'][0]['answer']='Synthetic answer';value['questions'][0]['learning_page']=0
    with pytest.raises(jsonschema.ValidationError):g.call_model('generate',{},material,None)
    schema={'type':'object','properties':{'nullable':{'type':['string','null']},'optional':{'type':'integer'},'required':{'type':'string'}},'required':['required']}
    assert g.decode_optional_fields({'nullable':None,'optional':None,'required':None},schema)=={'nullable':None,'required':None}


def stopped_after_brief(tmp_path):
    packet=f.packet(tmp_path/'source.txt');out=tmp_path/'job';out.mkdir()
    g.write(out/'ledger.json',{'identity':'first','repairRounds':0,'stages':{'normalize':{'status':'failed'}}})
    g.recover_schema_preflight(packet,out,schema_rejection_log(tmp_path/'first.log'),expected_identity='first')
    calls=[]
    def invoke(stage,*args):
        calls.append(stage)
        if stage=='generate':raise RuntimeError('preflight schema rejection')
        return f.model(stage,*args)
    with pytest.raises(RuntimeError):g.run(packet,out,invoke=invoke)
    return packet,out,schema_rejection_log(tmp_path/'generate.log',"required missing: Missing 'learning_page'"),calls


def test_generate_preflight_recovery_reuses_completed_brief_and_preserves_both_failures(tmp_path):
    packet,out,log,calls=stopped_after_brief(tmp_path)
    brief=(out/'normalize.json').read_bytes();usage=(out/'normalize.usage.json').read_bytes()
    old=json.loads((out/'ledger.json').read_text());first=(out/'preflight-rejection.json').read_bytes()
    proof=g.recover_generate_preflight(packet,out,log,expected_identity=old['identity'])
    assert proof['priorLedger']==old and (out/'preflight-rejection.json').read_bytes()==first
    ledger=json.loads((out/'ledger.json').read_text());assert [r['stage']for r in ledger['recoveries']]==['normalize','generate']
    assert ledger['stages']=={'normalize':old['stages']['normalize']}
    def invoke(stage,*args):calls.append(stage);return f.model(stage,*args)
    result=g.run(packet,out,invoke=invoke)
    assert calls==['normalize','generate','generate','source-0','medical-0']
    assert result['manifest']['repairRounds']==0
    assert (out/'normalize.json').read_bytes()==brief and (out/'normalize.usage.json').read_bytes()==usage
    with pytest.raises(ValueError):g.recover_generate_preflight(packet,out,log,expected_identity=g.identity(packet,None))


@pytest.mark.parametrize('change',['identity','cache','source','usage','prior-proof','rounds','started','output','wrong-error','content'])
def test_generate_recovery_never_reuses_unverified_cache_or_ambiguous_calls(tmp_path,change):
    packet,out,log,calls=stopped_after_brief(tmp_path);old=json.loads((out/'ledger.json').read_text());expected=old['identity']
    if change=='identity':expected='other'
    if change=='cache':(out/'normalize.json').write_text('{}')
    if change=='source':(tmp_path/'source.txt').write_bytes(b'changed')
    if change=='usage':(out/'normalize.usage.json').unlink()
    if change=='prior-proof':(out/'preflight-rejection.json').write_text('{}')
    if change=='rounds':old['repairRounds']=1
    if change=='started':old['stages']['generate']['status']='started'
    if change=='output':g.write(out/'generate.json',f.bank())
    if change=='wrong-error':schema_rejection_log(log)
    if change=='content':log.write_text(log.read_text()+'\n'+json.dumps({'type':'item.completed'}))
    g.write(out/'ledger.json',old);before=(out/'ledger.json').read_bytes()
    with pytest.raises((ValueError,OSError,KeyError)):g.recover_generate_preflight(packet,out,log,expected_identity=expected)
    assert (out/'ledger.json').read_bytes()==before and not (out/'preflight-generate-rejection.json').exists()


def test_root_transport_subset_keeps_full_local_constraints(tmp_path,monkeypatch):
    import copy,jsonschema
    material=tmp_path/'material';material.mkdir()
    original=copy.deepcopy(g.BRIEF_SCHEMA);captured={};value=f.brief()
    def run(prompt,**kwargs):
        captured.update(prompt=prompt,**kwargs)
        return {'text':json.dumps(value),'usage':{},'cost_usd':0,'duration_ms':1,'models':{}}
    monkeypatch.setattr(g.codex,'run',run)
    g.call_model('normalize',{},material,None)
    assert 'uniqueItems' not in json.dumps(captured['schema'])
    assert 'minLength' not in json.dumps(captured['schema'])
    assert 'uniqueItems' in captured['prompt'] and g.BRIEF_SCHEMA==original
    value['scope']['included']*=2
    with pytest.raises(jsonschema.ValidationError):g.call_model('normalize',{},material,None)
    value['scope']['included']=['']
    with pytest.raises(jsonschema.ValidationError):g.call_model('normalize',{},material,None)


def test_explicit_preflight_repair_keeps_prior_failure_and_never_resets_content_rounds(tmp_path):
    packet=f.packet(tmp_path/'source.txt');out=tmp_path/'job';out.mkdir()
    old={'identity':'old','repairRounds':0,'stages':{'normalize':{'status':'failed'}}}
    g.write(out/'ledger.json',old);log=schema_rejection_log(tmp_path/'rejected.log')
    proof=g.recover_schema_preflight(packet,out,log,expected_identity='old')
    assert proof['priorLedger']==old and (out/'preflight-rejection.log').read_bytes()==log.read_bytes()
    ledger=json.loads((out/'ledger.json').read_text());assert ledger['repairRounds']==0 and len(ledger['recoveries'])==1
    result=g.run(packet,out,invoke=f.model);assert result['manifest']['repairRounds']==0
    with pytest.raises(ValueError):g.recover_schema_preflight(packet,out,log,expected_identity=g.identity(packet,None))


@pytest.mark.parametrize('change',['identity','started','later-stage','rounds','output','content-event','network','input'])
def test_preflight_repair_refuses_any_uncertain_or_consumed_execution(tmp_path,change):
    packet=f.packet(tmp_path/'source.txt');out=tmp_path/'job';out.mkdir()
    old={'identity':'old','repairRounds':0,'stages':{'normalize':{'status':'failed'}}}
    if change=='identity':old['identity']='different'
    if change=='started':old['stages']['normalize']['status']='started'
    if change=='later-stage':old['stages']['generate']={'status':'failed'}
    if change=='rounds':old['repairRounds']=1
    if change=='output':g.write(out/'normalize.json',f.brief())
    if change=='input':packet['scope']='changed'
    g.write(out/'ledger.json',old);log=schema_rejection_log(tmp_path/'rejected.log')
    if change=='content-event':log.write_text(log.read_text()+'\n'+json.dumps({'type':'item.completed'}))
    if change=='network':log.write_text(log.read_text().replace('invalid_json_schema','network_error'))
    before=(out/'ledger.json').read_bytes()
    with pytest.raises(ValueError):g.recover_schema_preflight(packet,out,log,expected_identity='old')
    assert (out/'ledger.json').read_bytes()==before and not (out/'preflight-rejection.json').exists()


def test_pipeline_caches_complete_stages_without_second_model_call(tmp_path):
    packet=f.packet(tmp_path/'source.txt');out=tmp_path/'job';calls=[]
    def invoke(*args):calls.append(args[0]);return f.model(*args)
    result=g.run(packet,out,invoke=invoke)
    assert calls==['normalize','generate','source-0','medical-0']
    assert result['manifest']['repairRounds']==0
    assert g.run(packet,out,invoke=lambda *a:pytest.fail('must reuse'))==result
    assert not (out/'packet.json').exists()


def test_repairs_are_capped_and_resume_cannot_reset_them(tmp_path):
    packet=f.packet(tmp_path/'source.txt');calls=[]
    def invoke(stage,*rest):
        calls.append(stage);value,info=f.model(stage,*rest)
        if stage.startswith('medical-'):value['reviews'][0]['verdict']='wrong'
        return value,info
    result=g.run(packet,tmp_path/'job',invoke=invoke)
    assert result['manifest']['repairRounds']==3
    assert len([s for s in calls if s.startswith('medical-')])==4
    assert len([s for s in calls if s.startswith('repair-')])==3
    assert result['medical']['reviews'][0]['verdict']=='wrong'
    before=list(calls)
    g.run(packet,tmp_path/'job',invoke=invoke)
    assert calls==before


def test_ambiguous_failed_call_holds_instead_of_retry(tmp_path):
    packet=f.packet(tmp_path/'source.txt');calls=[]
    def interrupted(stage,*args):
        calls.append(stage)
        if stage=='generate':raise RuntimeError('process interrupted')
        return f.model(stage,*args)
    with pytest.raises(RuntimeError):g.run(packet,tmp_path/'job',invoke=interrupted)
    with pytest.raises(ValueError,match='중단/실패'):g.run(packet,tmp_path/'job',invoke=interrupted)
    assert calls==['normalize','generate']


@pytest.mark.parametrize('change',['model','input','stage','bytes','missing-ledger','missing-stage-record'])
def test_changed_identity_or_artifacts_hold(tmp_path,change):
    packet=f.packet(tmp_path/'source.txt');out=tmp_path/'job'
    g.run(packet,out,invoke=f.model)
    model=None
    if change=='model':model='another'
    if change=='input':packet['conceptMap']='different'
    if change=='stage':(out/'generate.json').write_text('{}')
    if change=='bytes':(tmp_path/'source.txt').write_bytes(b'changed')
    if change=='missing-ledger':(out/'ledger.json').unlink()
    if change=='missing-stage-record':
        ledger=json.loads((out/'ledger.json').read_text());del ledger['stages']['generate'];(out/'ledger.json').write_text(json.dumps(ledger))
    with pytest.raises(ValueError):g.run(packet,out,model=model,invoke=lambda *a:pytest.fail('must hold'))


def test_pdf_prepares_every_actual_page_and_hash(tmp_path):
    import fitz,hashlib
    path=tmp_path/'synthetic.pdf'
    pdf=fitz.open()
    for i in range(2):pdf.new_page().insert_text((50,50),f'Synthetic page {i+1}')
    pdf.save(path);pdf.close()
    packet=f.packet();s=packet['sources'][0];s.update(localPath=str(path),filename=path.name,sizeBytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    inventory=g.prepare(packet,tmp_path/'material')
    assert inventory[0]['page_count']==2
    assert len(list((tmp_path/'material').glob('*.png')))==2
    assert 'Synthetic page 2' in (tmp_path/'material/S1.md').read_text()


def test_source_model_receives_isolated_material_copy_and_canonical_quality(tmp_path,monkeypatch):
    import tempfile
    monkeypatch.setattr(tempfile,'tempdir',str(tmp_path))
    material=tmp_path/'material';material.mkdir();(material/'S1.md').write_text('Synthetic only')
    captured={}
    def run(prompt,**kwargs):
        captured.update(kwargs,prompt=prompt)
        assert kwargs['blind'] is False
        assert (kwargs['cwd']/'material/S1.md').read_text()=='Synthetic only'
        (kwargs['cwd']/'material/S1.md').write_text('only the copy changes')
        return {'text':json.dumps(f.bank()),'usage':{},'cost_usd':0,'duration_ms':1,'models':{}}
    monkeypatch.setattr(g.codex,'run',run)
    value,info=g.call_model('generate',{'brief':f.brief()},material,None)
    assert value==f.bank() and '문항 품질 원칙' in captured['prompt']
    assert (material/'S1.md').read_text()=='Synthetic only'
    assert not captured['cwd'].exists()


def test_medical_review_uses_existing_blind_helper_without_original_inputs(tmp_path,monkeypatch):
    calls=[]
    monkeypatch.setattr(g,'medical_review',lambda *a,**kw:calls.append((a,kw)) or (f.checks(f.bank()),{}))
    g.call_model('medical-0',{'bank':f.bank(),'title':'Synthetic','conceptMap':'must not be passed'},tmp_path,None)
    assert len(calls)==1 and calls[0][0]==(f.bank(),'Synthetic')


def test_web_original_is_bound_and_missing_file_never_falls_back(tmp_path):
    from studyez_contracts.roots import document_hash
    from studyez_contracts.roots.automation import packet_hash
    packet=f.packet(tmp_path/'source.txt');packet['authoring']='web'
    packet['webResponse']=f.web_response(packet['generationId']);packet['webResponseHash']=document_hash(packet['webResponse'])
    packet['inputHash']=packet_hash(packet)
    calls=[]
    def invoke(*args):calls.append(args[0]);return f.model(*args)
    result=g.run(packet,tmp_path/'job',invoke=invoke)
    assert result['manifest']['webResponseHash']==packet['webResponseHash']
    assert [q['question_id'] for q in result['document']['bank_snapshot']['questions']]==['Q001','Q002']
    del packet['webResponse']
    with pytest.raises(ValueError,match='웹 원문'):g.run(packet,tmp_path/'missing',invoke=lambda *a:pytest.fail('no fallback'))


def test_one_click_extracts_map_points_without_seeing_web_questions(tmp_path):
    from studyez_contracts.roots import document_hash
    from studyez_contracts.roots.automation import packet_hash,source_intake
    packet=f.packet(tmp_path/'source.txt');packet.update(authoring='web',inputMode='source',conceptMap='',points='')
    packet['webResponse']=f.web_response(packet['generationId']);packet['webResponseHash']=document_hash(packet['webResponse'])
    packet['inputHash']=packet_hash(packet);seen={}
    def invoke(stage,context,*args):
        seen[stage]=context
        return f.model(stage,context,*args)
    result=g.run(packet,tmp_path/'job',invoke=invoke)
    assert set(seen['normalize'])=={'title','scope','examDate','lecture_id','sources','inputMode','preserved_scope'}
    assert 'Secret answer' not in json.dumps(seen['normalize'])
    assert seen['generate']['webResponse']==packet['webResponse']
    assert result['brief']['provenance']['independent_points']=='confirmed'
    assert result['manifest']['sourceIntakeHash']==document_hash(source_intake(packet,result['brief']['sources']))


def test_source_raw_and_canonical_are_bound_and_consumer_recompiles(tmp_path):
    from studyez_contracts.roots import document_hash
    packet=f.packet(tmp_path/'source.txt');out=tmp_path/'job'
    result=g.run(packet,out,invoke=f.model)
    raw=json.loads((out/'source-0.raw.json').read_text(encoding='utf-8'))
    ledger=json.loads((out/'ledger.json').read_text(encoding='utf-8'))
    assert result['manifest']['sourceAssessment']==raw
    assert ledger['stages']['source-0']['rawOutputHash']==document_hash(raw)
    assert ledger['stages']['source-0']['outputHash']==document_hash(result['sourceAudit'])
    raw['assessment']['question_reviews'][0]['verdict']='wrong'
    (out/'source-0.raw.json').write_text(json.dumps(raw),encoding='utf-8')
    with pytest.raises(ValueError,match='지문'):g.run(packet,out,invoke=lambda *a:pytest.fail('no new review'))


@pytest.mark.parametrize('bad',['direction','roles','omitted-question','legacy-audit'])
def test_bad_source_envelope_preserves_raw_usage_and_never_spends_content_repairs(tmp_path,bad):
    import copy,jsonschema
    packet=f.packet(tmp_path/'source.txt');out=tmp_path/'job';calls=[]
    def invoke(stage,context,*rest):
        calls.append(stage);value,info=f.model(stage,context,*rest)
        if stage.startswith('source-'):
            value=copy.deepcopy(value)
            if bad=='direction':value['question_reviews'][0]['relations'][0]['direction_ids']=['D2']
            if bad=='roles':value['question_reviews'][0]['relations'].append(copy.deepcopy(value['question_reviews'][0]['relations'][0]))
            if bad=='omitted-question':value['question_reviews'].pop()
            if bad=='legacy-audit':value=f.audit(context['brief'],context['bank'])
            info={'usage':{'output_tokens':23}}
        return value,info
    with pytest.raises((ValueError,jsonschema.ValidationError)):g.run(packet,out,invoke=invoke)
    ledger=json.loads((out/'ledger.json').read_text(encoding='utf-8'))
    assert ledger['stages']['source-0']['status']=='failed' and ledger['repairRounds']==0
    assert (out/'source-0.raw.json').exists() and not (out/'source-0.json').exists()
    assert json.loads((out/'source-0.usage.json').read_text())['usage']['output_tokens']==23
    assert calls==['normalize','generate','source-0']
    with pytest.raises(ValueError,match='중단/실패'):g.run(packet,out,invoke=lambda *a:pytest.fail('must hold'))


def test_real_source_adapter_requests_input_bound_assessment_schema(tmp_path,monkeypatch):
    b=f.brief();bank=f.bank();material=tmp_path/'material';material.mkdir();captured={}
    def run(prompt,**kw):
        captured.update(prompt=prompt,**kw)
        return {'text':json.dumps(f.assessment(b,bank)),'usage':{},'cost_usd':0,'duration_ms':1,'models':{}}
    monkeypatch.setattr(g.codex,'run',run)
    value,_=g.call_model('source-0',{'brief':b,'bank':bank},material,None)
    assert value['schema_version']=='source-assessment/1'
    assert captured['schema']==g.output_schema(g.source_assessment_schema(b,bank))
    assert 'confirmed로 센다' not in captured['prompt'] and 'source-assessment/1' in captured['prompt']


def test_malformed_medical_record_is_technical_failure_not_question_repair(tmp_path):
    packet=f.packet(tmp_path/'source.txt');out=tmp_path/'job';calls=[]
    def invoke(stage,*args):
        calls.append(stage);value,info=f.model(stage,*args)
        if stage.startswith('medical-'):value['reviews'].pop()
        return value,info
    with pytest.raises(ValueError,match='missing/unknown'):g.run(packet,out,invoke=invoke)
    ledger=json.loads((out/'ledger.json').read_text(encoding='utf-8'))
    assert ledger['repairRounds']==0 and ledger['stages']['medical-0']['status']=='failed'
    assert (out/'medical-0.json').exists() and calls==['normalize','generate','source-0','medical-0']


def test_actual_source_content_findings_still_use_existing_bounded_repairs(tmp_path):
    packet=f.packet(tmp_path/'source.txt');calls=[]
    def invoke(stage,*args):
        calls.append(stage);value,info=f.model(stage,*args)
        if stage.startswith('source-'):value['question_reviews'][0]['verdict']='wrong'
        return value,info
    value=g.run(packet,tmp_path/'job',invoke=invoke)
    assert value['manifest']['repairRounds']==3
    assert len([n for n in calls if n.startswith('source-')])==4
    assert len([n for n in calls if n.startswith('repair-')])==3
    assert value['sourceAudit']['question_checks']['reviews'][0]['verdict']=='wrong'
    assert value['manifest']['sourceAssessment']['assessment']['question_reviews'][0]['verdict']=='wrong'

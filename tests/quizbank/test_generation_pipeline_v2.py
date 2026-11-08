import copy
import hashlib
import json
import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'contracts'))
import generation_v2_fixture as f
from quizbank import connection_generate as g
from studyez_contracts.roots import generation_v2 as c

def test_opt_in_recall_policy_runs_through_actual_orchestrator(tmp_path):
    from studyez_contracts.roots.recall_units import POLICY
    p=f.packet(tmp_path/'units-source.txt')
    def invoke(stage,ctx,*args):
        value,info=f.model(stage,ctx,*args)
        if stage=='normalize':value['recall_policy']=POLICY
        if stage.startswith('source-'):
            value['design_checks']=[{'question_id':q['question_id'],'verdict':'ok','reason':'Synthetic suitable recall'}for q in ctx['bank']['questions']]
        return value,info
    result=g.run(p,tmp_path/'units-out',invoke=invoke)
    assert result['brief']['recall_policy']==POLICY and result['sourceAudit']['goal_coverage']
    assert len(result['document']['tasks'])==2
    c.validate_result(result,p)

def test_real_orchestrator_uses_new_contract_and_reuses_all_stages(tmp_path):
    p=f.packet(tmp_path/'source.txt');out=tmp_path/'out';calls=[]
    def invoke(*args):calls.append(args[0]);return f.model(*args)
    result=g.run(p,out,invoke=invoke)
    assert calls==['normalize','generate','source-0','medical-0']
    assert len(result['document']['tasks'])==2 and result['manifest']['repairRounds']==0
    assert g.run(p,out,invoke=lambda *a:pytest.fail('no second model call'))==result
    c.validate_result(result,p)

def test_optional_suggestions_and_limitations_never_consume_repairs(tmp_path):
    p=f.packet(tmp_path/'source.txt');calls=[]
    def invoke(stage,*args):
        calls.append(stage);value,info=f.model(stage,*args)
        if stage.startswith('source-'):
            value['issues']=[{'issue_id':str(i),'kind':kind,'text':'Synthetic note','question_ids':[],'direction_ids':[]}for i,kind in enumerate(('optional_extension','limitation','confirmation'))]
        return value,info
    value=g.run(p,tmp_path/'out',invoke=invoke)
    assert value['manifest']['repairRounds']==0 and not any(s.startswith('repair')for s in calls)

def test_real_required_gap_consumes_one_combined_map_and_question_round(tmp_path):
    p=f.packet(tmp_path/'source.txt');calls=[]
    def invoke(stage,ctx,*args):
        calls.append(stage);value,info=f.model(stage,ctx,*args)
        if stage=='source-0':value['direction_evidence'][0]['components'][0].update(location='explanation',answer_unit_indices=[])
        if stage=='repair-1':
            value['brief']['targets'][0]['directions'][0]['cue']='Corrected synthetic cue'
            value['brief']['provenance']['independent_points']='derived';value['map_change_reason']='Actual synthetic map error corrected'
        return value,info
    result=g.run(p,tmp_path/'out',invoke=invoke)
    assert result['manifest']['repairRounds']==1 and calls.count('repair-1')==1
    assert result['manifest']['initialBrief']['targets'][0]['directions'][0]['cue']!='Corrected synthetic cue'
    assert result['manifest']['briefRevisions'][-1]['brief']==result['brief']
    assert len(result['document']['tasks'])==2

def test_three_round_limit_and_interrupted_stage_are_never_reset(tmp_path):
    p=f.packet(tmp_path/'source.txt');calls=[]
    def invoke(stage,*args):
        calls.append(stage);value,info=f.model(stage,*args)
        if stage.startswith('source-'):value['direction_evidence'][0]['components'][0].update(location='missing',answer_unit_indices=[])
        return value,info
    result=g.run(p,tmp_path/'out',invoke=invoke)
    assert result['manifest']['repairRounds']==3 and len([x for x in calls if x.startswith('repair-')])==3
    assert g.run(p,tmp_path/'out',invoke=lambda *a:pytest.fail('no repeats'))==result
    def interrupted(stage,*args):
        if stage=='generate':raise RuntimeError('Synthetic interrupted call')
        return f.model(stage,*args)
    with pytest.raises(RuntimeError):g.run(p,tmp_path/'interrupted',invoke=interrupted)
    with pytest.raises(ValueError,match='중단/실패'):g.run(p,tmp_path/'interrupted',invoke=lambda *a:pytest.fail('no retry'))

def diagram_packet(tmp_path):
    import fitz
    p=f.packet();path=tmp_path/'diagram.pdf'
    with fitz.open()as pdf:
        page=pdf.new_page(width=240,height=240);page.draw_rect(fitz.Rect(20,20,80,80),color=(0,0,1),fill=(0,0,1));pdf.save(path)
    s=p['sources'][0];s.update(filename=path.name,localPath=str(path.resolve()),sizeBytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    p['subject']='synthetic-geometry';p['runId']='unrelated-lesson';p['inputHash']=c.packet_hash(p)
    return p

def test_exact_crop_survives_real_renderer_source_medical_and_result(tmp_path):
    import base64
    p=diagram_packet(tmp_path);captured={}
    def invoke(stage,ctx,*args):
        if stage=='normalize':
            value,info=f.model(stage,ctx,*args);value['lecture_id']=p['subject']+'/'+p['runId'];return value,info
        captured[stage]=copy.deepcopy(ctx);return f.model(stage,ctx,*args)
    result=g.run(p,tmp_path/'out',invoke=invoke);bank=result['document']['bank_snapshot'];img=bank['questions'][0]['stimuli'][0]
    assert hashlib.sha256(base64.b64decode(img['png_base64'])).hexdigest()==img['sha256']
    assert captured['source-0']['bank']['questions'][0]['stimuli'][0]==img==captured['medical-0']['bank']['questions'][0]['stimuli'][0]
    assert [t['question_id']for t in result['document']['tasks']]==['Q2','Q1']
    bad=copy.deepcopy(result);bad['document']['bank_snapshot']['questions'][0]['stimuli'][0]['page']=2
    with pytest.raises(ValueError):c.validate_result(bad,p)

def test_medical_projection_excludes_history_but_keeps_both_conflicting_claims():
    from quizbank.connection_generate_v2 import medical_input
    bank=f.old.bank();bank['audit_summary']['changes']=['PRIVATE_PREVIOUS_VERDICT']
    bank['questions'][0]['exam_rationale']='PRIVATE_PREVIOUS_VERDICT'
    bank['source_conflicts']=[{'conflict_id':'C1','description':'PRIVATE_PREVIOUS_VERDICT','source_refs':[],'unresolved':True}]
    view=medical_input(bank,[{'conflict_id':'C1','facts':'Source claims A; current answer B'}])
    text=json.dumps(view)
    assert 'PRIVATE_PREVIOUS_VERDICT'not in text and 'Source claims A; current answer B'in text
    assert view['questions'][0]['answer']==bank['questions'][0]['answer']
    bank['questions'][0]['explanation']='Previous review of systems was unremarkable.'
    assert 'Previous review of systems'in medical_input(bank,[])['questions'][0]['explanation']

def test_real_medical_adapter_attaches_exact_images_with_tools_disabled(tmp_path,monkeypatch):
    from quizbank.connection_generate_v2 import call_model,medical_input
    p=diagram_packet(tmp_path)
    def invoke(stage,ctx,*args):
        value,info=f.model(stage,ctx,*args)
        if stage=='normalize':value['lecture_id']=p['subject']+'/'+p['runId']
        return value,info
    value=g.run(p,tmp_path/'out',invoke=invoke);bank=value['document']['bank_snapshot'];calls=[]
    bank['audit_summary']['changes'].append('PRIVATE_FROZEN_REVIEW_HISTORY')
    def fake(prompt,**kw):
        assert 'PRIVATE_FROZEN_REVIEW_HISTORY'not in prompt
        calls.append(kw);assert kw['blind']is True and kw['images']
        expected=bank['questions'][0]['stimuli'][0]['sha256'];assert hashlib.sha256(kw['images'][0].read_bytes()).hexdigest()==expected
        return {'text':json.dumps({**f.old.checks(bank),'pool_checks':[]}),'usage':{},'cost_usd':None,'duration_ms':1,'models':{}}
    monkeypatch.setattr(g.codex,'run',fake)
    reviewed,_=call_model('medical-0',{'bank':bank,'clinicalInput':medical_input(bank,[])},tmp_path/'out/material',None)
    assert len(calls)==1 and reviewed['counts']['ok']==2

def test_large_lecture_other_source_id_and_late_physical_page_are_supported(tmp_path):
    import fitz
    from quizbank.connection_visuals import render
    path=tmp_path/'other-source.pdf'
    with fitz.open()as pdf:
        for i in range(42):
            page=pdf.new_page(width=200,height=200)
            if i==41:page.draw_rect(fitz.Rect(120,120,170,170),color=(1,0,0),fill=(1,0,0))
        pdf.save(path)
    source={'id':'DIAGRAM_SOURCE','localPath':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
    spec={'question_id':'Q1','source_id':'DIAGRAM_SOURCE','page':42,'crop':[0.5,0.5,0.9,0.9],'reason':'Synthetic late-page diagram'}
    material=tmp_path/'material';material.mkdir();bank=render(f.old.bank(),[spec],{'sources':[source]},material)
    assert bank['questions'][0]['stimuli'][0]['page']==42 and bank['questions'][0]['stimuli'][0]['source_id']=='DIAGRAM_SOURCE'

def test_historical_review_in_clinical_prose_is_blocked_until_author_separates_it(tmp_path):
    p=f.packet(tmp_path/'source.txt');calls=[]
    def invoke(stage,*args):
        calls.append(stage);value,info=f.model(stage,*args)
        if stage=='generate':value['bank']['questions'][0]['explanation']='sourceAudit previous verdict must not bias a fresh reviewer'
        return value,info
    result=g.run(p,tmp_path/'out',invoke=invoke)
    assert result['manifest']['repairRounds']==1 and 'medical-0'not in calls and 'medical-1'in calls
    entry=next(s for s in result['manifest']['stages']if s['name']=='medical-0')
    assert entry['status']=='blocked'and entry['blockedReport']['reason']
    c.validate_result(result,p)

def test_unverified_clinical_projection_never_reaches_independent_model_or_chases_uncertainty(tmp_path):
    p=f.packet(tmp_path/'source.txt');calls=[]
    def invoke(stage,*args):
        calls.append(stage);value,info=f.model(stage,*args)
        if stage.startswith('source-'):value['clinical_context_status']='unknown'
        return value,info
    with pytest.raises(ValueError,match='입력 분리'):g.run(p,tmp_path/'out',invoke=invoke)
    assert not any(s.startswith(('medical-','repair-'))for s in calls)
    ledger=json.loads((tmp_path/'out/ledger.json').read_text(encoding='utf-8'))
    assert ledger['repairRounds']==0 and ledger['stages']['medical-0']['status']=='blocked'

def _tree_packet(path,parents):
    import json as _json
    from studyez_contracts.roots.automation import packet_hash
    p=f.packet(path)
    p['conceptMap']=_json.dumps({'schema_version':'concept-map-extract/3','title':'t','overview':'o','relations':[],'notes':[],
        'concepts':[{'concept_id':cid,'parent_id':parent,'title':'T'+cid,'core_facts':['f'],
            'source_refs':[{'source_id':'S1','pages':[1],'locator':None}]}for cid,parent in parents]})
    p['inputHash']=packet_hash(p);return p

def test_map_tree_parents_kept_by_brief_cost_no_repair(tmp_path):
    p=_tree_packet(tmp_path/'source.txt',[('A',None),('B','A'),('C','A'),('D','A')]);calls=[]
    def invoke(stage,*args):calls.append(stage);return f.model(stage,*args)
    result=g.run(p,tmp_path/'out',invoke=invoke)
    assert result['manifest']['repairRounds']==0 and not any(s.startswith('repair')for s in calls)
    assert not list((tmp_path/'out').glob('map-hierarchy-*.json'))

def test_flattened_map_tree_becomes_one_map_fix_repair(tmp_path):
    # Map nests C under B; the synthetic brief puts C directly under A.
    p=_tree_packet(tmp_path/'source.txt',[('A',None),('B','A'),('C','B'),('D','A')]);seen=[]
    def invoke(stage,ctx,*args):
        value,info=f.model(stage,ctx,*args)
        if stage=='repair-1':
            seen.extend(r['text']for r in ctx['repairReasons']if r['kind']=='map_fix')
            next(x for x in value['brief']['concepts']if x['concept_id']=='C')['parent_ids']=['B']
            value['brief']['provenance']['independent_points']='derived';value['map_change_reason']='Keep the Map parent of C'
        return value,info
    result=g.run(p,tmp_path/'out',invoke=invoke)
    assert result['manifest']['repairRounds']==1 and len(seen)==1 and 'C' in seen[0] and 'B' in seen[0]
    assert (tmp_path/'out/map-hierarchy-0.json').exists() and not (tmp_path/'out/map-hierarchy-1.json').exists()
    assert next(x for x in result['brief']['concepts']if x['concept_id']=='C')['parent_ids']==['B']
    c.validate_result(result,p)

import copy
import json
import sys
import threading
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'contracts'))
import generation_v2_fixture as f
from quizbank import connection_parallel as p, connection_generate as g
from studyez_contracts.roots.automation import packet_hash,source_intake
from studyez_contracts.roots import document_hash


def setup(tmp_path):
    packet=f.packet(tmp_path/'original.txt')
    packet.update(authoring='cli',inputMode='source',parallelAuthoring=True,conceptMap='',points='')
    packet['inputHash']=packet_hash(packet)
    out=tmp_path/'out';out.mkdir();material=out/'material'
    sources=g.prepare(packet,material)
    return packet,out,source_intake(packet,sources),material


def output(kind):
    ref={'source_id':'S1','pages':[],'locator':'Synthetic original'}
    if kind=='map':return {'schema_version':'concept-map-extract/2','title':'Synthetic','overview':'Shapes',
        'concepts':[{'concept_id':'C001','title':'Shape','core_facts':['Synthetic fact'],'source_refs':[ref]}],'relations':[],'notes':[]}
    if kind=='point':return {'schema_version':'exam-point-extract/2','title':'Synthetic',
        'points':[{'point_id':'P001','point':'Recall synthetic shape','source_refs':[ref]}],'notes':[]}
    value=f.author();return {k:value[k] for k in ('bank','visual_stimuli','clinical_conflicts')}


def test_three_jobs_overlap_and_never_receive_each_others_outputs(tmp_path):
    packet,out,ctx,material=setup(tmp_path);barrier=threading.Barrier(3);calls=[]
    def invoke(kind,context,*args):
        assert not {'bank','brief','independentMap','independentPoints','independentBank'} & set(context)
        calls.append(kind);barrier.wait(timeout=5)
        return output(kind),{'usage':{},'text':'synthetic'}
    values,proof=p.run(packet,out,ctx,material,invoke=invoke)
    assert set(calls)==set(p.KINDS) and set(values)==set(p.KINDS)
    assert max(r['startedAt']for r in proof['branches'].values()) < min(r['finishedAt']for r in proof['branches'].values())
    again,proof2=p.run(packet,out,ctx,material,invoke=lambda *a:pytest.fail('no second call'))
    assert again==values and proof2==proof


def test_failed_branch_is_retained_and_never_automatically_replayed(tmp_path):
    packet,out,ctx,material=setup(tmp_path);calls=[]
    def invoke(kind,*args):
        calls.append(kind)
        if kind=='map':raise ValueError('Synthetic failure')
        return output(kind),{'text':'synthetic','usage':{}}
    with pytest.raises(ValueError,match='Synthetic failure'):p.run(packet,out,ctx,material,invoke=invoke)
    with pytest.raises(ValueError,match='no replay'):p.run(packet,out,ctx,material,invoke=lambda *a:pytest.fail('no replay'))
    assert len(calls)==3 and p.read(out/'parallel/map/state.json')['state']=='failed'


def test_join_cannot_rewrite_answers_or_question_ids():
    bank=output('bank')['bank'];changed=copy.deepcopy(bank);changed['questions'][0]['answer']='Different'
    with pytest.raises(ValueError,match='content'):p.preserved_bank(bank,changed)
    changed=copy.deepcopy(bank);changed['questions'][0]['concept_id']='Remapped'
    p.preserved_bank(bank,changed)


@pytest.mark.parametrize('protocol',['source-assessment/2','source-assessment/2-parallel/1'])
def test_all_three_results_feed_existing_bounded_review_pipeline(tmp_path,monkeypatch,protocol):
    packet,out,ctx,material=setup(tmp_path);calls=[]
    packet['sourceAssessmentFormat']=protocol;packet['inputHash']=packet_hash(packet)
    monkeypatch.setattr(p,'model_job',lambda kind,*a:(output(kind),{'text':'synthetic','usage':{}}))
    def invoke(stage,ctx,*args):
        calls.append(stage)
        if stage=='normalize':assert 'independentMap'in ctx and 'independentPoints'in ctx and 'independentBank'not in ctx
        if stage=='generate':assert 'independentBank'in ctx
        return f.model(stage,ctx,*args)
    result=g.run(packet,out,invoke=invoke)
    assert calls==['normalize','generate','source-0','medical-0']
    assert result['manifest']['parallelAuthoring']['policy']==p.POLICY
    assert result['manifest']['repairRounds']==0


def test_runner_lists_each_branch_and_detects_dead_parent(tmp_path):
    from runner.parallel_status import register
    from runner.status_batch import collect_batches
    packet,out,ctx,material=setup(tmp_path)
    p.run(packet,out,ctx,material,invoke=lambda kind,*a:(output(kind),{'text':'synthetic'}))
    project=tmp_path;script=project/'pilot.py';script.write_text('')
    config=register(project,out,script,out/'pilot.log');status=p.read(out/'parallel-status.json');status['pid']=123
    status['states']['map']['stage']='running';p.write(out/'parallel-status.json',status)
    processes=[{'ProcessId':123,'ParentProcessId':1,'CommandLine':f'python "{script}"'}]
    boards,jobs=collect_batches(project/'runs',processes)
    assert len(boards[0]['done'])==2 and len(jobs)==1
    boards,jobs=collect_batches(project/'runs',[])
    assert not jobs and any('실행 프로세스 없음'in r['stage']for r in boards[0]['attention'])


def test_opted_in_original_image_id_survives_the_host_pipeline(tmp_path,monkeypatch):
    import fitz
    from quizbank.connection_figures import sha
    from studyez_contracts.roots import generation_v2 as c
    from runner.root_native_json import schema_for
    packet,out,ctx,material=setup(tmp_path)
    pix=fitz.Pixmap(fitz.csRGB,fitz.IRect(0,0,100,100),False);pix.clear_with(180)
    doc=fitz.open();page=doc.new_page(width=400,height=400)
    page.insert_image(fitz.Rect(50,50,250,250),stream=pix.tobytes('png'))
    source=tmp_path/'picture.pdf';doc.save(source);doc.close()
    packet['sources'][0].update(localPath=str(source),filename='picture.pdf',sizeBytes=source.stat().st_size,sha256=sha(source))
    packet['inputHash']=packet_hash(packet)
    monkeypatch.setattr(p,'model_job',lambda kind,*a:(output(kind),{'text':'synthetic','usage':{}}))
    def invoke(stage,context,*args):
        value,info=f.model(stage,context,*args)
        if stage=='generate':
            assert schema_for(stage,context)==c.PARALLEL_AUTHOR
            row=p.read(out/'material/figure-index.json')['images'][0]
            spec={k:row[k]for k in ('image_id','source_id','page','crop')}
            spec.update(question_id=value['bank']['questions'][0]['question_id'],reason='Synthetic original figure')
            value['visual_stimuli']=[spec]
        return value,info
    result=g.run(packet,out,invoke=invoke)
    assert result['manifest']['visualStimuli'][0]['image_id']
    assert result['document']['bank_snapshot']['questions'][0]['stimuli'][0]['source_sha256']==sha(source)
    assert 'image_id'not in c.AUTHOR['properties']['visual_stimuli']['items']['properties']


def test_new_protocol_needs_explicit_mode_and_unknown_protocol_never_calls_models(tmp_path):
    packet,out,ctx,material=setup(tmp_path)
    packet.update(sourceAssessmentFormat='source-assessment/2-parallel/1',parallelAuthoring=False)
    packet['inputHash']=packet_hash(packet)
    with pytest.raises(ValueError,match='명시적'):g.run(packet,out,invoke=lambda *a:pytest.fail('no model'))
    packet.update(sourceAssessmentFormat='source-assessment/unsupported',parallelAuthoring=True)
    packet['inputHash']=packet_hash(packet)
    with pytest.raises(ValueError,match='지원하지'):g.run(packet,out,invoke=lambda *a:pytest.fail('no model'))

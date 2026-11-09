import copy,json,sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'contracts'))
import generation_v2_fixture as f
from quizbank import connection_generate as g
from quizbank.connection_recovery_v2 import recover
from studyez_contracts.roots import generation_v2 as c,document_hash
from studyez_contracts.roots.automation import packet_hash

def invalid_map(b):
    b['prerequisites']=[{'before_target':'missing','after_target':'T1','relation_id':'R1'}]
    return b

def invoke(stage,ctx,*args):
    value,info=f.model(stage,ctx,*args)
    if stage=='normalize':invalid_map(value)
    if stage=='generate':
        value['brief']['prerequisites']=[];value['brief']['provenance']['independent_points']='derived'
        value['map_change_reason']='Synthetic invalid prerequisite corrected; original source scope preserved'
    return value,{'usage':{'input_tokens':100,'output_tokens':20},'models':{'gpt-6.1-sol':20},'duration_ms':2,'cost_usd':None}

def test_initial_fault_is_corrected_during_existing_first_authoring_and_counted(tmp_path):
    p=f.packet(tmp_path/'source.txt');out=tmp_path/'out';calls=[]
    def model(stage,*args):calls.append(stage);return invoke(stage,*args)
    r=g.run(p,out,invoke=model)
    assert calls==['normalize','generate','source-0','medical-0']
    assert r['manifest']['repairRounds']==1 and r['manifest']['initialMapCorrection']['errors']
    assert r['manifest']['initialBrief']['prerequisites']and not r['brief']['prerequisites']
    c.validate_result(json.loads(json.dumps(r,sort_keys=True)),p)
    assert g.run(p,out,invoke=lambda *a:pytest.fail('No replay'))==r
    for change in('cost','findings','independence'):
        bad=copy.deepcopy(r)
        if change=='cost':bad['manifest']['repairRounds']=0
        elif change=='findings':bad['manifest']['initialMapCorrection']['errors']=[]
        else:bad['brief']['provenance']['independent_points']='confirmed'
        with pytest.raises(ValueError):c.validate_result(bad,p)

def test_initial_correction_and_later_repairs_share_exactly_three_rounds(tmp_path):
    p=f.packet(tmp_path/'source.txt');calls=[]
    def model(stage,*args):
        calls.append(stage);v,info=invoke(stage,*args)
        if stage.startswith('medical-'):v['reviews'][0]['verdict']='wrong'
        return v,info
    r=g.run(p,tmp_path/'out',invoke=model)
    assert r['manifest']['repairRounds']==3 and 'repair-2'in calls and 'repair-3'not in calls and 'source-3'not in calls
    assert len(r['document']['tasks'])==1

def test_failed_initial_correction_keeps_its_consumed_round_and_never_replays(tmp_path):
    p=f.packet(tmp_path/'source.txt');out=tmp_path/'out';calls=[]
    def model(stage,*args):
        calls.append(stage)
        if stage=='generate':raise RuntimeError('Interrupted authoring')
        return invoke(stage,*args)
    with pytest.raises(RuntimeError):g.run(p,out,invoke=model)
    assert json.loads((out/'ledger.json').read_text(encoding='utf-8'))['repairRounds']==1
    with pytest.raises(ValueError):g.run(p,out,invoke=lambda *a:pytest.fail('No replay'))
    assert calls==['normalize','generate']

def failed_cache(tmp_path,monkeypatch):
    p=f.packet(tmp_path/'source.txt');p.update(inputMode='source',conceptMap='',points='');p['inputHash']=packet_hash(p);out=tmp_path/'out'
    shape=c.validate_shape
    def old_acceptance(value,schema,label):
        shape(value,schema,label)
        if label=='initial brief2':c.validate_brief(value)
    with monkeypatch.context()as m:
        m.setattr(c,'validate_shape',old_acceptance)
        with pytest.raises(ValueError):g.run(p,out,invoke=invoke)
    ledger=json.loads((out/'ledger.json').read_text(encoding='utf-8'))
    return p,out,ledger

def test_completed_failed_acceptance_reuses_exact_raw_and_preserves_old_failure(tmp_path,monkeypatch):
    p,out,old=failed_cache(tmp_path,monkeypatch);raw=(out/'normalize.raw.json').read_bytes();usage=(out/'normalize.usage.json').read_bytes()
    proof=recover(p,out,expected_identity=old['identity'],reason='Reviewed mechanical acceptance repair')
    assert proof['modelReplay']is False and proof['repairRounds']==0
    assert raw==(out/'normalize.raw.json').read_bytes()and usage==(out/'normalize.usage.json').read_bytes()
    calls=[]
    def model(stage,*args):calls.append(stage);return invoke(stage,*args)
    r=g.run(p,out,invoke=model)
    assert 'normalize'not in calls and r['manifest']['repairRounds']==1
    assert r['manifest']['normalizationRecoveries'][0]['proof']['priorLedger']==old
    from runner.connection_generation import completed_result
    assert completed_result(out,p)==r
    bad=copy.deepcopy(r);bad['manifest']['normalizationRecoveries'][0]['proof']['modelReplay']=True
    with pytest.raises(ValueError):c.validate_result(bad,p)
    with pytest.raises(ValueError):recover(p,out,expected_identity=old['identity'],reason='Do not repeat')

@pytest.mark.parametrize('tamper',['raw','usage','input','source','missing_usage','started','completed','later'])
def test_recovery_rejects_incomplete_ambiguous_or_changed_evidence(tmp_path,monkeypatch,tamper):
    p,out,old=failed_cache(tmp_path,monkeypatch)
    if tamper in('raw','usage','input'):
        target=out/('normalize.'+tamper+'.json');v=json.loads(target.read_text(encoding='utf-8'));v['changed']=True;g.write(target,v)
    elif tamper=='source':Path(p['sources'][0]['localPath']).write_bytes(b'changed source')
    elif tamper=='missing_usage':(out/'normalize.usage.json').unlink()
    else:
        if tamper=='later':old['stages']['generate']={'status':'started'}
        else:old['stages']['normalize']['status']=tamper
        g.write(out/'ledger.json',old)
    with pytest.raises((ValueError,FileNotFoundError)):recover(p,out,expected_identity=old['identity'],reason='Never invoke a model')
    assert not(out/'normalize.recovery.json').exists()


@pytest.fixture(autouse=True)
def legacy_ledgers(monkeypatch):
    """These recovery paths exist for runs recorded before the new-run policies (2026-11-09,
    docs/changes/2026-11-09-main-quiz-runner-pipeline): shared initial-correction budget, no review retry.
    New-policy runs are refused by the tools (test_run_policies)."""
    monkeypatch.setattr('quizbank.connection_generate_v2.RUN_POLICIES', [])

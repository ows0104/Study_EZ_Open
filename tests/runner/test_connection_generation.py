import copy
import io
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'contracts'))
import automation_fixture as f
from runner import connection_generation as worker
from runner import root_choices, root_evidence, root_mcq
from runner.bank_flow import execution


@pytest.fixture(autouse=True)
def no_evidence_model(monkeypatch):
    """게시 뒤 근거 보강·선지는 tests/runner/test_root_evidence_publish.py·test_root_mcq_publish.py가 따로 본다.
    여기서는 모델을 부르지 않는다."""
    calls=[]
    monkeypatch.setattr(root_evidence,'build',lambda *a,**k:calls.append(a) or None)
    monkeypatch.setattr(root_choices,'build',lambda *a,**k:None)
    monkeypatch.setattr(root_mcq,'build',lambda *a,**k:None)
    return calls


class Client:
    base='http://local.example'
    def __init__(self):self.packet=f.packet();self.calls=[];self.published=False
    def call(self,method,path,payload=None):
        self.calls.append((method,path,payload))
        if method=='GET':return {'published':self.published,'packet':{**self.packet,'sources':[{**s,'downloadUrl':'/signed/source?secret=hidden'} for s in self.packet['sources']]}}
        return {'status':'ready'}


@pytest.mark.parametrize('version',[None,'source-assessment/2'])
def test_signed_download_subprocess_publication_and_safe_saved_packet(tmp_path,monkeypatch,capsys,version):
    client=Client();requests=[];commands=[]
    if version:
        from studyez_contracts.roots.automation import packet_hash
        client.packet['sourceAssessmentFormat']=version;client.packet['inputHash']=packet_hash(client.packet)
    def download(req,**kwargs):requests.append(req);return io.BytesIO(f.BODY)
    monkeypatch.setattr(worker.urllib.request,'urlopen',download)
    def child(args,**kwargs):
        commands.append(args)
        packet=json.loads(Path(args[args.index('--packet')+1]).read_text())
        out=Path(args[args.index('--out')+1])
        if version:
            import generation_v2_fixture as f2
            from quizbank import connection_generate as g
            g.run(packet,out,invoke=f2.model)
        else:(out/'result.json').write_text(json.dumps(f.result(packet)))
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(worker,'run_forwarded',child)
    assert worker.run_generation(client,'test','demo',tmp_path,'a'*32,model='test-model')==0
    assert not requests[0].has_header('Authorization')
    assert commands[0][1:3]==['-m','runner.root_native_json'if version=='source-assessment/2'else'quizbank.connection_generate'] and commands[0][-1]=='test-model'
    packet_text=(tmp_path/'_root-generation'/('a'*32)/'packet.json').read_text()
    assert 'downloadUrl' not in packet_text and 'secret=hidden' not in packet_text
    assert client.calls[-1][0]=='PUT' and '게시 완료' in capsys.readouterr().out


@pytest.mark.parametrize('failure',['source','child','result','publication'])
def test_failure_never_prints_success_or_posts_invalid_artifacts(tmp_path,monkeypatch,capsys,failure):
    client=Client()
    monkeypatch.setattr(worker.urllib.request,'urlopen',lambda *a,**k:io.BytesIO(b'bad' if failure=='source' else f.BODY))
    def child(args,**kwargs):
        packet=json.loads(Path(args[args.index('--packet')+1]).read_text());result=f.result(packet)
        if failure=='result':result['medical']['reviews']=[]
        (Path(args[args.index('--out')+1])/'result.json').write_text(json.dumps(result))
        return SimpleNamespace(returncode=1 if failure=='child' else 0)
    monkeypatch.setattr(worker,'run_forwarded',child)
    original=client.call
    def call(method,*args):
        if method=='PUT' and failure=='publication':raise RuntimeError('lost reply')
        return original(method,*args)
    client.call=call
    if failure=='child':assert worker.run_generation(client,'test','demo',tmp_path,'a'*32)==1
    else:
        with pytest.raises((ValueError,RuntimeError)):worker.run_generation(client,'test','demo',tmp_path,'a'*32)
    if failure!='publication':assert not any(c[0]=='PUT' for c in client.calls)
    assert '게시 완료' not in capsys.readouterr().out


def test_explicit_dispatch_precedes_legacy_raw_requirements(tmp_path,monkeypatch):
    fake=SimpleNamespace(call=lambda *a:{'connectionGeneration':'a'*32})
    calls=[]
    monkeypatch.setattr(worker,'run_generation',lambda *a,**k:calls.append((a,k)) or 0)
    assert execution.run(fake,tmp_path,'test','demo','2026','2025',tmp_path)==0
    assert calls
    fake.call=lambda *a:{}
    with pytest.raises(KeyError):execution.run(fake,tmp_path,'test','demo','2026','2025',tmp_path)


def test_already_published_does_not_download_or_run(tmp_path,monkeypatch):
    client=Client();client.published=True
    monkeypatch.setattr(worker,'run_forwarded',lambda *a,**k:pytest.fail('already published'))
    assert worker.run_generation(client,'test','demo',tmp_path,'a'*32)==0

def test_parallel_status_uses_operating_runs_when_code_is_in_another_runtime(tmp_path,monkeypatch):
    from studyez_contracts.roots.automation import packet_hash
    client=Client();client.packet.update(parallelAuthoring=True,authoring='cli',inputMode='source',sourceAssessmentFormat='source-assessment/2-parallel/1')
    client.packet['inputHash']=packet_hash(client.packet)
    monkeypatch.setattr(worker.urllib.request,'urlopen',lambda *a,**k:io.BytesIO(f.BODY))
    monkeypatch.setattr(worker,'run_forwarded',lambda *a,**k:SimpleNamespace(returncode=1))
    runs=tmp_path/'runs'
    assert worker.run_generation(client,'test','demo',runs,'a'*32)==1
    config=json.loads((runs/'status-jobs'/('main-quiz-parallel-'+('a'*32)+'.json')).read_text(encoding='utf-8'))
    assert config['script']=='runner.root_native_json'and config['outputs']=='runs/_root-generation/'+('a'*32)

@pytest.mark.parametrize('tamper',[False,True])
def test_completed_pipeline_result_reuses_original_proof_without_new_model_budget(tmp_path,monkeypatch,tamper):
    import generation_v2_fixture as f2
    from quizbank import connection_generate as g
    out=tmp_path/'_root-generation'/('a'*32);out.mkdir(parents=True)
    packet=f2.packet(out/'source-0.txt');g.run(packet,out,invoke=f2.model)
    client=Client();client.packet=packet
    monkeypatch.setattr(worker,'run_forwarded',lambda *a,**k:pytest.fail('completed result must not restart'))
    if tamper:
        (out/'source-0.raw.json').write_text('{}',encoding='utf-8')
        with pytest.raises(ValueError):worker.run_generation(client,'test','demo',tmp_path,'a'*32)
        assert not any(m=='PUT'for m,_,_ in client.calls)
    else:assert worker.run_generation(client,'test','demo',tmp_path,'a'*32)==0


def test_resume_reuses_verified_frozen_copy_without_network(tmp_path,monkeypatch):
    client=Client();out=tmp_path/'_root-generation'/('a'*32);out.mkdir(parents=True)
    path=out/'source-0.txt';path.write_bytes(f.BODY)
    monkeypatch.setattr(worker.urllib.request,'urlopen',lambda *a,**k:pytest.fail('verified copy must not download'))
    calls=[]
    monkeypatch.setattr(worker,'run_forwarded',lambda *a,**k:calls.append(a)or SimpleNamespace(returncode=1))
    assert worker.run_generation(client,'test','demo',tmp_path,'a'*32)==1
    assert path.read_bytes()==f.BODY and len(calls)==1


def test_corrupt_frozen_copy_holds_without_overwrite_or_new_model(tmp_path,monkeypatch):
    client=Client();out=tmp_path/'_root-generation'/('a'*32);out.mkdir(parents=True)
    path=out/'source-0.txt';path.write_bytes(b'preserve corrupt evidence')
    monkeypatch.setattr(worker.urllib.request,'urlopen',lambda *a,**k:pytest.fail('must not replace corrupt copy'))
    monkeypatch.setattr(worker,'run_forwarded',lambda *a,**k:pytest.fail('must not run model'))
    with pytest.raises(ValueError):worker.run_generation(client,'test','demo',tmp_path,'a'*32)
    assert path.read_bytes()==b'preserve corrupt evidence'


def test_connection_reset_during_read_retries_before_any_model(tmp_path,monkeypatch):
    requests=[];monkeypatch.setattr(worker.time,'sleep',lambda *_:None)
    class Reset(io.BytesIO):
        def read(self,*args):raise ConnectionResetError('synthetic reset')
    def download(request,**kwargs):
        requests.append(request);return Reset()if len(requests)==1 else io.BytesIO(f.BODY)
    monkeypatch.setattr(worker.urllib.request,'urlopen',download)
    path=tmp_path/'source.txt'
    worker.frozen_source(path,'https://synthetic.invalid/signed',f.packet()['sources'][0])
    assert len(requests)==2 and path.read_bytes()==f.BODY
    assert all(not req.has_header('Authorization')for req in requests)
    assert not list(tmp_path.glob('*.download'))


@pytest.mark.parametrize('failure',['reset','forbidden','hash'])
def test_frozen_download_is_bounded_and_never_accepts_wrong_bytes(tmp_path,monkeypatch,failure):
    from urllib.error import HTTPError
    calls=[];monkeypatch.setattr(worker.time,'sleep',lambda *_:None)
    def download(request,**kwargs):
        calls.append(request)
        if failure=='reset':raise ConnectionResetError('synthetic reset')
        if failure=='forbidden':raise HTTPError(request.full_url,403,'synthetic forbidden',{},None)
        return io.BytesIO(b'wrong source')
    monkeypatch.setattr(worker.urllib.request,'urlopen',download)
    path=tmp_path/'source.txt'
    with pytest.raises((OSError,ValueError)):worker.frozen_source(path,'https://synthetic.invalid/signed',f.packet()['sources'][0])
    assert len(calls)==(3 if failure=='reset'else 1)
    assert not path.exists()

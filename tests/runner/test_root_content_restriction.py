"""Provider safety refusal is a terminal input hold, never a retry/fallback."""
import json
import subprocess
import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'contracts'))
import generation_v2_fixture as f
from quizbank import connection_generate as g
from runner import root_native_json as n
from test_root_native_json import provider

REFUSAL="Invalid prompt: we've limited access to this content for safety reasons. SECRET_SOURCE_FRAGMENT"


def test_refusal_is_distinct_from_timeout_and_does_not_echo_source():
    value=n.classify_error(g.codex.SessionError(REFUSAL))
    assert value['kind']=='model_content_restricted'and value['automaticRetry']is False
    assert 'SECRET_SOURCE_FRAGMENT'not in value['message']and 'MODEL_CONTENT_RESTRICTED'in value['message']
    try:raise subprocess.TimeoutExpired('synthetic',1)
    except subprocess.TimeoutExpired as cause:
        error=g.codex.SessionError('timed out');error.__cause__=cause
    assert n.classify_error(error)['kind']=='model_timeout'
    assert n.classify_error(ValueError('ordinary failure'))['message']=='ordinary failure'


@pytest.fixture
def restricted(tmp_path):
    out=tmp_path/'out';out.mkdir();packet=f.packet(tmp_path/'source.txt');g.write(out/'packet.json',packet);calls=[]
    def invoke(prompt,**kwargs):
        stage=kwargs['cwd'].parent.name;calls.append(stage)
        if stage=='generate':raise g.codex.SessionError(REFUSAL)
        return provider(out)(prompt,**kwargs)
    with pytest.raises(g.codex.SessionError):g.run(packet,out,invoke=n.NativeJson(out,invoke=invoke))
    return out,packet,calls


def test_refused_input_preserves_ledger_and_never_calls_provider_again(restricted):
    out,packet,calls=restricted;before=(out/'ledger.json').read_bytes();snapshot=n.read(out/'.native/generate/content-block.json')
    assert snapshot['proof']['classification']['kind']=='model_content_restricted'
    assert n.read(out/'.native/generate/failure.json')['classification']['kind']=='model_content_restricted'
    assert n.read(out/'ledger.json')['stages']['generate']['status']=='failed'and not(out/'result.json').exists()
    with pytest.raises(n.ContentRestricted):n.NativeJson(out,invoke=lambda *a,**k:pytest.fail('provider must never be called'))('source-0',{},out/'material',None)
    assert calls==['normalize','generate']and(out/'ledger.json').read_bytes()==before
    assert n.remember_restriction(out,'generate',REFUSAL)==snapshot


def test_cli_surfaces_safe_terminal_reason_before_generator_or_publication(restricted,monkeypatch,capsys):
    out,packet,calls=restricted
    monkeypatch.setattr(sys,'argv',['root_native_json','--packet',str(out/'packet.json'),'--out',str(out)])
    monkeypatch.setattr(g,'run',lambda *a,**k:pytest.fail('blocked input must stop before generator'))
    assert n.main()==1
    message=capsys.readouterr().out;assert 'MODEL_CONTENT_RESTRICTED'in message and 'SECRET_SOURCE_FRAGMENT'not in message


@pytest.mark.parametrize('target',['evidence','proof','input','packet','runtime'])
def test_changed_provider_block_evidence_fails_closed(restricted,target):
    out,packet,calls=restricted
    if target=='evidence':(out/'.native/generate/provider-rejection.log').write_text('changed')
    if target=='proof':
        path=out/'.native/generate/content-block.json';row=n.read(path);row['proof']['classification']['automaticRetry']=True;g.write(path,row)
    if target=='input':g.write(out/'generate.input.json',{})
    if target=='packet':packet['inputHash']='0'*64;g.write(out/'packet.json',packet)
    if target=='runtime':
        ledger=n.read(out/'ledger.json');ledger['identity']='0'*64;g.write(out/'ledger.json',ledger)
    with pytest.raises(ValueError)as error:n.require_unblocked(out)
    assert not isinstance(error.value,n.ContentRestricted)


def test_no_clinical_publication_can_bypass_a_preserved_refusal(restricted):
    out,packet,calls=restricted
    with pytest.raises(n.ContentRestricted):n.validate_all(out,{'manifest':{'stages':[]}})
    with pytest.raises(ValueError):n.remember_restriction(out,'generate',n.RESTRICTED_MESSAGE)

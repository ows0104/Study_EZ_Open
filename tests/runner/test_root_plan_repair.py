import copy,json,sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'contracts'))
import generation_v2_fixture as f
from runner import root_plan_repair as r,root_native_json as n

def test_real_file_receipt_changes_only_one_missing_row_and_consumes_last_attempt(tmp_path):
    author=f.author();row=author['bank']['retrieval_plan'].pop(0);before=copy.deepcopy(author)
    def provider(prompt,**kwargs):
        work=kwargs['cwd'];state=n.read(work.parent/'state.json')
        assert state['status']=='started'and state['consumed']=={'before':2,'after':3,'maximum':3}
        (work/'result.json').write_text(json.dumps(row),encoding='utf-8')
        return {'text':json.dumps({'path':'result.json','sha256':n.sha(work/'result.json')}),'turns':1,'session_id':'synthetic',
            'usage':{},'duration_ms':1,'models':{},'cost_usd':None}
    (tmp_path/'plan-final').mkdir()
    value,receipt=r.repair(tmp_path,author,provider)
    assert value==row and receipt['status']=='completed'and author==before
    with pytest.raises(ValueError,match='already consumed'):r.repair(tmp_path,author,lambda *a:pytest.fail('No retry'))

def test_interrupted_last_attempt_is_preserved_and_never_automatically_repeated(tmp_path):
    author=f.author();author['bank']['retrieval_plan'].pop(0);(tmp_path/'plan-final').mkdir()
    with pytest.raises(RuntimeError):r.repair(tmp_path,author,lambda *a,**k:(_ for _ in()).throw(RuntimeError('interrupted')))
    state=n.read(tmp_path/'plan-final/repair/state.json')
    assert state['status']=='failed'and state['consumed']['after']==3 and state['automaticRetry']is False
    with pytest.raises(ValueError,match='already consumed'):r.repair(tmp_path,author,lambda *a:pytest.fail('No retry'))

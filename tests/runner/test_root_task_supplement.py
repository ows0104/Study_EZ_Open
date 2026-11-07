import json,sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'contracts'))
import task_supplement_fixture as f
from runner import root_task_supplement as r,root_native_json as n
from quizbank.connection_generate import write


def setup(out):
    base,p,s,m=f.fixture();write(out/'parent-result.json',base);write(out/'capture.json',{'runtime':{}})
    write(out/'status.json',{'pid':0,'states':{k:{'stage':'queued'}for k in ('author','source','medical')}})
    (out/'material').mkdir();(out/'material/synthetic.txt').write_text('Synthetic untrusted source')
    return p,{'stage':'author','parentPath':str(out/'parent-result.json'),'replacementRound':0}


def test_real_receipt(tmp_path):
    p,inp=setup(tmp_path)
    def provider(kind,work,context,schema):
        assert n.read(work.parent/'state.json')['status']=='started'
        write(work/'result.json',p)
        return {'text':json.dumps({'path':'result.json','sha256':n.sha(work/'result.json')}),'turns':1,'session_id':'synthetic-test-only'}
    output,proof=r.run_stage(tmp_path,'author-0',inp,'Synthetic formatting task',invoke=provider)
    assert output==p and proof['status']=='completed'
    with pytest.raises(ValueError,match='no automatic replay'):r.run_stage(tmp_path,'author-0',inp,'Synthetic',invoke=lambda *a:pytest.fail('replay'))


def test_no_replay(tmp_path):
    p,inp=setup(tmp_path)
    with pytest.raises(RuntimeError):r.run_stage(tmp_path,'author-0',inp,'Synthetic',invoke=lambda *a:(_ for _ in()).throw(RuntimeError('interrupted')))
    assert n.read(tmp_path/'author-0/state.json')['status']=='failed'
    with pytest.raises(ValueError,match='no automatic replay'):r.run_stage(tmp_path,'author-0',inp,'Synthetic',invoke=lambda *a:pytest.fail('replay'))


def test_input_tamper(tmp_path):
    p,inp=setup(tmp_path)
    def provider(kind,work,context,schema):
        write(work/'input.json',{'forged':True});write(work/'result.json',p)
        return {'text':json.dumps({'path':'result.json','sha256':n.sha(work/'result.json')}),'turns':1,'session_id':'synthetic-test-only'}
    with pytest.raises(ValueError,match='protected evidence'):r.run_stage(tmp_path,'author-0',inp,'Synthetic',invoke=provider)

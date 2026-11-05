import json
from pathlib import Path
import pytest
from quizbank import organize
from studyez_contracts.bank.schema import schema_errors


def test_json_conversion_never_calls_the_model_and_preserves_evidence(tmp_path,monkeypatch):
    raw=(Path(__file__).parents[1]/'fixtures/bank-file-valid.json').read_text(encoding='utf-8')
    def forbidden(*a,**kw): raise AssertionError('Model called for JSON conversion')
    monkeypatch.setattr(organize.session,'run_structured',forbidden)
    bank,info=organize.organize(raw,{'title':'Synthetic','sources':[],'prompt_version':'1.80'},out=tmp_path)
    assert info['conversion']=='authored-json/2' and info['cost_usd']==0
    assert schema_errors(bank)==[]
    evidence=json.loads((tmp_path/'authored-evidence.json').read_text(encoding='utf-8'))
    assert set(evidence)=={q['question_id']for q in bank['questions']}
    assert evidence['Q006']['evidence']['mode']=='linked'
    with pytest.raises(ValueError): organize.organize(raw,{'title':'Synthetic','prompt_version':'1.81'})
    with pytest.raises(ValueError): organize.organize(raw+'truncated',{'title':'Synthetic'})
    with pytest.raises(ValueError): organize.organize('```json\n'+raw+'\n```',{'title':'Synthetic','prompt_version':'1.80'})

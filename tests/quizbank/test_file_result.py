import json

import pytest

from quizbank import file_result
from quizbank.session import SessionError

SCHEMA = {'type':'object','properties':{'items':{'type':'array','items':{'type':'string'}}},
          'required':['items'],'additionalProperties':False}


def test_full_file_is_validated_with_only_a_small_acknowledgment(tmp_path, monkeypatch):
    result={'items':['판단 근거'] * 100}
    def call(prompt, schema, work, model, label):
        assert schema==file_result.WRITTEN and '다시 출력하지 않고' in prompt
        assert json.loads((work/'report.schema.json').read_text())==SCHEMA
        (work/'report.json').write_text(json.dumps(result,ensure_ascii=False),encoding='utf-8')
        return {'written':True},{'output_tokens':7}
    monkeypatch.setattr(file_result,'_call',call)
    output,usage=file_result.write('검수',SCHEMA,tmp_path,None,'검수','report.json')
    assert output==result and usage['output_tokens']==7


@pytest.mark.parametrize('response',[None,'{','{"items":[1]}'])
def test_missing_truncated_or_wrong_schema_results_cannot_use_stale_files(tmp_path,monkeypatch,response):
    (tmp_path/'report.json').write_text('{"items":["지난 결과"]}',encoding='utf-8')
    def call(*args):
        assert not (tmp_path/'report.json').exists()
        if response is not None:(tmp_path/'report.json').write_text(response,encoding='utf-8')
        return {'written':True},{}
    monkeypatch.setattr(file_result,'_call',call)
    with pytest.raises(SessionError,match='결과 파일'):
        file_result.write('검수',SCHEMA,tmp_path,None,'검수','report.json')

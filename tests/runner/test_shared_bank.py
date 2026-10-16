import pytest
from runner import preview, shared_bank


RAW = '### Q001 | basic | Core | 5 | 2 | direct\n문제: 질문\n정답: ["답"]\n' + '출제근거: 원본\n' * 20 + '\nSTUDYEZ_BANK_COMPLETE'


def turns(raw=RAW, run='260929_03'):
    return [preview.Turn('user', f'S1 [{run}] lecture.pdf'), preview.Turn('assistant', raw)]


@pytest.mark.parametrize('prefix', ['If you want, I can:', '원하시면 다음을 도와드릴 수 있습니다.'])
def test_only_ui_suggestion_tail_is_removed(prefix):
    assert shared_bank.extract(turns(RAW + '\n\n---\n\n' + prefix + '\n\n- Summarize this conversation'), '260929_03') == RAW


@pytest.mark.parametrize('raw', [RAW.replace('STUDYEZ_BANK_COMPLETE',''), RAW+'\n새 문항 본문', RAW+'\nSTUDYEZ_BANK_COMPLETE', RAW.replace('STUDYEZ_BANK_COMPLETE','### Q001 | basic | Core | 5 | 2 | direct\nSTUDYEZ_BANK_COMPLETE')])
def test_incomplete_duplicate_or_trailing_content_is_rejected(raw):
    with pytest.raises(ValueError): shared_bank.extract(turns(raw), '260929_03')


def test_wrong_lecture_and_untrusted_url_are_rejected_before_network(monkeypatch):
    with pytest.raises(ValueError): shared_bank.extract(turns(run='other'), '260929_03')
    for url in ['http://chatgpt.com/share/abc','https://chatgpt.com.evil/share/abc','https://chatgpt.com/c/abc','https://chatgpt.com/share/abc?redirect=evil']:
        with pytest.raises(ValueError): shared_bank.fetch(url,'260929_03')


def test_bank_reader_can_preserve_turns_larger_than_preview_cap():
    text='x' * 50000 + '\nSTUDYEZ_BANK_COMPLETE'
    out=[]
    preview._walk({'role':'assistant','text':text},out,shared_bank.MAX_CHARS+1)
    assert out[0].text == text
    legacy=[]
    preview._walk({'role':'assistant','text':text},legacy)
    assert len(legacy[0].text)==preview.MAX_TURN_CHARS


def test_hydrated_complete_message_and_exact_stream_chunks_are_not_duplicated():
    first=RAW.split('STUDYEZ_BANK_COMPLETE')[0].strip()
    transcript=turns(first)+[preview.Turn('assistant',RAW),preview.Turn('assistant',first)]
    assert shared_bank.extract(transcript,'260929_03')==RAW


def test_stream_chunk_with_conflicting_question_is_rejected():
    transcript=turns(RAW)+[preview.Turn('assistant',RAW.replace('질문','다른 질문'))]
    with pytest.raises(ValueError): shared_bank.extract(transcript,'260929_03')


def test_codeblock_rendering_wrapper_is_not_part_of_authored_answer():
    assert shared_bank.extract(turns('<CodeBlock language="markdown">'+RAW+'</CodeBlock>'),'260929_03')==RAW


def test_legacy_question_table_counts_only_the_primary_questions():
    raw='## 3. Question Bank\n### 3.1 Questions\n| question_id | question |\n| --- | --- |\n| Q001 | '+('내용 '*70)+' |\n### 3.2 Choice Details\n| Q001 | 보기 |\nSTUDYEZ_BANK_COMPLETE'
    assert shared_bank.question_ids(shared_bank.extract(turns(raw),'260929_03'))==['Q001']


def test_same_published_response_does_not_restart_postprocessing(monkeypatch):
    monkeypatch.setattr(shared_bank,'fetch',lambda *a:(RAW,'fixture'))
    class Client:
        calls=[]
        def call(self, method, path, data=None):
            self.calls.append((method,path,data))
            assert method=='PUT'
            return {'reused':True}
    c=Client()
    result=shared_bank.recover(c,'/test','260929_03',{'raw':RAW,'shareUrl':'https://chatgpt.com/share/test','respondedAt':'now','publishedCurrent':True},force=True)
    assert result['shareUnchanged'] and len(c.calls)==1


def test_published_complete_answer_inside_saved_stream_transcript_is_reused(monkeypatch):
    monkeypatch.setattr(shared_bank,'fetch',lambda *a:(RAW,'fixture'))
    saved='진행 안내\n\n'+RAW+'\n\n'+RAW[-80:]
    class Client:
        def call(self,method,path,data=None):
            assert method=='PUT' and data['raw']==saved
            return {'reused':True}
    assert shared_bank.recover(Client(),'/test','260929_03',{'raw':saved,'shareUrl':'https://chatgpt.com/share/test','respondedAt':'now','publishedCurrent':True},force=True)['shareUnchanged']

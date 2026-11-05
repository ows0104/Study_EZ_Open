"""Synthetic invariant checks; no clinical authoring, network or real model."""
import json,sys
from pathlib import Path
from types import SimpleNamespace
import fitz,jsonschema,pytest
sys.path.insert(0,str(Path(__file__).resolve().parent))
import visual_support as v

def test_exact_authored_crop_and_bad_bounds_are_not_silently_fixed(tmp_path):
    source=tmp_path/'synthetic.pdf'
    with fitz.open()as pdf:
        page=pdf.new_page(width=100,height=100);page.draw_rect(fitz.Rect(0,0,50,50));pdf.save(source)
    out=tmp_path/'out';(out/'material').mkdir(parents=True)
    packet={'sources':[{'id':'S1','localPath':str(source),'sha256':v.digest(source)}]}
    row={'question_id':'A','source_id':'S1','page':1,'crop':[0,0,.5,.5],'reason':'Synthetic rectangle only'}
    jsonschema.validate(row,v.STIMULUS)
    record=v.render([row],{'questions':[{'question_id':'A'}]},packet,out,1)[0]
    assert record['width']==record['height']==100
    assert record['imageSha256']==v.digest(out/'material'/record['imageFile'])
    with pytest.raises(ValueError,match='overwrite'):v.render([row],{'questions':[{'question_id':'A'}]},packet,out,1)
    with pytest.raises(ValueError,match='Invalid authored'):v.render([{**row,'crop':[.5,0,.1,.5]}],{'questions':[{'question_id':'A'}]},packet,out,2)

def test_blind_question_images_are_attached_with_tools_disabled(tmp_path,monkeypatch):
    img=tmp_path/'A.png';img.write_bytes(b'synthetic image bytes');captured={}
    monkeypatch.setattr(v.codex,'executable',lambda:'codex-test')
    events=[{'type':'thread.started','thread_id':'synthetic'},
        {'type':'item.completed','item':{'type':'agent_message','text':'{"answer":"A"}'}},
        {'type':'turn.completed','usage':{'input_tokens':1,'output_tokens':2}}]
    def run(argv,**kwargs):
        captured.update(argv=argv,**kwargs)
        return SimpleNamespace(returncode=0,stdout='\n'.join(map(json.dumps,events)),stderr='')
    monkeypatch.setattr(v,'run_process',run);monkeypatch.setattr(v.telemetry,'record',lambda **kw:None)
    result=v.blind_with_images('Synthetic A question',schema={'type':'object'},system='Synthetic reviewer',images=[img],stage=tmp_path)
    argv=captured['argv'];assert '--ephemeral'in argv and argv[argv.index('--image')+1]==str(img.resolve())
    assert 'features.shell_tool=false'in argv and 'features.unified_exec=false'in argv
    assert 'features.view_image=false'in argv and 'web_search="disabled"'in argv
    assert captured['input']=='Synthetic A question' and result['text']=='{"answer":"A"}'
    assert (tmp_path/'blind-events.jsonl').exists()

def test_blind_parser_rejects_tool_events_even_for_image_questions():
    with pytest.raises(v.codex.SessionError,match='도구 이벤트'):
        v.codex.parse_events(json.dumps({'type':'item.completed','item':{'type':'command_execution'}}),model='gpt-test',blind=True)

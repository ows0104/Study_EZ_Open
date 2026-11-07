import hashlib
import fitz
import pytest
from quizbank import connection_figures as figures
from quizbank import connection_visuals as visual


def test_embedded_image_id_keeps_original_pixels_and_source_placement(tmp_path):
    pix=fitz.Pixmap(fitz.csRGB,fitz.IRect(0,0,100,100),False);pix.clear_with(180)
    original=pix.tobytes('png');doc=fitz.open();page=doc.new_page(width=400,height=400)
    page.insert_image(fitz.Rect(50,50,250,250),stream=original);path=tmp_path/'source.pdf';doc.save(path);doc.close()
    source={'id':'S1','localPath':str(path),'sha256':figures.sha(path)}
    material=tmp_path/'material';material.mkdir();catalog=figures.prepare({'sources':[source]},material)
    row=catalog['images'][0];spec={k:row[k]for k in ('image_id','source_id','page','crop')}
    spec.update(question_id='Q1',reason='Synthetic original image')
    bank={'questions':[{'question_id':'Q1'}]}
    result=visual.render(bank,[spec],{'sources':[source]},material)
    assert result['questions'][0]['stimuli'][0]['sha256']==row['sha256']
    assert row['width']==100 and row['height']==100
    (material/row['path']).write_bytes(b'changed')
    with pytest.raises(ValueError,match='changed'):figures.selected(spec,source,material)

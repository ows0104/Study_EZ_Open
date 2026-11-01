"""Make every derivative image use a consistent full-page source raster."""
import json
import pymupdf as f
import build_package as b

doc=f.open(b.SOURCE)
for path in sorted((b.OUT/'sections').glob('*.json')):
    s=json.loads(path.read_text(encoding='utf-8'))
    for material in s['questions']+s['source_notes']+[s['answer_table_original']]:
        for record in material['source_regions']:
            updated,_=b.region_record(doc,record['source_page'],f.Rect(record['bbox']),b.OUT/record['file'])
            record.update(updated)
        for record in material['images']:
            updated,pix=b.region_record(doc,record['source_page'],f.Rect(record['bbox']),b.OUT/record['file'])
            record.update(updated)
            gp=record['gpt_image']['file']
            record['gpt_image']={'file':gp,**b.labeled_image(pix,record['id']+f' | source p.{record["source_page"]}',b.OUT/gp)}
    b.save_json(path,s)
    print('REFRESHED',s['id'],flush=True)

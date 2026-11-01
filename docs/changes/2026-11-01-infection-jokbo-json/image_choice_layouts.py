"""Keep the original number-to-picture layout for the two image-only MCQs."""
import json,shutil
import pymupdf as f
import build_package as b

v=json.loads((b.HERE/'materials-verification.json').read_text(encoding='utf-8'))
assert v['status']=='passed' and v['manifest_sha256']==b.file_sha(b.OUT/'manifest.json')
# Preserve actual successful full-source pixel evidence for unchanged PNGs.
shutil.copyfile(b.OUT/'manifest.json',b.HERE/'pixel-baseline-manifest.json')
shutil.copyfile(b.HERE/'materials-verification.json',b.HERE/'pixel-baseline-verification.json')
records={}
for path in (b.OUT/'sections').glob('*.json'):
    s=json.loads(path.read_text(encoding='utf-8'))
    for material in s['questions']+s['source_notes']+[s['answer_table_original']]:
        for record in material['source_regions']+material['images']:
            records[record['file']]={key:record[key] for key in ('file','source_page','bbox','render_scale','render_method','width','height','pixel_sha256','sha256')}
b.save_json(b.HERE/'pixel-baseline-records.json',{'source_sha256':b.PLAN['source']['sha256'],
            'manifest_sha256':v['manifest_sha256'],'records':records})
count=0
for path in (b.OUT/'sections').glob('*.json'):
    s=json.loads(path.read_text(encoding='utf-8'));changed=False
    for q in s['questions']:
        if not(q['images'] and q['choices'] and any(not c['text'].strip() for c in q['choices'])):continue
        q['visual_layout_required']=True;q['layout_images']=[]
        for i,region in enumerate(q['source_regions'],1):
            ident=f'{q["id"]}-L{i:02d}';file=b.OUT/'gpt-images'/f'{ident}.png'
            pix=f.Pixmap(b.OUT/region['file'])
            q['layout_images'].append({**region,'id':ident,'role':'image_choice_source_layout',
                'gpt_image':{'file':b.rel(file),**b.labeled_image(pix,ident+f' | source p.{region["source_page"]}',file)}})
        changed=True;count+=1
    if changed:b.save_json(path,s)
assert count==2
print('Added source-layout attachment support for',count,'image-only choice questions.')

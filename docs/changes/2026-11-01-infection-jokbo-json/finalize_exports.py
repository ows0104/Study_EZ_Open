"""Refresh mechanical exports after retaining explicit source-context roles."""
import json
from pathlib import Path
import build_package as b

catalog=json.loads((b.OUT/'catalog.json').read_text(encoding='utf-8'))
questions=[]
for key,meta in b.PLAN['files'].items():
    path=b.OUT/'sections'/f'S{key}.json'
    s=json.loads(path.read_text(encoding='utf-8'))
    for q in s['questions']:q['source_unit_kind']='question'
    for n,u in zip(s['source_notes'],[u for u in meta['units'] if u['kind']!='question']):
        n['source_unit_kind']=u['kind']
    s['answer_table_original']['source_unit_kind']='answer_table'
    b.save_json(path,s)
    entry=next(e for e in catalog['sections'] if e['id']==s['id'])
    entry.update(b.export_md(json.loads(path.read_text(encoding='utf-8'))))
    questions.extend({**q,'section_id':s['id'],'section_title':s['title']} for q in s['questions'])
catalog['counts']['gpt_image_attachments']=sum(len(e['image_files']) for e in catalog['sections'])
catalog['counts']['image_choice_questions']=sum(bool(q.get('layout_images')) for q in questions)
catalog['counts']['image_choice_layout_images']=sum(len(q.get('layout_images',[])) for q in questions)
b.save_json(b.OUT/'catalog.json',catalog)
b.save_json(b.OUT/'questions.json',{'schema_version':'1.0','paths_relative_to':'package_root','questions':questions})
files=[{'file':b.rel(p),'bytes':p.stat().st_size,'sha256':b.file_sha(p)} for p in sorted(b.OUT.rglob('*')) if p.is_file() and p.name!='manifest.json']
b.save_json(b.OUT/'manifest.json',{'schema_version':'1.0','files':files})
artifact=json.loads((b.HERE/'artifact.json').read_text(encoding='utf-8'))
artifact['counts']=catalog['counts'];b.save_json(b.HERE/'artifact.json',artifact)
print(json.dumps(catalog['counts'],ensure_ascii=False))

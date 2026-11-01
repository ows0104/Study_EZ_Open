"""Render representative saved PDF pages for visual QA."""
import build_materials as b
import pymupdf as f
plan=b.read(b.HERE/'upload-plan.json');folder=b.HERE/'preview';folder.mkdir(exist_ok=True)
selected=[]
for section,role in [('S3','priority'),('S3','reference'),('S13','figure'),('S55','unresolved'),('SCBL4','long'),('SLAB','appendix')]:
    meta=next(m for m in plan['files'].values() if m['section_id']==section)
    if role=='reference':q=next(q for q in meta['questions'] if not q['priority']);page=q['first_page']
    elif role=='unresolved':
        q=next((q for q in meta['questions'] if q['answer']['status']!='source_match'),meta['questions'][0]);page=q['first_page']
    elif role=='appendix':page=meta['pages']
    else:page=meta['questions'][0]['first_page']
    with f.open(meta['path']) as doc:
        path=folder/f'{section}-{role}.png';doc[page-1].get_pixmap(matrix=f.Matrix(1.4,1.4),alpha=False).save(path)
        selected.append({'pdf':meta['path'],'page':page,'preview':str(path),'role':role})
for role,predicate in [('actual-unresolved',lambda q:q['answer']['status']!='source_match'),
                       ('continued',lambda q:q['last_page']>q['first_page']),
                       ('joint-professors',lambda q:len(q['professors'])>1)]:
    meta,q=next((m,q) for m in plan['files'].values() for q in m['questions'] if predicate(q))
    page=q['last_page'] if role=='continued' else q['first_page']
    with f.open(meta['path']) as doc:
        path=folder/f'{role}.png';doc[page-1].get_pixmap(matrix=f.Matrix(1.4,1.4),alpha=False).save(path)
        selected.append({'pdf':meta['path'],'page':page,'preview':str(path),'role':role})
b.save(b.HERE/'rendered-pages.json',selected)
print('Rendered',len(selected),'representative pages')

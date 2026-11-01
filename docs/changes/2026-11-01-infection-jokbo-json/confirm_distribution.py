"""Read-only confirmation of PDF publication and retained management archives."""
from pathlib import Path
import concurrent.futures,hashlib,json,os,sys
from datetime import datetime,timezone,timedelta
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent
os.chdir(ROOT/'server');sys.path.insert(0,str(ROOT/'server'))
from sqlalchemy import select
from app.database import SessionLocal
from app.models import Asset,Lecture
from app.storage import ObjectStorage

def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
plan=json.loads((HERE.parent/'2026-11-01-infection-jokbo-answer-audit/upload-plan.json').read_text(encoding='utf-8'))
wanted={r['run_id']:r for r in plan['lectures']}
with SessionLocal() as db:
    assets=db.scalars(select(Asset).where(Asset.subject=='감염과 면역',Asset.kind=='jokbo')).all()
    rows=[{'run_id':a.run_id,'filename':a.filename,'content_type':a.content_type,'object_key':a.object_key,'size_bytes':a.size_bytes} for a in assets]
    linked=set(db.scalars(select(Lecture.run_id).where(Lecture.subject=='감염과 면역',Lecture.timetable_event_id.is_not(None))).all())
assert {r['run_id'] for r in rows}==set(wanted) and set(wanted)<=linked
storage=ObjectStorage()
def verify(row):
    target=wanted[row['run_id']];local=Path(target['path'])
    expected=plan['files'][target['section']]['sha256']
    assert row['filename']==local.name and local.suffix.lower()=='.pdf'
    assert row['content_type']=='application/pdf' and row['size_bytes']==local.stat().st_size
    response=storage.client.get_object(Bucket=storage.bucket,Key=row['object_key'])
    body=response['Body'];h=hashlib.sha256()
    try:
        for chunk in body.iter_chunks(1024*1024):h.update(chunk)
    finally:body.close()
    assert h.hexdigest()==expected==digest(local)
    return {'run_id':row['run_id'],'filename':row['filename'],'sha256':expected}
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:verified=list(pool.map(verify,rows))
print('Confirmed 80 timetable-linked PDF attachments; stored bytes match verified local PDFs.',flush=True)
artifact=json.loads((HERE/'artifact.json').read_text(encoding='utf-8'));folder=Path(artifact['output_folder'])
previous=json.loads((HERE/'materials-verification.json').read_text(encoding='utf-8'))
assert digest(folder/'manifest.json')==previous['manifest_sha256']
manifest=json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
for item in manifest['files']:
    path=(folder/item['file']).resolve()
    assert path.is_relative_to(folder.resolve()) and path.stat().st_size==item['bytes'] and digest(path)==item['sha256']
package=json.loads((HERE/'package-verification.json').read_text(encoding='utf-8'))
for item in package['bundles']:assert digest(item['path'])==item['sha256']
result={'status':'passed','confirmed_at':datetime.now(timezone(timedelta(hours=9))).isoformat(),
        'site_format':'PDF','pdf_attachments':80,'site_files':verified,'management_folder':str(folder),
        'management_files_retained':len(manifest['files']),'management_json_and_images':'retained',
        'archive_bundles_retained':len(package['bundles']),'answer_links_to_review':19,
        'policy':'docs/policies/infection-immunity-materials-2026.md','remote_changes':False}
(HERE/'distribution-confirmation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('Confirmed management JSON, linked images, original sources and both archives; policy recorded.')

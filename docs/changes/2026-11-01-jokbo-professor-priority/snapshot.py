"""Read-only inventory and local rollback evidence, without credentials in output."""
from pathlib import Path
import hashlib, json, os, sys
ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'server'))
os.chdir(ROOT / 'server')
from sqlalchemy import select
from app.database import SessionLocal
from app.models import Asset, Lecture, QuizBank

def digest(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def main():
    target = HERE / 'remote-before.json'
    assert not target.exists(), 'Preserve the original snapshot'
    old = json.loads((HERE.parent / '2026-11-01-infection-jokbo-answer-audit/upload-plan.json').read_text(encoding='utf-8'))
    with SessionLocal() as db:
        lectures = [{k: str(getattr(l, k)) if k == 'date' else getattr(l, k) for k in
                    ('run_id', 'uid', 'title', 'date', 'slot', 'slot_end', 'start_time', 'professors', 'author', 'version', 'timetable_event_id')}
                    for l in db.scalars(select(Lecture).where(Lecture.subject == old['subject']))]
        assets = [{k: getattr(a, k) for k in ('id', 'run_id', 'kind', 'filename', 'object_key', 'size_bytes', 'content_type')}
                  for a in db.scalars(select(Asset).where(Asset.subject == old['subject']))]
        banks = [{'run_id': b.run_id, 'build_id': b.build_id} for b in db.scalars(select(QuizBank).where(QuizBank.subject == old['subject']))]
    assert {l['run_id'] for l in lectures} == {l['run_id'] for l in old['lectures']}
    wanted = {r['run_id']: r for r in old['lectures']}
    for a in assets:
        if a['kind'] == 'jokbo':
            row = wanted[a['run_id']]; meta = old['files'][row['section']]; path = Path(row['path'])
            assert digest(path) == meta['sha256'] and a['filename'] == path.name and a['size_bytes'] == path.stat().st_size
            a['preserved_local_path'] = str(path); a['sha256'] = meta['sha256']
    target.write_text(json.dumps({'lectures': lectures, 'assets': assets, 'banks': banks}, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'lectures': len(lectures), 'assets': len(assets), 'current_notes': sum(a['kind']=='notes_current' for a in assets), 'banks': len(banks)}))

if __name__ == '__main__': main()

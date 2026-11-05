"""Run the real API against a dedicated local database; never reads server/.env."""
import json
import os
import sys
from pathlib import Path
from datetime import date
root = Path(__file__).resolve().parents[3]
local = root / 'tmp' / 'connection-product-local'
local.mkdir(parents=True, exist_ok=True)
os.environ.update(ENVIRONMENT='local-test', DATABASE_URL=f'sqlite:///{(local / "app.db").as_posix()}', STUDYEZ_LOCAL_STORAGE_DIR=str(local / 'storage'))
sys.path.insert(0, str(root / 'server'))
from app.database import Base, SessionLocal, engine
from app.models import Lecture, ConnectionContent
from app.routes.connections import Document
Base.metadata.create_all(engine)
document = Document.model_validate_json(Path(__file__).with_name('cholinergic.json').read_text(encoding='utf-8')).model_dump()
with SessionLocal() as db:
    if not db.get(Lecture, ('약리학','261002_01')):
        db.add(Lecture(subject='약리학',run_id='261002_01',uid='local-cholinergic',date=date(2026,10,2),slot=1,slot_end=1,start_time='09:00',title='콜린성 약리학(1)',professors=['이철환'],author='',version=1))
    if not db.get(ConnectionContent, ('약리학','261002_01',document['revision'])):
        db.add(ConnectionContent(subject='약리학',run_id='261002_01',revision=document['revision'],document=document,published=False))
    db.commit()
if __name__ == '__main__':
    import uvicorn
    uvicorn.run('app.main:app', host='127.0.0.1', port=8016)

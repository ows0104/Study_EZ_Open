"""Explicit root-only production schema preparation; no existing learning writes."""
import argparse
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'server'),str(ROOT)]
from dotenv import load_dotenv
load_dotenv(ROOT/'server/.env')
from sqlalchemy import inspect,text,select
from app.database import engine,SessionLocal
from app.models.root_learning import RootContent,RootControl,RootSession,RootEvent
from app.models.root_generation import RootGeneration
from app.models import Lecture,Asset,QuizBank

p=argparse.ArgumentParser();p.add_argument('--apply',action='store_true');a=p.parse_args()
tables=[m.__table__ for m in (RootContent,RootControl,RootSession,RootEvent,RootGeneration)]
assert engine.dialect.name=='postgresql','Only the explicitly configured production PostgreSQL connection is expected'
if a.apply:
    with engine.begin() as conn:
        for table in tables:table.create(conn,checkfirst=True)
        columns={c['name'] for c in inspect(conn).get_columns('root_generation')}
        for name in ('web_dispatch','web_response'):
            if name not in columns:conn.execute(text(f'ALTER TABLE root_generation ADD COLUMN {name} JSON'))
        for table in tables:conn.execute(text(f'ALTER TABLE {table.name} ENABLE ROW LEVEL SECURITY'))
with engine.connect() as conn:
    rows=conn.execute(text("SELECT relname,relrowsecurity FROM pg_class WHERE relname IN ('root_content','root_control','root_session','root_event','root_generation') ORDER BY relname")).all()
print(json.dumps({'rootTables':[{'name':r[0],'rls':r[1]} for r in rows],'applied':a.apply}))
with SessionLocal() as db:
    lecture=db.get(Lecture,('약리학','261002_01'));assert lecture
    assets=db.scalars(select(Asset).where(Asset.subject=='약리학',Asset.run_id=='261002_01',Asset.kind.in_(['notes_current','jokbo']))).all()
    bank=db.get(QuizBank,('약리학','261002_01'))
    print(json.dumps({'pilot':lecture.title,'sources':[{'kind':s.kind,'filename':s.filename,'bytes':s.size_bytes} for s in assets],
        'existingBank':{'build':bank.build_id,'status':bank.status,'questions':len(bank.bank['questions'])} if bank else None},ensure_ascii=False))

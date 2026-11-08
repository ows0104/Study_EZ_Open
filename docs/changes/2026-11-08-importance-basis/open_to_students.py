"""감염병리1(261104_02) map-tree-26110803을 학생에게 공개 — 관리자 publication 경로 그대로.

User approval 2026-11-08: 「학생 공개」. Only control.allowed_users changes (['runner'] → [] = 전체);
revision/enabled stay; one publication RootEvent is added by the route itself.
"""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
MAIN = ROOT.parents[1] if ROOT.parent.name == '.worktrees' else ROOT
sys.path.insert(0, str(ROOT / 'server')); sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv
load_dotenv(MAIN / 'server/.env', override=False)
from app.database import SessionLocal
from app.auth import CurrentUser
from app.routes.root_learning import publish, Publication
from app.models.root_learning import RootControl, RootEvent
from sqlalchemy import select

SUBJECT, RUN_ID, REVISION = '감염과 면역', '261104_02', 'map-tree-26110803'
with SessionLocal() as db:
    control = db.get(RootControl, (SUBJECT, RUN_ID))
    before = {'revision': control.revision, 'enabled': control.enabled, 'allowedUsers': control.allowed_users}
    assert before == {'revision': REVISION, 'enabled': True, 'allowedUsers': ['runner']}, before
    events = db.scalar(select(__import__('sqlalchemy').func.count()).select_from(RootEvent).where(RootEvent.run_id == RUN_ID))
    result = publish(SUBJECT, RUN_ID, Publication(revision=REVISION, reviewed=True, enabled=True, allowedUsers=[]),
                     CurrentUser(id='runner', email='', is_admin=True), db)
    control = db.get(RootControl, (SUBJECT, RUN_ID)); db.refresh(control)
    after = {'revision': control.revision, 'enabled': control.enabled, 'allowedUsers': control.allowed_users}
    events_after = db.scalar(select(__import__('sqlalchemy').func.count()).select_from(RootEvent).where(RootEvent.run_id == RUN_ID))
    assert after == {'revision': REVISION, 'enabled': True, 'allowedUsers': []} and events_after == events + 1, (after, events, events_after)
record = {'before': before, 'after': after, 'route': result, 'events': [events, events_after]}
out = MAIN / 'runs/_e2e/26110803/publication/open-to-students.json'
out.write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding='utf-8'); print(json.dumps(record, ensure_ascii=False))

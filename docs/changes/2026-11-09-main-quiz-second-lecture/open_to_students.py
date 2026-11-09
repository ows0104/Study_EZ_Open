"""사슬알균(감염과 면역 261105_01) map-tree-26110901을 학생에게 공개 — 관리자 publication 경로 그대로.

User approval 2026-11-09: 「학생 공개」. Only control.allowed_users changes (['runner'] → [] = 전체);
revision/enabled stay; one publication RootEvent is added by the route itself.
Adapted from docs/changes/2026-11-08-importance-basis/open_to_students.py (감염병리1).
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
from sqlalchemy import select, func

SUBJECT, RUN_ID, REVISION = '감염과 면역', '261105_01', 'map-tree-26110901'
with SessionLocal() as db:
    others = sorted([c.subject, c.run_id, c.revision, c.enabled, list(c.allowed_users or [])]
                    for c in db.scalars(select(RootControl)) if (c.subject, c.run_id) != (SUBJECT, RUN_ID))
    control = db.get(RootControl, (SUBJECT, RUN_ID))
    before = {'revision': control.revision, 'enabled': control.enabled, 'allowedUsers': control.allowed_users}
    assert before == {'revision': REVISION, 'enabled': True, 'allowedUsers': ['runner']}, before
    count = lambda: db.scalar(select(func.count()).select_from(RootEvent).where(RootEvent.subject == SUBJECT, RootEvent.run_id == RUN_ID))
    events = count()
    result = publish(SUBJECT, RUN_ID, Publication(revision=REVISION, reviewed=True, enabled=True, allowedUsers=[]),
                     CurrentUser(id='runner', email='', is_admin=True), db)
    control = db.get(RootControl, (SUBJECT, RUN_ID)); db.refresh(control)
    after = {'revision': control.revision, 'enabled': control.enabled, 'allowedUsers': control.allowed_users}
    events_after = count()
    others_after = sorted([c.subject, c.run_id, c.revision, c.enabled, list(c.allowed_users or [])]
                          for c in db.scalars(select(RootControl)) if (c.subject, c.run_id) != (SUBJECT, RUN_ID))
    assert after == {'revision': REVISION, 'enabled': True, 'allowedUsers': []} and events_after == events + 1, (after, events, events_after)
    assert others_after == others, 'Another lecture changed'
record = {'before': before, 'after': after, 'route': result, 'events': [events, events_after], 'otherControls': len(others)}
out = MAIN / 'runs/_e2e/26110901/publication/open-to-students.json'
out.write_text(json.dumps(record, ensure_ascii=False, indent=1, default=str), encoding='utf-8'); print(json.dumps(record, ensure_ascii=False, default=str))

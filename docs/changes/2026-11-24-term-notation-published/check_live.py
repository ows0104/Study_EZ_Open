"""운영 쓰기 뒤 확인(읽기만): DB·R2가 after/ 사본과 같고, 운영 문서로 계산한 기록이 옛 문서와 같은지."""
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(r'C:\Users\ows01\Documents\Python Scripts\Study_EZ_Open\server\.env')
from sqlalchemy import distinct, select

from app.database import SessionLocal
from app.models.lectures import Asset
from app.models.root_generation import RootGeneration
from app.models.root_learning import RootContent, RootControl, RootEvent
from app.root_learning import policy as policy_module
from app.root_learning.content import events_for
from app.root_learning.light import stored
from app.root_learning.state import personal_tiers, replay_tasks
from app.storage import ObjectStorage
from studyez_contracts.roots import document_hash

WORK = Path(r'C:\Users\ows01\Documents\Python Scripts\Study_EZ_Open\runs\_development\2026-11-24-term-notation-published')


def load(p):
    return json.loads(p.read_text(encoding='utf-8')) if p.exists() else None


def check(db, store, rid):
    meta = load(WORK / rid / 'before/meta.json')
    after, old = load(WORK / rid / 'after/document.json'), load(WORK / rid / 'before/document.json')
    subject, rev = meta['subject'], meta['revision']
    out = {'runId': rid}
    assert db.get(RootControl, (subject, rid)).revision == rev, '공개판'
    row = db.get(RootContent, (subject, rid, rev))
    assert row.document == after and row.digest == document_hash(after), 'root_content'
    assert row.light == stored(after), 'light'
    gen = db.get(RootGeneration, meta['generationId'])
    assert gen.result['document'] == after and gen.result_digest == document_hash(gen.result), 'root_generation'
    for kind, m in meta['assets'].items():
        asset = db.get(Asset, m['id'])
        want = (WORK / rid / f'after/{kind}.json').read_bytes()
        got = store.get_bytes(asset.object_key)
        assert got == want and asset.size_bytes == len(want), (kind, asset.object_key)
        out[kind] = asset.object_key.rsplit('/', 1)[-1]
    now, pol = datetime.now(timezone.utc), policy_module.configured_policy()
    users = db.scalars(select(distinct(RootEvent.user_id)).where(RootEvent.subject == subject, RootEvent.run_id == rid)).all()
    n = 0
    for user in users:
        events = events_for(db, subject, rid, user)
        n += len(events)
        assert replay_tasks(old, events, now, pol) == replay_tasks(row.document, events, now, pol), '기록'
        assert personal_tiers(old, events, now) == personal_tiers(row.document, events, now), '내 중요도'
    out['events'] = n
    return out


if __name__ == '__main__':
    store = ObjectStorage()
    with SessionLocal() as db:
        db.connection().exec_driver_sql('SET TRANSACTION READ ONLY')
        for rid in sys.argv[1:]:
            print(json.dumps(check(db, store, rid), ensure_ascii=False), flush=True)
        db.rollback()

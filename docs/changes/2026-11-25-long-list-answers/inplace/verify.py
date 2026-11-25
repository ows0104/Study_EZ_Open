"""운영 쓰기 전 확인(읽기만): 고친 사본으로 바꿔도 학습 기록·선지·순서·근거가 똑같이 붙는지.

- 각 사용자의 실제 이벤트로 replay_tasks·내 중요도·제외를 옛 문서와 새 문서에서 계산해 같아야 한다.
- 선지(root_mcq v2)·순서(root_order)가 붙던 문항은 새 글·새 asset에서도 붙고, 근거 지문이 맞던 문항은 그대로 맞아야 한다.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(r'C:\Users\ows01\Documents\Python Scripts\Study_EZ_Open\server\.env')
from sqlalchemy import select, distinct

from app.database import SessionLocal
from app.models.root_learning import RootEvent
from app.root_learning import policy as policy_module
from app.root_learning.content import events_for, excluded_ids
from app.root_learning.state import personal_tiers, replay_tasks
from studyez_contracts.bank.slide_focus import question_hash
from studyez_contracts.roots import mcq as mcq_contract
from studyez_contracts.roots import order as order_contract

WORK = Path(r'C:\Users\ows01\Documents\Python Scripts\Study_EZ_Open\runs\_development\2026-11-25-long-list-answers/inplace')


def load(path):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else None


def check(db, rid):
    meta = load(WORK / rid / 'before/meta.json')
    old, new = (load(WORK / rid / s / 'document.json') for s in ('before', 'after'))
    rev = meta['revision']
    now = datetime.now(timezone.utc)
    pol = policy_module.configured_policy()
    users = db.scalars(select(distinct(RootEvent.user_id)).where(RootEvent.subject == meta['subject'], RootEvent.run_id == rid)).all()
    events_checked = 0
    for user in users:
        events = events_for(db, meta['subject'], rid, user)
        events_checked += len(events)
        assert replay_tasks(old, events, now, pol) == replay_tasks(new, events, now, pol), (rid, '기록 계산이 달라짐')
        assert personal_tiers(old, events, now) == personal_tiers(new, events, now), (rid, '내 중요도가 달라짐')
        assert excluded_ids(events, rev) == excluded_ids(events, rev), (rid, '제외')
    oq = {q['question_id']: q for q in old['bank_snapshot']['questions']}
    nq = {q['question_id']: q for q in new['bank_snapshot']['questions']}
    out = {'runId': rid, 'users': len(users), 'events': events_checked}
    for kind, attach in (('root_mcq', mcq_contract.attachable_v2), ('root_order', order_contract.attachable)):
        a, b = load(WORK / rid / f'before/{kind}.json'), load(WORK / rid / f'after/{kind}.json')
        if a is None:
            continue
        was = {qid for qid, q in oq.items() if attach(a, rev, q) is not None}
        now_ = {qid for qid, q in nq.items() if attach(b, rev, q) is not None}
        assert was == now_, (rid, kind, sorted(was ^ now_)[:10])
        out[kind] = len(now_)
    a, b = load(WORK / rid / 'before/root_evidence.json'), load(WORK / rid / 'after/root_evidence.json')
    for block in ('slideFocus', 'evidenceResolution'):
        ra = (a.get(block) or {}).get('questions') or {}
        rb = (b.get(block) or {}).get('questions') or {}
        was = {k for k, r in ra.items() if k in oq and r.get('questionHash') == question_hash(oq[k])}
        now_ = {k for k, r in rb.items() if k in nq and r.get('questionHash') == question_hash(nq[k])}
        assert was == now_, (rid, block, sorted(was ^ now_)[:10])
        out[block] = len(now_)
    return out


if __name__ == '__main__':
    with SessionLocal() as db:
        db.connection().exec_driver_sql('SET TRANSACTION READ ONLY')
        for rid in sys.argv[1:]:
            print(json.dumps(check(db, rid), ensure_ascii=False), flush=True)
        db.rollback()

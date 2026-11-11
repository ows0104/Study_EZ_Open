"""Give the 감염과 면역 lectures moved by the 2026-11-05 timetable notice their current timetable numbers.

docs/changes/2026-11-11-immunity-renumber. Six pairs swap run IDs. The 미코플라스마·무산소 pair is mixed in place
(a note named with the new number reached the old row on 2026-11-08), so its rows are sorted by what they hold.

  (default)                       read only: print the plan, the mixed-pair judgments and the plan fingerprint
  --copy-r2                       copy every moved asset to its new R2 key (nothing is deleted)
  --apply --expect-plan SHA       apply exactly the reviewed plan in one transaction, write a receipt
  --reverse --previous-receipt R  undo an applied receipt
  --local-runs [--apply]          swap the runner's own files under runs/ (backed up first)
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
CHANGE = ROOT / 'docs/changes/2026-11-11-immunity-renumber'
SUBJECT = '감염과 면역'
SWAP = {'261105_05': '261110_01', '261110_01': '261105_05',  # 렙토스피라 ↔ 콜레라
        '261110_02': '261113_01', '261113_01': '261110_02',  # 헤르페스 ↔ 아데노·폭스
        '261118_01': '261119_06', '261119_06': '261118_01',  # 신종 감염병 ↔ 의료관련감염
        '261119_05': '261119_07', '261119_07': '261119_05',  # 감염병의 예방 ↔ 형성평가
        '261126_03': '261126_05', '261126_05': '261126_03'}  # 호산구성 질환 ↔ 다양한 알레르기
MIXED = ('261105_06', '261106_06')
HOME = {'미코': '261105_06', '무산소': '261106_06'}  # current timetable: 미코플라스마 11-05 14:00, 무산소 11-06 14:00
STABLE = {'261105_06': '무산소', '261106_06': '미코'}  # what each row held under the 11-05 stable IDs
SHOWN = {'261105_06': '미코', '261106_06': '무산소'}  # what each row's title, notes and deck say since the overwrite
OVERWRITE = datetime(2026, 11, 8, 14, 30, tzinfo=timezone.utc)
IDS = sorted(set(SWAP) | set(MIXED))
TOPICS = {'미코': re.compile(r'미코|클라미디아|mycoplasma|chlamydia|김동현|251107_06', re.I),
          '무산소': re.compile(r'무산소|clostridium|bacteroides|anaerob|difficile|염진기|이원우|251106_06', re.I)}
# Activity rows carry no content: before the overwrite they belonged to the row's stable topic, after it to the
# topic the row showed (its title, notes and deck).
TIMED = {'preview': 'updated_at', 'prequiz_job': 'created_at', 'user_preview': 'updated_at',
         'preview_open': 'last_at', 'asset_grab': 'last_at', 'user_review': 'updated_at', 'note_read': 'created_at',
         'lecture_memo': 'updated_at'}
GROUPED = {'pre_item', 'main_item', 'card_edit', 'quiz_attempt', 'main_attempt', 'pre_review_log', 'main_review_log'}
SINGULAR = {'notes_current', 'notes_prev', 'main_apkg', 'pre_apkg', 'jokbo'}
LOCAL_SWAP = {**SWAP, MIXED[0]: MIXED[1], MIXED[1]: MIXED[0]}  # the runner's files follow the 11-05 stable IDs


class Stop(RuntimeError):
    """The database is not in the reviewed shape; nothing is written."""


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()


def topic(text):
    hits = [name for name, rx in TOPICS.items() if rx.search(text or '')]
    return hits[0] if len(hits) == 1 else None


def utc(value):
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def key_of(event):
    """The run ID a timetable cell gets from its date and period (09:00 is period 1)."""
    day = event['date'] if isinstance(event['date'], str) else event['date'].isoformat()
    return day[2:4] + day[5:7] + day[8:10] + f"_{int(str(event['start_time'])[:2]) - 8:02d}"


def encode(row):
    return {k: (v.isoformat() if isinstance(v, (date, datetime)) else v) for k, v in row.items()}


def decode(table, row):
    out = {}
    for k, v in row.items():
        kind = table.c[k].type.__class__.__name__.lower()
        if isinstance(v, str) and ('datetime' in kind or 'timestamp' in kind):
            v = datetime.fromisoformat(v)
        elif isinstance(v, str) and kind == 'date':
            v = date.fromisoformat(v)
        out[k] = v
    return out


def lecture_tables(md):
    return [t for name, t in sorted(md.tables.items())
            if name != 'lecture' and {'subject', 'run_id'} <= set(t.c.keys())]


def identity(table, row):
    """The row's primary key without its lecture columns."""
    cols = [c.name for c in table.primary_key.columns] or list(table.c.keys())
    return {c: row[c] for c in cols if c not in ('subject', 'run_id')}


def group_topics(name, rows):
    """A run's question rows share one topic: every row that names one must agree."""
    found = {}
    for r in rows:
        text = ' '.join(str(r.get(c) or '') for c in ('stem', 'answer', 'explanation', 'question', 'source_stem'))
        t = topic(text)
        if t:
            found.setdefault(r['run_id'], set()).add(t)
    return {rid: next(iter(ts)) if len(ts) == 1 else None for rid, ts in found.items()}


def judge(name, row, groups):
    rid = row['run_id']
    if name == 'asset':
        return topic(row['filename']), f"file {row['kind']}: {row['filename']}"
    if name == 'run_meta':
        return topic(json.dumps(row['payload'], ensure_ascii=False)), 'deck description'
    if name in GROUPED:
        return groups.get(rid), 'question content of the run'
    if name in TIMED:
        at = utc(row[TIMED[name]])
        return (STABLE[rid] if at < OVERWRITE else SHOWN[rid]), f"{TIMED[name]} {at:%m-%d %H:%M}Z"
    return None, 'no rule for this table'


def build_plan(conn, md, abandon=()):
    """`abandon`: ids of failed Main-Quiz generations the operator gave up. Their packet keeps the old run ID, so
    resuming one after the renumber would reach the swapped lecture; without this they stop the plan."""
    from sqlalchemy import select
    L, E = md.tables['lecture'], md.tables['timetable_event']
    lectures = {r['run_id']: dict(r) for r in conn.execute(
        select(L).where(L.c.subject == SUBJECT, L.c.run_id.in_(IDS))).mappings()}
    if set(lectures) != set(IDS):
        raise Stop(f'lectures missing: {sorted(set(IDS) - set(lectures))}')
    if any(conn.execute(select(L.c.run_id).where(L.c.run_id.like('~%'))).all()):
        raise Stop('staging lecture rows exist from an interrupted run')
    for rid in MIXED:
        if topic(lectures[rid]['title']) != SHOWN[rid]:
            raise Stop(f'{rid} title is not {SHOWN[rid]}: {lectures[rid]["title"]}')
    events = {r['id']: dict(r) for r in conn.execute(select(E)).mappings()}
    for rid, row in lectures.items():
        event = events.get(row['timetable_event_id'])
        wanted = SWAP.get(rid) or MIXED[1 - MIXED.index(rid)]
        if not event or key_of(event) != wanted:
            raise Stop(f'{rid} is not linked to the cell numbered {wanted} (already renumbered?)')
    final = {}
    for rid, dst in SWAP.items():
        row = dict(lectures[rid], run_id=dst)
        row['uid'] = re.sub(f'^{rid}#', f'{dst}#', row['uid'] or '')
        final[dst] = row
    for rid in MIXED:
        other = MIXED[1 - MIXED.index(rid)]
        final[rid] = dict(lectures[rid], timetable_event_id=lectures[other]['timetable_event_id'], match_confirmed=True)
    for rid, row in final.items():
        event = events.get(row['timetable_event_id'])
        if not event or key_of(event) != rid:
            raise Stop(f'{rid} would link to a timetable cell numbered {event and key_of(event)}')
        if rid in MIXED and topic(event['details']) != SHOWN[rid]:
            raise Stop(f'{rid} would link to the {topic(event["details"])} cell')

    moves, drops, judged, seen = [], [], [], []
    staying = {}
    J = md.tables['prequiz_job']
    open_jobs = {x[0] for x in conn.execute(select(J.c.id).where(
        J.c.subject == SUBJECT, J.c.run_id.in_(IDS), J.c.state.in_(('queued', 'running', 'held'))))}
    for t in lecture_tables(md):
        rows = [dict(r) for r in conn.execute(
            select(t).where(t.c.subject == SUBJECT, t.c.run_id.in_(IDS))).mappings()]
        if t.name == 'prequiz_job' and open_jobs:
            raise Stop(f'jobs for these lectures are still open: {sorted(open_jobs)}')
        if t.name == 'root_generation':
            unfinished = [g['id'] for g in rows if g['result'] is None and g['id'] not in abandon]
            if any(g['job_id'] in open_jobs for g in rows):
                raise Stop('a Main-Quiz generation for these lectures is still running')
            if unfinished:
                raise Stop(f'a failed Main-Quiz generation could still be resumed: {unfinished} '
                           '(finish it, or pass --abandon-generation to re-request it under the new number)')
        groups = group_topics(t.name, rows) if t.name in GROUPED else {}
        for r in rows:
            src = r['run_id']
            seen.append([t.name, src, encode(identity(t, r))])
            if src in SWAP:
                dst = SWAP[src]
            else:
                t_topic, why = judge(t.name, r, groups)
                judged.append({'table': t.name, 'key': encode(identity(t, r)), 'run_id': src, 'topic': t_topic, 'why': why})
                if t_topic is None:
                    continue
                dst = HOME[t_topic]
            move = {'table': t.name, 'key': encode(identity(t, r)), 'from': src, 'to': dst}
            if t.name == 'asset':
                parts = r['object_key'].split('/')
                if parts[:3] != ['lectures', SUBJECT, src]:
                    raise Stop(f'asset key outside its lecture folder: {r["object_key"]}')
                move.update(object_key=r['object_key'], new_key='/'.join(['lectures', SUBJECT, dst, *parts[3:]]),
                            size=r['size_bytes'], kind=r['kind'], filename=r['filename'])
            if dst != src:
                moves.append(move)
            else:
                staying.setdefault(t.name, []).append(dict(r))
    unknown = [j for j in judged if j['topic'] is None]
    if unknown:
        raise Stop('undecided rows: ' + json.dumps(unknown, ensure_ascii=False, default=str))

    # The mixed pair holds two copies of the same slide images; the copy already in place stays.
    assets_in = {(r['run_id'], r['kind'], r['filename']): r for r in staying.get('asset', [])}
    for m in [m for m in moves if m['table'] == 'asset']:
        here = assets_in.get((m['to'], m['kind'], m['filename']))
        if here is None:
            assets_in[(m['to'], m['kind'], m['filename'])] = m
            continue
        if here.get('size_bytes', here.get('size')) != m['size'] or m['kind'] in SINGULAR:
            raise Stop(f'two different files named {m["filename"]} would meet in {m["to"]}')
        moves.remove(m)
        drops.append(m)
    # A moved file must not reach a key that already holds a file: R2 would keep the other file there and the row
    # would point at it (review 2026-11-11).
    taken = {r['object_key'] for r in staying.get('asset', [])} | {m['object_key'] for m in moves + drops if 'object_key' in m}
    for m in moves:
        if m.get('new_key') in taken:
            raise Stop(f'{m["new_key"]} already holds another file')
    for rid in IDS:
        kinds = [k for (r, k, _) in assets_in if r == rid and k in SINGULAR]
        if len(kinds) != len(set(kinds)):
            raise Stop(f'{rid} would hold two files of one kind')
    for t in lecture_tables(md):
        keys = [fingerprint([m['to'], m['key']]) for m in moves if m['table'] == t.name]
        keys += [fingerprint([r['run_id'], encode(identity(t, r))]) for r in staying.get(t.name, [])]
        if len(keys) != len(set(keys)):
            raise Stop(f'{t.name}: two rows would share one key')

    hidden = []
    if 'study_hidden_lecture' in md.tables:
        H = md.tables['study_hidden_lecture']
        old_keys = {f'{SUBJECT}/{rid}': rid for rid in SWAP}
        for r in conn.execute(select(H).where(H.c.lecture_key.in_(old_keys))).mappings():
            hidden.append({'user_id': r['user_id'], 'from': r['lecture_key'],
                           'to': f'{SUBJECT}/{SWAP[old_keys[r["lecture_key"]]]}'})
    # Sorted: Postgres returns rows in storage order, which a student's write can change (2026-11-11 the reviewed
    # fingerprint moved with no row added, moved or removed).
    moves, drops = sorted(moves, key=fingerprint), sorted(drops, key=fingerprint)
    judged = sorted(judged, key=fingerprint)
    hidden = sorted(hidden, key=fingerprint)
    plan = {'moves': moves, 'drops': drops, 'inserts': [], 'hidden': hidden, 'judged': judged,
            'abandoned_generations': sorted(abandon), 'rows': sorted(seen, key=fingerprint),
            'lectures': {rid: encode(row) for rid, row in sorted(final.items())},
            'lectures_before': {rid: encode(row) for rid, row in sorted(lectures.items())}}
    plan['sha256'] = fingerprint({k: v for k, v in plan.items() if k != 'judged'})
    return plan


def outside_fingerprint(conn, md):
    """The keys of every row of the lecture tables that this change must not touch. Keys only: the statements here
    change nothing but `run_id`/`object_key` of matched rows, and full rows (bank JSON up to 20MB) would hold the
    table locks for minutes."""
    from sqlalchemy import select, or_
    result = {}
    for t in [md.tables['lecture'], *lecture_tables(md)]:
        cols = list({c.name: c for c in [*t.primary_key.columns, t.c.subject, t.c.run_id]}.values())
        rows = conn.execute(select(*cols).where(or_(t.c.subject != SUBJECT, t.c.run_id.notin_(IDS)))).mappings()
        result[t.name] = fingerprint(sorted(fingerprint(encode(dict(r))) for r in rows))
    return result


def lock(conn, md):
    """Short table locks so no site write lands between the plan and its check."""
    if conn.dialect.name == 'postgresql':
        conn.exec_driver_sql("SET LOCAL lock_timeout = '10s'")
        names = ', '.join(sorted({'lecture', 'study_hidden_lecture', *(t.name for t in lecture_tables(md))} & set(md.tables)))
        conn.exec_driver_sql(f'LOCK TABLE {names} IN SHARE ROW EXCLUSIVE MODE')


def row_keys(md, rows_before):
    return sorted(([name, r['run_id'], encode(identity(md.tables[name], r))]
                   for name, rows in rows_before.items() if name != 'lecture' for r in rows), key=fingerprint)


def apply_plan(conn, md, plan):
    from sqlalchemy import and_, delete, insert, select, update
    L = md.tables['lecture']
    outside = outside_fingerprint(conn, md)
    rows_before = {t.name: [dict(r) for r in conn.execute(select(t).where(t.c.subject == SUBJECT, t.c.run_id.in_(IDS))).mappings()]
                   for t in [L, *lecture_tables(md)]}
    stage = '~{}'.format
    current = {r['run_id']: r for r in rows_before['lecture']}
    if {rid: encode(r) for rid, r in current.items()} != plan['lectures_before']:
        raise Stop('lecture rows changed since the plan was made')
    # Every row of the 12 lectures must be one the plan decided on; a row written since would stay on a number
    # that now belongs to the other lecture (review 2026-11-11).
    if row_keys(md, rows_before) != plan['rows']:
        raise Stop('rows of these lectures changed since the plan was made')

    def where(t, key, run_id):
        return and_(t.c.subject == SUBJECT, t.c.run_id == run_id, *[t.c[c] == v for c, v in decode(t, key).items()])

    for rid in IDS:
        conn.execute(insert(L).values(**dict(current[rid], run_id=stage(rid), uid='~' + (current[rid]['uid'] or ''),
                                                 timetable_event_id=None)))
    for d in plan['drops']:
        t = md.tables[d['table']]
        if conn.execute(delete(t).where(where(t, d['key'], d['from']))).rowcount != 1:
            raise Stop(f'row to drop not found: {d}')
    for m in plan['moves']:
        t = md.tables[m['table']]
        values = {'run_id': stage(m['to'])}
        if 'new_key' in m:
            values['object_key'] = m['new_key']
        if conn.execute(update(t).where(where(t, m['key'], m['from'])).values(**values)).rowcount != 1:
            raise Stop(f'row to move not found: {m["table"]} {m["key"]} {m["from"]}')
    for rid, row in plan['lectures'].items():
        row = decode(L, row)
        conn.execute(update(L).where(L.c.subject == SUBJECT, L.c.run_id == rid)
                     .values(**{k: v for k, v in row.items() if k not in ('subject', 'run_id')}))
    for t in lecture_tables(md):
        for rid in IDS:
            conn.execute(update(t).where(t.c.subject == SUBJECT, t.c.run_id == stage(rid)).values(run_id=rid))
    for ins in plan['inserts']:
        t = md.tables[ins['table']]
        conn.execute(insert(t).values(**decode(t, ins['row'])))
    for t in lecture_tables(md):
        left = conn.execute(select(t.c.run_id).where(t.c.run_id.like('~%'))).all()
        if left:
            raise Stop(f'{t.name} still holds staged rows')
    conn.execute(delete(L).where(L.c.subject == SUBJECT, L.c.run_id.like('~%')))
    if plan['hidden']:
        H = md.tables['study_hidden_lecture']
        for h in plan['hidden']:
            if conn.execute(update(H).where(H.c.user_id == h['user_id'], H.c.lecture_key == h['from'])
                            .values(lecture_key='~' + h['to'])).rowcount != 1:
                raise Stop(f'hidden lecture row not found: {h}')
        for h in plan['hidden']:
            if conn.execute(update(H).where(H.c.user_id == h['user_id'], H.c.lecture_key == '~' + h['to'])
                            .values(lecture_key=h['to'])).rowcount != 1:
                raise Stop(f'hidden lecture row not found: {h}')

    if outside_fingerprint(conn, md) != outside:
        raise Stop('rows outside the 12 lectures changed')
    after = {t.name: [dict(r) for r in conn.execute(select(t).where(t.c.subject == SUBJECT, t.c.run_id.in_(IDS))).mappings()]
             for t in [L, *lecture_tables(md)]}
    want = simulate(rows_before, plan, md)
    for name in after:
        got = sorted(fingerprint(encode(r)) for r in after[name])
        if got != sorted(fingerprint(encode(r)) for r in want[name]):
            raise Stop(f'{name} is not what the plan says')
    return {'applied': True, 'plan_sha256': plan['sha256'], 'outside': outside,
            'rows': {name: len(rows) for name, rows in after.items() if rows}}


def simulate(rows_before, plan, md):
    """The 12 lectures' rows as the plan leaves them, computed without the database."""
    out = {name: [dict(r) for r in rows] for name, rows in rows_before.items()}
    out['lecture'] = [decode(md.tables['lecture'], r) for r in plan['lectures'].values()]
    for d in plan['drops']:
        t = md.tables[d['table']]
        key = decode(t, d['key'])
        out[d['table']] = [r for r in out[d['table']]
                           if not (r['run_id'] == d['from'] and all(r[c] == v for c, v in key.items()))]
    for m in plan['moves']:
        t = md.tables[m['table']]
        key = decode(t, m['key'])
        hit = [r for r in out[m['table']] if r['run_id'] == m['from'] and all(r[c] == v for c, v in key.items())
               and not r.get('_moved')]
        assert len(hit) == 1, m
        hit[0].update(run_id=m['to'], _moved=True)
        if 'new_key' in m:
            hit[0]['object_key'] = m['new_key']
    for ins in plan['inserts']:
        out[ins['table']].append(decode(md.tables[ins['table']], ins['row']))
    for rows in out.values():
        for r in rows:
            r.pop('_moved', None)
    return out


def reverse_plan(conn, md, receipt):
    """Undo an applied receipt against the database as it is now (read under the lock): the receipt's moves go
    back, rows written since on a swapped pair swap with their lecture, and a row written since on the mixed pair
    stops the reverse (which lecture it meant is a human call)."""
    from sqlalchemy import select
    plan = receipt['plan']
    moved = {fingerprint([m['table'], m['to'], m['key']]): m for m in plan['moves']}
    kept = {fingerprint(k) for k in plan['rows']} - {fingerprint([m['table'], m['from'], m['key']]) for m in plan['moves'] + plan['drops']}
    moves, new_rows = [], []
    for t in lecture_tables(md):
        for r in conn.execute(select(t).where(t.c.subject == SUBJECT, t.c.run_id.in_(IDS))).mappings():
            key, src = encode(identity(t, r)), r['run_id']
            m = moved.get(fingerprint([t.name, src, key]))
            if m:
                moves.append({**m, 'from': m['to'], 'to': m['from'],
                              **({'object_key': m['new_key'], 'new_key': m['object_key']} if 'new_key' in m else {})})
            elif fingerprint([t.name, src, key]) in kept:
                continue
            elif src in SWAP:
                back = {'table': t.name, 'key': key, 'from': src, 'to': SWAP[src]}
                if t.name == 'asset':
                    parts = r['object_key'].split('/')
                    back.update(object_key=r['object_key'], new_key='/'.join(['lectures', SUBJECT, SWAP[src], *parts[3:]]),
                                size=r['size_bytes'], kind=r['kind'], filename=r['filename'])
                moves.append(back)
            else:
                new_rows.append([t.name, src, key])
    if new_rows:
        raise Stop('rows written since on the mixed pair; decide them by hand: ' + json.dumps(new_rows, ensure_ascii=False, default=str))
    L = md.tables['lecture']
    now = {r['run_id']: encode(dict(r)) for r in conn.execute(
        select(L).where(L.c.subject == SUBJECT, L.c.run_id.in_(IDS))).mappings()}
    rows_now = {t.name: [dict(r) for r in conn.execute(select(t).where(t.c.subject == SUBJECT, t.c.run_id.in_(IDS))).mappings()]
                for t in lecture_tables(md)}
    back = {'moves': moves, 'drops': [], 'inserts': [{'table': d['table'], 'row': d['row']} for d in receipt['dropped_rows']],
            'hidden': [{**h, 'from': h['to'], 'to': h['from']} for h in plan['hidden']],
            'judged': [], 'lectures': plan['lectures_before'], 'lectures_before': now, 'rows': row_keys(md, rows_now)}
    back['sha256'] = fingerprint({k: v for k, v in back.items() if k != 'judged'})
    return back


def dropped_rows(conn, md, plan):
    from sqlalchemy import and_, select
    rows = []
    for d in plan['drops']:
        t = md.tables[d['table']]
        key = decode(t, d['key'])
        row = conn.execute(select(t).where(and_(t.c.subject == SUBJECT, t.c.run_id == d['from'],
                                                *[t.c[c] == v for c, v in key.items()]))).mappings().one()
        rows.append({'table': d['table'], 'row': encode(dict(row))})
    return rows


def r2_moves(plan):
    return [(m['object_key'], m['new_key'], m['size']) for m in plan['moves'] if 'new_key' in m]


def _head(storage, key):
    from botocore.exceptions import ClientError
    try:
        head = storage.client.head_object(Bucket=storage.bucket, Key=key)
    except ClientError as error:
        if error.response.get('Error', {}).get('Code') in ('404', 'NoSuchKey', 'NotFound'):
            return None
        raise
    return head['ContentLength'], head['ETag']


def copy_r2(plan, storage):
    """Copy each moved file to its new key; an object already there must be the same file (size and ETag)."""
    copied = 0
    for old, new, size in r2_moves(plan):
        source = _head(storage, old)
        if source is None or (size is not None and source[0] != size):
            raise Stop(f'R2 source missing or not the recorded file: {old}')
        if _head(storage, new) is None:
            storage.client.copy_object(Bucket=storage.bucket, Key=new, CopySource={'Bucket': storage.bucket, 'Key': old})
            copied += 1
        if not _same(_head(storage, new), source):
            raise Stop(f'R2 object at the new key is not the same file: {new}')
    return copied


def _same(a, b):
    """Same size and ETag; a multipart source's ETag ('…-N') is not the copy's MD5, so size decides there."""
    return a is not None and b is not None and a[0] == b[0] and (a[1] == b[1] or '-' in a[1] + b[1])


def check_r2(plan, storage):
    for old, new, size in r2_moves(plan):
        if not _same(_head(storage, new), _head(storage, old)):
            raise Stop(f'R2 object at the new key is missing or differs: {new} (run --copy-r2 first)')


# ------------------------------------------------------------------ the runner's files

def local_runs(runs, *, apply=False):
    """The runner keeps the 11-05 stable IDs in its folders, pairs, upload ledger and prestudy targets."""
    plan = []
    dirs = [runs / rid for rid in LOCAL_SWAP if (runs / rid).exists()]
    logs = [runs / f'agent.{rid}.log' for rid in LOCAL_SWAP if (runs / f'agent.{rid}.log').exists()]
    targets = []
    for p in sorted(runs.glob('25????_??/pre_target.json')):
        data = json.loads(p.read_text(encoding='utf-8'))
        if data.get('subject') == SUBJECT and data.get('run_id') in LOCAL_SWAP:
            targets.append((p, data['run_id']))
    pairs_path = runs / '_pairs' / f'{SUBJECT}.json'
    ledger_path = runs / 'published.json'
    plan = {'dirs': [p.name for p in dirs], 'logs': [p.name for p in logs],
            'pre_targets': [(p.parent.name, rid, LOCAL_SWAP[rid]) for p, rid in targets]}
    if not apply:
        return plan
    # Check everything before the first rename, so a stop leaves nothing half-moved (review 2026-11-11).
    backup = runs / '_development' / CHANGE.name / 'local-before'
    if backup.exists():
        raise Stop(f'backup already exists: {backup}')
    staged = [p.with_name('~' + p.name) for p in dirs + logs]
    if any(p.exists() for p in staged):
        raise Stop(f'staging names already exist: {[p.name for p in staged if p.exists()]}')
    for p, rid in targets:
        if f'"run_id": "{rid}"' not in p.read_text(encoding='utf-8'):
            raise Stop(f'{p} does not hold run_id {rid} in the expected form')
    backup.mkdir(parents=True)
    for p in [pairs_path, ledger_path, *[t for t, _ in targets], *logs]:
        if p.exists():
            dest = backup / p.relative_to(runs)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, dest)
    for group in (dirs, logs):
        for p in group:
            p.rename(p.with_name('~' + p.name))
        for p in group:
            rid = re.search(r'\d{6}_\d{2}', p.name).group()
            p.with_name('~' + p.name).rename(p.with_name(p.name.replace(rid, LOCAL_SWAP[rid])))
    for p, rid in targets:
        text = p.read_text(encoding='utf-8')
        new = text.replace(f'"run_id": "{rid}"', f'"run_id": "{LOCAL_SWAP[rid]}"', 1)
        assert new != text, p
        p.write_text(new, encoding='utf-8')
    if pairs_path.exists():
        pairs = json.loads(pairs_path.read_text(encoding='utf-8'))
        pairs = {LOCAL_SWAP.get(k, k): v for k, v in pairs.items()}
        pairs_path.write_text(json.dumps(pairs, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    if ledger_path.exists():
        ledger = json.loads(ledger_path.read_text(encoding='utf-8'))
        for api, lectures in ledger.get('apis', {}).items():
            ledger['apis'][api] = {(f'{SUBJECT}/{LOCAL_SWAP[k.split("/")[1]]}'
                                    if k.startswith(f'{SUBJECT}/') and k.split('/')[1] in LOCAL_SWAP else k): v
                                   for k, v in lectures.items()}
        ledger_path.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return plan


# ------------------------------------------------------------------ command line

def connect(database):
    if database == 'local':
        os.environ.update(ENVIRONMENT='local-test',
                          DATABASE_URL='sqlite:///' + (ROOT / 'server/local_test_data/studyez.db').as_posix())
    else:
        from dotenv import load_dotenv
        load_dotenv(Path(os.environ.get('STUDYEZ_ENV_ROOT', ROOT)) / 'server/.env', override=True)
    sys.path.insert(0, str(ROOT / 'server'))
    from app.database import engine
    from sqlalchemy import MetaData
    md = MetaData()
    md.reflect(bind=engine)
    return engine, md


def storage():
    sys.path.insert(0, str(ROOT / 'server'))
    from app.storage import ObjectStorage
    return ObjectStorage()


def prepare_candidate():
    """A data-only candidate (the tool, the emptied aliases, the change record) bound to the deploy approval."""
    sys.path.insert(0, str(ROOT / 'scripts'))
    import development as dev
    import release_evidence as release
    folder, state = dev.load(CHANGE.name)
    errors = dev.gate(folder, state, 'release')
    if errors:
        raise SystemExit('; '.join(errors))
    entries = [Path(__file__).resolve(), ROOT / 'data/timetable/identities/2026-2.json',
               ROOT / 'data/timetable/identities/2026-2-notes.json']
    candidate = {**dev.evidence(folder, state), 'config': {
        'target': 'lecture-renumber-data',
        'destination': 'StudyEZ production DB lecture tables of 12 감염과 면역 lectures, R2 copies, runs/ runner files',
        'rollback': '--reverse --previous-receipt; R2 originals kept; runs backup under runs/_development'},
        'files': {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in entries},
        'environment_files': ['server/.env'], 'environment_hash': release.environment_hash('server'),
        'release_hash': dev.digest([folder / 'release.md'])}
    token = release.value_hash(candidate)
    dest = ROOT / 'runs/_development' / CHANGE.name / 'candidates' / token
    for p in entries:
        target = dest / p.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            shutil.copyfile(p, target)
        assert target.read_bytes() == p.read_bytes()
    assert release.manifest(dest) == candidate['files']
    candidate.update(id=token, artifact=dest.relative_to(ROOT).as_posix())
    dev.update(folder, lambda st: st.update(candidate=candidate))
    return {'candidate': token, 'files': len(entries)}


def deploy_gate():
    sys.path.insert(0, str(ROOT / 'scripts'))
    import development as dev
    folder, state = dev.load(CHANGE.name)
    errors = dev.gate(folder, state, 'deploy')
    if errors:
        raise SystemExit('; '.join(errors))


def summary(plan):
    by = {}
    for m in plan['moves']:
        by.setdefault(m['table'], {}).setdefault(f"{m['from']}→{m['to']}", 0)
        by[m['table']][f"{m['from']}→{m['to']}"] += 1
    return {'plan_sha256': plan['sha256'], 'moves': by, 'drops': [(d['from'], d['filename']) for d in plan['drops']],
            'hidden': len(plan['hidden']), 'r2_copies': len(r2_moves(plan)),
            'mixed': [{k: j[k] for k in ('table', 'run_id', 'topic', 'why')} for j in plan['judged']]}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--database', choices=['production', 'local'], default='production')
    parser.add_argument('--copy-r2', action='store_true')
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--expect-plan')
    parser.add_argument('--reverse', action='store_true')
    parser.add_argument('--previous-receipt', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--local-runs', type=Path)
    parser.add_argument('--abandon-generation', action='append', default=[])
    parser.add_argument('--prepare', action='store_true')
    args = parser.parse_args()
    if args.prepare:
        print(json.dumps(prepare_candidate()))
        return
    if args.local_runs:
        if args.apply:
            deploy_gate()
        print(json.dumps(local_runs(args.local_runs, apply=args.apply), ensure_ascii=False, default=str, indent=1))
        return
    engine, md = connect(args.database)
    previous = json.loads(args.previous_receipt.read_text(encoding='utf-8')) if args.reverse else None

    def make(conn):
        return (reverse_plan(conn, md, previous) if args.reverse
                else build_plan(conn, md, abandon=tuple(args.abandon_generation)))

    if not args.apply:
        with engine.connect() as conn:
            plan = make(conn)
        if args.copy_r2:
            if args.database == 'production':
                deploy_gate()
            print(json.dumps({'copied': copy_r2(plan, storage()), 'objects': len(r2_moves(plan))}))
        else:
            print(json.dumps(summary(plan), ensure_ascii=False, default=str, indent=1))
        return
    if not args.output or args.output.exists():
        raise SystemExit('--apply needs a new --output receipt path')
    if not args.expect_plan:
        raise SystemExit('--apply needs --expect-plan: print the plan first (also for --reverse)')
    if args.database == 'production':
        deploy_gate()
    with engine.connect() as conn:
        preview = make(conn)
    if preview['sha256'] != args.expect_plan:
        raise SystemExit(f'plan changed since review: {preview["sha256"]}')
    if args.database == 'production':
        check_r2(preview, storage())  # before the lock: ~150 R2 calls must not hold site writes
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with engine.begin() as conn:
        lock(conn, md)
        plan = make(conn)  # the plan applied is the one read under the lock
        if plan['sha256'] != args.expect_plan:
            raise Stop(f'plan changed while taking the lock: {plan["sha256"]}')
        dropped = dropped_rows(conn, md, plan)
        result = apply_plan(conn, md, plan)
        receipt = {**result, 'plan': plan, 'dropped_rows': dropped, 'reverse': args.reverse,
                   'at': datetime.now(timezone.utc).isoformat(), 'committed': False}
        # Written before the commit, so a committed change always has its receipt (review 2026-11-11).
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(json.dumps(receipt, ensure_ascii=False, indent=1, default=str) + '\n')
            f.flush()
            os.fsync(f.fileno())
    receipt['committed'] = True
    args.output.write_text(json.dumps(receipt, ensure_ascii=False, indent=1, default=str) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in result.items() if k != 'outside'}, ensure_ascii=False))


if __name__ == '__main__':
    main()

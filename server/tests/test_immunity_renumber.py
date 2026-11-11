"""Isolated swap, mixed-pair sorting, stop conditions and receipt rollback (docs/changes/2026-11-11-immunity-renumber)."""
from datetime import date, datetime, timezone
import json
import os
from pathlib import Path
import sys
import tempfile

TMP = Path(tempfile.mkdtemp(prefix='studyez-renumber-'))
ROOT = Path(__file__).resolve().parents[2]
os.environ.update(ENVIRONMENT='local-test', DATABASE_URL=f"sqlite:///{(TMP / 'test.db').as_posix()}")
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'server'))

from app.database import Base, engine
import app.models  # noqa: F401  (registers every table)
from sqlalchemy import Boolean, Date, DateTime, Integer, JSON, MetaData, event as sa_event, insert, select, update
import immunity_renumber as r


@sa_event.listens_for(engine, 'connect')
def _foreign_keys(dbapi, _):
    # Production enforces the lecture FKs (ON DELETE CASCADE); the staging rows must be empty when deleted.
    dbapi.execute('PRAGMA foreign_keys=ON')

S = r.SUBJECT
BEFORE = datetime(2026, 11, 4, 12, 0, tzinfo=timezone.utc)
AFTER = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)
# topic, current cell (date, start), stored run ID (11-05 stable) — the production shape on 2026-11-11
LECTURES = {
    '렙토스피라, 매독균, 보렐리아(김현제)': ('2026-11-10', '09:00', '261105_05'),
    '콜레라, 캄필로박터, 수도모나스(방예지)': ('2026-11-05', '13:00', '261110_01'),
    '헤르페스바이러스과(김현제)': ('2026-11-13', '09:00', '261110_02'),
    '아데노바이러스, 폭스바이러스(방예지)': ('2026-11-10', '10:00', '261113_01'),
    '신종 감염병에 대한 대처와 전망(박상원)': ('2026-11-19', '14:00', '261118_01'),
    '의료관련감염(김의석)': ('2026-11-18', '09:00', '261119_06'),
    '감염병의 예방(신수)': ('2026-11-19', '15:00', '261119_05'),
    '형성평가와 피드백(박완범)': ('2026-11-19', '13:00', '261119_07'),
    '호산구성 질환(김세훈)': ('2026-11-26', '13:00', '261126_03'),
    '다양한 알레르기질환(양민석)': ('2026-11-26', '11:00', '261126_05'),
}


def fill(table, **given):
    """A row with every required column: the given values plus a neutral value of the column's type."""
    row = dict(given)
    for c in table.c:
        if c.name in row or c.nullable or c.default is not None or c.server_default is not None or c.autoincrement is True:
            continue
        t = c.type
        row[c.name] = (False if isinstance(t, Boolean) else 0 if isinstance(t, Integer) else
                       BEFORE if isinstance(t, DateTime) else date(2026, 11, 1) if isinstance(t, Date) else
                       {} if isinstance(t, JSON) else 'x')
    return row


def put(conn, name, **values):
    t = Base.metadata.tables[name]
    conn.execute(insert(t).values(**fill(t, **values)))


def event(conn, eid, day, start, details):
    put(conn, 'timetable_event', id=eid, date=date.fromisoformat(day), start_time=start, end_time=start,
        title='감염과 면역', details=details, category='lecture', slot=int(start[:2]) - 8)


def lecture(conn, run_id, title, eid, day, start):
    put(conn, 'lecture', subject=S, run_id=run_id, uid=f'{run_id}#{title}', title=title, timetable_event_id=eid,
        date=date.fromisoformat(day), slot=int(start[:2]) - 8, slot_end=int(start[:2]) - 8, start_time=start,
        professors=[], match_confirmed=True)


def asset(conn, run_id, kind, filename, size=10):
    put(conn, 'asset', id=f'{run_id}-{kind}-{filename}', subject=S, run_id=run_id, kind=kind, filename=filename,
        object_key=f'lectures/{S}/{run_id}/{kind}/{filename}', size_bytes=size, content_type='application/pdf',
        uploaded_at=BEFORE)


def items(conn, run_id, stems):
    for i, stem in enumerate(stems):
        put(conn, 'pre_item', subject=S, run_id=run_id, item_id=f'c{i:03d}', ord=i, stem=stem, answer='a')


def seed():
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        for n, (title, (day, start, rid)) in enumerate(LECTURES.items()):
            event(conn, f'e{n}', day, start, title)
            lecture(conn, rid, title, f'e{n}', day, start)
            asset(conn, rid, 'jokbo', f'2026-족보-{title[:4]}.pdf')
        # 미코플라스마·무산소: the 11-08 note with the new number reached the old row (title, notes, deck), while
        # the cell link, questions, 족보 and first deck images still follow the 11-05 stable ID.
        event(conn, 'e-miko', '2026-11-05', '14:00', '미생물학) 미코플라스마, 클라미디아 김동현')
        event(conn, 'e-anae', '2026-11-06', '14:00', '미생물학) 무산소성세균 염진기')
        lecture(conn, '261105_06', '미코플라즈마, 클라미디아(김동현)', 'e-anae', '2026-11-05', '14:00')
        lecture(conn, '261106_06', '무산소세균(염진기)', 'e-miko', '2026-11-06', '14:00')
        for rid, mine, other in (('261105_06', ('미코플라즈마, 클라미디아(김동현)', '251107_06', '2026-S13-족보-염진기.pdf'), '251106_06'),
                                 ('261106_06', ('무산소세균(염진기)', '251106_06', '2026-S17-족보-김동현.pdf'), '251107_06')):
            asset(conn, rid, 'notes_current', f'[{rid}]{mine[0]}_학생v1.pdf')
            asset(conn, rid, 'pre_apkg', f'[x] 미생물학) {mine[0]} 예습.apkg')
            asset(conn, rid, 'jokbo', mine[2])
            asset(conn, rid, 'media', f'{mine[1]}_s008.png', size=len(mine[1]) + int(mine[1][5]))   # the deck rebuilt on 11-08
            asset(conn, rid, 'media', f'{other}_s008.png', size=len(other) + int(other[5]))     # the first deck's images
            put(conn, 'preview', subject=S, run_id=rid, provider='chatgpt', updated_at=BEFORE)
        items(conn, '261105_06', ['절대무산소균이 산소에 노출되면?', 'Clostridium의 아포는?'])
        items(conn, '261106_06', ['Mycoplasma의 세포벽은?', '클라미디아의 생활사는?'])
        put(conn, 'user_review', user_id='u2', subject=S, run_id='261106_06', provider='chatgpt', updated_at=AFTER)
        put(conn, 'user_preview', user_id='u1', subject=S, run_id='261105_06', provider='chatgpt', updated_at=BEFORE)
        # learning records, a Main-Quiz generation and a hidden lecture on a swapped pair
        items(conn, '261113_01', ['아데노바이러스의 유전체는?'])
        put(conn, 'quiz_attempt', user_id='u1', subject=S, run_id='261113_01', item_id='c000', answered_at=BEFORE)
        put(conn, 'root_generation', id='g1', job_id=1, subject=S, run_id='261113_01', user_id='u1', request_id='q1',
            input_digest='d', packet={'runId': '261113_01'}, baseline='b', result={'ok': True})
        put(conn, 'study_hidden_lecture', user_id='u1', lecture_key=f'{S}/261113_01')
        # an unrelated lecture of the same subject and one of another subject: never touched
        event(conn, 'e-other', '2026-11-03', '09:00', '리케차')
        lecture(conn, '261103_01', '리케차', 'e-other', '2026-11-03', '09:00')
        asset(conn, '261103_01', 'jokbo', 'other.pdf')
        put(conn, 'lecture', subject='병리학', run_id='261113_01', uid='p', title='병리', professors=[])


def dump():
    md = MetaData()
    md.reflect(bind=engine)
    with engine.connect() as conn:
        return {n: sorted(r.fingerprint(r.encode(dict(x))) for x in conn.execute(select(t)).mappings())
                for n, t in md.tables.items()}


def reflect():
    md = MetaData()
    md.reflect(bind=engine)
    return md


def one(conn, sql, **kw):
    return conn.exec_driver_sql(sql, tuple(kw.values()) if kw else ()).all()


def main():
    seed()
    original = dump()
    md = reflect()
    with engine.connect() as conn:
        plan = r.build_plan(conn, md)
    assert {(m['from'], m['to']) for m in plan['moves'] if m['table'] == 'lecture'} == set()
    assert sorted(d['filename'] for d in plan['drops']) == ['251106_06_s008.png', '251107_06_s008.png']
    late = TMP / 'late.db'
    with engine.begin() as conn:  # a row written after the plan was read stops the apply
        put(conn, 'user_preview', user_id='late', subject=S, run_id='261113_01', provider='chatgpt', updated_at=AFTER)
    try:
        with engine.begin() as conn:
            r.apply_plan(conn, md, plan)
        raise RuntimeError('a row the plan never saw was left behind')
    except r.Stop as exc:
        assert 'changed since the plan' in str(exc)
    with engine.begin() as conn:
        conn.execute(md.tables['user_preview'].delete().where(md.tables['user_preview'].c.user_id == 'late'))
    assert dump() == original and not late.exists()
    print('PASS a row written after the plan stops the apply')
    with engine.begin() as conn:
        dropped = r.dropped_rows(conn, md, plan)
        result = r.apply_plan(conn, md, plan)
    assert result['applied']
    with engine.connect() as conn:
        lec = {x['run_id']: x for x in conn.execute(select(md.tables['lecture']).where(
            md.tables['lecture'].c.subject == S)).mappings()}
        ev = {x['id']: x for x in conn.execute(select(md.tables['timetable_event'])).mappings()}
        for rid, x in lec.items():
            assert r.key_of(ev[x['timetable_event_id']]) == rid, rid
        assert lec['261110_02']['title'].startswith('아데노') and lec['261113_01']['title'].startswith('헤르페스')
        assert lec['261110_02']['uid'].startswith('261110_02#')
        assert lec['261105_06']['title'].startswith('미코') and lec['261105_06']['timetable_event_id'] == 'e-miko'
        A = md.tables['asset']
        files = {rid: sorted(x['filename'] for x in conn.execute(select(A).where(A.c.run_id == rid)).mappings())
                 for rid in ('261105_06', '261106_06')}
        assert files['261105_06'] == ['2026-S17-족보-김동현.pdf', '251107_06_s008.png',
                                      '[261105_06]미코플라즈마, 클라미디아(김동현)_학생v1.pdf',
                                      '[x] 미생물학) 미코플라즈마, 클라미디아(김동현) 예습.apkg'], files
        assert all('251106_06' in f or '무산소' in f or '염진기' in f for f in files['261106_06']), files
        keys = [x[0] for x in conn.execute(select(A.c.object_key).where(A.c.subject == S, A.c.run_id == '261110_02'))]
        assert keys and all(k.startswith(f'lectures/{S}/261110_02/') for k in keys)
        P = md.tables['pre_item']
        assert [x[0] for x in conn.execute(select(P.c.stem).where(P.c.run_id == '261105_06'))][0].startswith('Mycoplasma')
        assert [x[0] for x in conn.execute(select(P.c.stem).where(P.c.run_id == '261110_02'))] == ['아데노바이러스의 유전체는?']
        Q = md.tables['quiz_attempt']
        assert [x[0] for x in conn.execute(select(Q.c.run_id))] == ['261110_02']
        assert [x[0] for x in conn.execute(select(md.tables['root_generation'].c.run_id))] == ['261110_02']
        assert [x[0] for x in conn.execute(select(md.tables['study_hidden_lecture'].c.lecture_key))] == [f'{S}/261110_02']
        U = md.tables['user_review']
        assert [x[0] for x in conn.execute(select(U.c.run_id))] == ['261106_06']  # after the overwrite: the row it saw
        assert not conn.execute(select(md.tables['lecture']).where(md.tables['lecture'].c.run_id.like('~%'))).all()
    print('PASS apply: 12 lectures on their current numbers, mixed pair sorted by content, records follow their topic')

    with engine.connect() as conn:
        try:
            r.build_plan(conn, md)
            raise RuntimeError('a second run would swap the lectures back')
        except r.Stop as exc:
            assert 'already renumbered' in str(exc)
    print('PASS a second run stops instead of swapping back')

    receipt = json.loads(json.dumps({'plan': plan, 'dropped_rows': dropped}, ensure_ascii=False, default=str))
    UP = md.tables['user_preview']
    with engine.begin() as conn:  # a student opens 아데노 (now 261110_02) after the renumber
        put(conn, 'user_preview', user_id='since', subject=S, run_id='261110_02', provider='chatgpt', updated_at=AFTER)
    with engine.begin() as conn:
        back = r.reverse_plan(conn, md, receipt)
        r.apply_plan(conn, md, back)
    with engine.begin() as conn:
        assert [x[0] for x in conn.execute(select(UP.c.run_id).where(UP.c.user_id == 'since'))] == ['261113_01']
        conn.execute(UP.delete().where(UP.c.user_id == 'since'))
    assert dump() == original
    print('PASS receipt rollback restores every row byte for byte')

    G, J = md.tables['root_generation'], md.tables['prequiz_job']
    with engine.begin() as conn:
        conn.execute(update(G).values(result=None))
        put(conn, 'prequiz_job', id=1, subject=S, run_id='261113_01', kind='bank', state='running')
    for state, words in (('running', 'still open'), ('failed', 'could still be resumed')):
        with engine.begin() as conn:
            conn.execute(update(J).values(state=state))
        try:
            with engine.connect() as conn:
                r.build_plan(conn, md)
            raise RuntimeError(f'a {state} generation was moved')
        except r.Stop as exc:
            assert words in str(exc), exc
    with engine.connect() as conn:
        assert r.build_plan(conn, md, abandon=('g1',))['abandoned_generations'] == ['g1']
    with engine.begin() as conn:
        conn.execute(update(G).values(result={'ok': True}))
        put(conn, 'asset', id='odd', subject=S, run_id='261105_06', kind='media', filename='unknown.png',
            object_key=f'lectures/{S}/261105_06/media/unknown.png', size_bytes=1, uploaded_at=BEFORE)
    try:
        with engine.connect() as conn:
            r.build_plan(conn, md)
        raise RuntimeError('an undecided mixed-pair row was moved')
    except r.Stop as exc:
        assert 'undecided' in str(exc)
    print('PASS a running or resumable generation, or an undecided row, stops before any write')

    before = dump()
    bad = json.loads(json.dumps(plan, ensure_ascii=False, default=str))
    bad['moves'][0]['key'] = {k: 'missing' for k in bad['moves'][0]['key']}
    with engine.begin() as conn:
        conn.execute(md.tables['asset'].delete().where(md.tables['asset'].c.id == 'odd'))
    before = dump()
    try:
        with engine.begin() as conn:
            r.apply_plan(conn, md, bad)
        raise RuntimeError('a stale plan was applied')
    except r.Stop:
        pass
    assert dump() == before
    print('PASS a stale plan rolls back the whole transaction')

    runs = TMP / 'runs'
    for rid in ('261105_05', '261110_01', '261113_01'):
        (runs / rid).mkdir(parents=True)
        (runs / rid / 'BUILDING').write_text(rid, encoding='utf-8')
        (runs / f'agent.{rid}.log').write_text(rid, encoding='utf-8')
    (runs / '251114_01').mkdir()
    (runs / '251114_01/pre_target.json').write_text(json.dumps({'subject': S, 'run_id': '261113_01'}), encoding='utf-8')
    (runs / '251114_01/HOLD').write_text('사람 메모', encoding='utf-8')
    (runs / '_pairs').mkdir()
    (runs / f'_pairs/{S}.json').write_text(json.dumps({'261105_05': '251110_02', '261103_01': '251104_01'}), encoding='utf-8')
    (runs / 'published.json').write_text(json.dumps({'apis': {'a': {f'{S}/261113_01': {'f': 1}, f'{S}/261103_01': {}}}}),
                                         encoding='utf-8')
    r.local_runs(runs, apply=True)
    assert (runs / '261110_02/BUILDING').read_text(encoding='utf-8') == '261113_01'
    assert (runs / 'agent.261110_01.log').read_text(encoding='utf-8') == '261105_05'
    assert json.loads((runs / '251114_01/pre_target.json').read_text(encoding='utf-8'))['run_id'] == '261110_02'
    assert (runs / '251114_01/HOLD').read_text(encoding='utf-8') == '사람 메모'
    assert json.loads((runs / f'_pairs/{S}.json').read_text(encoding='utf-8')) == {'261110_01': '251110_02', '261103_01': '251104_01'}
    assert set(json.loads((runs / 'published.json').read_text(encoding='utf-8'))['apis']['a']) == {f'{S}/261110_02', f'{S}/261103_01'}
    assert (runs / '_development' / r.CHANGE.name / 'local-before/published.json').exists()
    print('PASS runner files swap with a backup and keep hand-made files')


if __name__ == '__main__':
    main()

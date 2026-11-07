"""관리자 화면이 3초마다 치는 generation GET이 그 강의의 모든 판을 적재하지 않는다."""
from datetime import UTC, datetime, timedelta
from tests.root_support import setup, ADMIN
client, user, SessionLocal = setup()
from sqlalchemy import event, select
from app.database import engine
from app.models import PrequizJob
from app.models.root_generation import RootGeneration

GENERATIONS = 5
START = datetime(2026, 11, 3, 1, tzinfo=UTC)


def result_of(count):
    review = lambda i: {'question_id': f'Q{i:03d}', 'verdict': 'doubt', 'note': 'synthetic note'}
    return {'manifest': {'repairRounds': 2},
            'document': {'tasks': [{'id': f'T{i:03d}'} for i in range(count)]},
            'brief': {'targets': [{'id': f'P{i:03d}'} for i in range(count)]},
            'sourceAudit': {'input_issues': ['synthetic issue'],
                            'question_checks': {'reviews': [review(0)]},
                            'review': {'coverage': [{'point_id': 'P000', 'status': 'covered', 'reason': ''}]}},
            'medical': {'reviews': [review(1)]},
            'validation': {'errors': [], 'warnings': ['synthetic warning']}}


def add(index, *, result=None, digest=None):
    with SessionLocal() as db:
        job = PrequizJob(subject='test', run_id='demo', kind='bank', state='running', stage='출제', message='')
        db.add(job); db.flush()
        db.add(RootGeneration(id=f'{index:032d}', job_id=job.id, subject='test', run_id='demo', user_id='admin',
            request_id=f'req-{index}', input_digest=f'{index:064d}', baseline='b' * 64,
            packet={'revision': f'r{index}', 'privatePilot': True, 'conceptMap': 'map', 'points': 'points',
                    'scope': 'scope', 'examDate': None, 'inputMode': 'source', 'authoring': 'web'},
            result=result, result_digest=digest, created_at=START + timedelta(minutes=index)))
        db.commit()


statements = []
event.listen(engine, 'before_cursor_execute',
    lambda conn, cursor, statement, parameters, context, executemany: statements.append(statement))


def poll():
    statements.clear()
    user('admin', True)
    response = client.get(ADMIN + '/generation')
    assert response.status_code == 200, response.text
    return response.json()['generation']


def generation_selects():
    return [s for s in statements if 'FROM root_generation' in s and s.lstrip().upper().startswith('SELECT')]


# 오래된 판들은 result를 싣고, 가장 최근 판은 아직 출제 중이다.
for index in range(GENERATIONS - 1):
    add(index, result=result_of(40), digest=f'{index:064d}')
add(GENERATIONS - 1)

with SessionLocal() as db:
    assert len(db.scalars(select(RootGeneration).where(RootGeneration.subject == 'test',
        RootGeneration.run_id == 'demo')).all()) == GENERATIONS

job = poll()
# 가장 최근 판을 준다.
assert job['id'] == f'{GENERATIONS - 1:032d}', job['id']
assert job['revision'] == f'r{GENERATIONS - 1}'
assert job['report'] is None and job['published'] is False
# 폴링이 쓰는 필드는 그대로 있다.
for field in ('state', 'stage', 'message', 'published', 'input', 'awaitingWeb', 'privatePilot', 'featureEnabled'):
    assert field in job, field
assert job['input'] == {'conceptMap': 'map', 'points': 'points', 'scope': 'scope',
                        'examDate': None, 'inputMode': 'source'}

# 판이 다섯 개여도 한 판만 고르는 질의여야 한다.
selects = generation_selects()
assert len(selects) == 1, selects
assert 'LIMIT' in selects[0].upper(), selects[0]

# 가장 최근 판에 result가 있으면 report를 그대로 만든다.
add(GENERATIONS, result=result_of(7), digest=f'{GENERATIONS:064d}')
job = poll()
assert job['id'] == f'{GENERATIONS:032d}'
assert job['published'] is True
assert job['report'] == {'repairRounds': 2, 'taskCount': 7, 'targetCount': 7,
    'issues': ['synthetic issue', 'synthetic warning'],
    'questionNotes': [{'source': '원본 대조', 'question_id': 'Q000', 'verdict': 'doubt', 'note': 'synthetic note'},
                      {'source': '독립 정답 검수', 'question_id': 'Q001', 'verdict': 'doubt', 'note': 'synthetic note'}],
    'coverage': [{'point_id': 'P000', 'status': 'covered', 'reason': ''}]}, job['report']
selects = generation_selects()
assert len(selects) == 1 and 'LIMIT' in selects[0].upper(), selects

print('root generation poll: bounded query and preserved fields')

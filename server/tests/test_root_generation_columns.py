"""관리자 generation 폴링이 큰 JSON(result·web_dispatch·web_response)을 끌어오지 않고, 응답은 그대로다.

운영(Supabase)에서는 2.5MB result를 매 폴링 끌어오는 비용이 2초대로 보였다. 격리 SQLite에서는
그 지연이 재현되지 않으므로, 이 검사는 지연 대신 **SELECT 결과 칼럼**을 본다.
응답 동일성은 수정 전 `public_job`의 사본(아래 legacy_*)을 전체 행에 돌린 값과 비교한다.
"""
from datetime import UTC, datetime, timedelta
from tests.root_support import setup
client, user, SessionLocal = setup()
from fastapi import HTTPException
from sqlalchemy import event, update
from app.database import engine
from app.models import PrequizJob
from app.models.root_generation import RootGeneration
from app.root_learning.content import globally_enabled
from app.routes.root_generation import generation_input

HEAVY = {'result', 'web_dispatch', 'web_response'}
START = datetime(2026, 11, 3, 1, tzinfo=UTC)
UNSET = object()


# ── 수정 전 코드의 사본(cc67288b root_generation.py) — 기준값 계산용. 바꾸지 않는다. ──
def legacy_canonical(db, row):
    seen = set()
    while row.packet.get('supersededBy'):
        if row.id in seen: raise HTTPException(409, '중복 작업 연결을 확인해야 합니다.')
        seen.add(row.id)
        prior = db.get(RootGeneration, row.packet['supersededBy'])
        if (prior is None or prior.user_id != row.user_id or prior.packet['privatePilot'] != row.packet['privatePilot']
            or generation_input(prior.packet) != generation_input(row.packet)
            or (prior.created_at, prior.id) >= (row.created_at, row.id)):
            raise HTTPException(409, '중복 작업의 입력·소유자가 다릅니다.')
        row = prior
    return row


def legacy_public_job(db, row):
    row = legacy_canonical(db, row)
    job = db.get(PrequizJob, row.job_id)
    report = None
    if row.result:
        result = row.result
        if result.get('policy') in ('verified-main-quiz-replacement/1', 'verified-main-quiz-curation/1'):
            from app.root_learning.replacement_import import report as replacement_report
            report = replacement_report(result)
        else: report = {'repairRounds': result['manifest']['repairRounds'], 'taskCount': len(result['document']['tasks']),
            'targetCount': len(result['brief']['targets']),
            'issues': result['sourceAudit']['input_issues'] + result['validation']['errors'] + result['validation']['warnings'],
            'questionNotes': [{'source': label, **r} for label, checks in [('원본 대조', result['sourceAudit']['question_checks']), ('독립 정답 검수', result['medical'])]
                for r in checks['reviews'] if r['verdict'] != 'ok'],
            'coverage': result['sourceAudit']['review']['coverage']}
    return {'id': row.id, 'requestId': row.request_id, 'jobId': row.job_id, 'state': job.state, 'stage': job.stage, 'message': job.message,
            'published': row.result_digest is not None, 'revision': row.packet['revision'],
            'privatePilot': row.packet['privatePilot'], 'featureEnabled': globally_enabled(),
            'createdAt': row.created_at.isoformat(),
            'input': {**{k: row.packet[k] for k in ('conceptMap', 'points', 'scope')},
                'examDate': row.packet.get('requestedExamDate', row.packet['examDate']),
                'inputMode': row.packet.get('inputMode', 'provided')}, 'report': report,
            'authoring': row.packet.get('authoring', 'cli'), 'parallelAuthoring': row.packet.get('parallelAuthoring', False), 'awaitingWeb': row.packet.get('authoring') == 'web' and not row.web_response and job.state == 'held' and not job.cancel_requested and job.stage == 'ChatGPT 응답 대기',
            'dispatched': bool(row.web_dispatch),
            # map-tree/1 (2026-11-09): request kind, frozen source names and resume count; packet only, no heavy column.
            'pipeline': row.packet.get('pipeline'), 'sources': [{k: s[k] for k in ('id', 'kind', 'filename')} for s in row.packet.get('sources', [])],
            'operatorResumes': len(row.packet.get('operatorResumes', [])),
            # 「새로 출제」 (2026-11-11-main-quiz-start-over): the request this one restarts; packet only.
            'restartOf': row.packet.get('restartOf')}
# ── 사본 끝 ──


def legacy_latest(run_id):
    with SessionLocal() as db:
        row = db.query(RootGeneration).filter_by(subject='test', run_id=run_id).order_by(RootGeneration.created_at.desc()).first()
        return legacy_public_job(db, row)


def legacy_result(count, tag='synthetic'):
    review = lambda i, verdict: {'question_id': f'Q{i:03d}', 'verdict': verdict, 'note': tag}
    return {'manifest': {'repairRounds': 2},
            'document': {'tasks': [{'id': f'T{i:03d}', 'pad': 'x' * 2000} for i in range(count)]},
            'brief': {'targets': [{'id': f'P{i:03d}'} for i in range(count)]},
            'sourceAudit': {'input_issues': [tag + ' issue'],
                            'question_checks': {'reviews': [review(0, 'doubt'), review(1, 'ok')]},
                            'review': {'coverage': [{'point_id': 'P000', 'status': 'covered', 'reason': ''}]}},
            'medical': {'reviews': [review(2, 'wrong')]},
            'validation': {'errors': ['e1'], 'warnings': [tag + ' warning']}}


def replacement_result(policy='verified-main-quiz-replacement/1'):
    source = {'reviews': [
        {'question_id': 'Q001', 'source_verdict': 'ok', 'goal_verdict': 'doubt', 'importance_verdict': 'ok', 'reason': 'goal'},
        {'question_id': 'Q002', 'source_verdict': 'ok', 'goal_verdict': 'ok', 'importance_verdict': 'doubt', 'reason': 'imp'}],
        'coverage_findings': ['finding']}
    medical = {'reviews': [{'question_id': 'Q003', 'verdict': 'wrong', 'note': 'm', 'suggested_answer': 'x'},
                           {'question_id': 'Q004', 'verdict': 'ok', 'note': '', 'suggested_answer': ''}]}
    body = {'rounds': [{'sourceReview': {'reviews': []}, 'medicalReview': {'reviews': []}},
                       {'sourceReview': source, 'medicalReview': medical}]}
    document = {'tasks': [{'id': 'T1'}, {'id': 'T2'}], 'review': {'targets': [{'id': 'P1'}], 'coverage': [{'point_id': 'P1'}]}}
    if policy == 'verified-main-quiz-curation/1':
        return {'policy': policy, 'repairRounds': 1, 'document': document, 'approval': {'scope_limits': ['limit']},
                'candidate': body}
    return {'policy': policy, 'repairRounds': 3, 'document': document, **body}


def packet(run_id, revision, **extra):
    return {'subject': 'test', 'runId': run_id, 'title': 't', 'revision': revision, 'privatePilot': True,
            'conceptMap': 'map', 'points': 'points', 'scope': 'scope', 'examDate': '2026-11-20',
            'inputMode': 'source', 'authoring': 'web', 'sources': [], **extra}


serial = iter(range(10 ** 6))


def add(run_id, *, minutes, state='running', stage='출제', result=UNSET, digest=None,
        web_dispatch=UNSET, web_response=UNSET, cancel=False, **extra):
    """UNSET은 칼럼을 넘기지 않는다(SQL NULL). None을 넘기면 ORM이 JSON null로 쓴다."""
    n = next(serial)
    with SessionLocal() as db:
        job = PrequizJob(subject='test', run_id=run_id, kind='bank', state=state, stage=stage, message='m',
                         cancel_requested=cancel)
        db.add(job); db.flush()
        values = {'result': result, 'web_dispatch': web_dispatch, 'web_response': web_response}
        db.add(RootGeneration(id=f'{n:032x}', job_id=job.id, subject='test', run_id=run_id, user_id='admin',
            request_id=f'req-{n}', input_digest=f'{n:064x}', baseline='b' * 64,
            packet=packet(run_id, f'r{n}', **extra), result_digest=digest,
            created_at=START + timedelta(minutes=minutes), **{k: v for k, v in values.items() if v is not UNSET}))
        db.commit()
        return f'{n:032x}'


reads = []


def record(conn, cursor, statement, parameters, context, executemany):
    if 'root_generation' in statement and statement.lstrip().upper().startswith('SELECT') and cursor.description:
        names = {d[0].removeprefix('root_generation_') for d in cursor.description}
        reads.append(names & HEAVY)


event.listen(engine, 'after_cursor_execute', record)


def poll(run_id):
    reads.clear()
    user('admin', True)
    response = client.get(f'/api/admin/root-learning/lectures/test/{run_id}/generation')
    assert response.status_code == 200, response.text
    return response.json()['generation'], [r for r in reads if r]


def check(run_id, *, first_reads=(), label=''):
    """같은 응답, 첫 폴링에서 허용된 큰 칼럼만, 두 번째 폴링에서는 큰 칼럼 0."""
    expected = legacy_latest(run_id)
    job, heavy = poll(run_id)
    assert job == expected, (label, job, expected)
    assert heavy == [set(c) for c in first_reads], (label, 'first poll heavy columns', heavy)
    job, heavy = poll(run_id)
    assert job == expected, (label, 'second poll', job)
    assert heavy == [], (label, 'second poll heavy columns', heavy)
    return job


# 1. 출제 중, 웹 응답 대기 — 큰 칼럼이 모두 SQL NULL
add('s1', minutes=0, state='held', stage='ChatGPT 응답 대기')
job = check('s1', label='waiting web, SQL NULL')
assert job['awaitingWeb'] is True and job['dispatched'] is False and job['report'] is None

# 2. JSON null과 {} — Python bool로는 거짓
add('s2', minutes=0, state='held', stage='ChatGPT 응답 대기', result=None, web_dispatch={}, web_response=None)
job = check('s2', label='JSON null / empty dict')
assert job['awaitingWeb'] is True and job['dispatched'] is False and job['report'] is None

# 3. 전송·응답 기록이 있는 판(웹 응답 원문이 크다)
add('s3', minutes=0, state='held', stage='ChatGPT 응답 대기',
    web_dispatch={'promptVersion': '1.2', 'promptHash': 'a' * 64, 'sourceSnapshots': ['s' * 50000]},
    web_response={'responseFile': 'r.md', 'raw': 'x' * 200000})
job = check('s3', label='dispatched + responded')
assert job['awaitingWeb'] is False and job['dispatched'] is True

# 4. 취소 요청된 웹 대기 판
add('s4', minutes=0, state='held', stage='ChatGPT 응답 대기', cancel=True)
assert check('s4', label='cancel requested')['awaitingWeb'] is False

# 5. 게시된 판(기존 report). 오래된 판들 위에 최신 판이 있다.
for minutes in range(3):
    add('s5', minutes=minutes, state='done', stage='완료', result=legacy_result(30, 'old'), digest=f'{minutes:064x}')
latest5 = add('s5', minutes=10, state='done', stage='완료', result=legacy_result(300), digest='5' * 64,
              web_dispatch={'promptVersion': '1.2', 'promptHash': 'a' * 64}, web_response={'raw': 'y' * 1000})
job = check('s5', first_reads=[{'result'}], label='published legacy report')
assert job['published'] is True and job['report']['taskCount'] == 300 and job['dispatched'] is True

# 6. 대체판·큐레이션 정책 report
add('s6', minutes=0, state='done', stage='완료', result=replacement_result(), digest='6' * 64,
    web_dispatch={'policy': 'verified-main-quiz-replacement/1', 'sourceSnapshots': ['z' * 50000]})
assert check('s6', first_reads=[{'result'}], label='replacement report')['report']['repairRounds'] == 3
add('s7', minutes=0, state='done', stage='완료', result=replacement_result('verified-main-quiz-curation/1'), digest='7' * 64)
assert check('s7', first_reads=[{'result'}], label='curation report')['report']['issues'] == ['limit']

# 7. 중복 사슬: 최신 판이 이전 판을 가리키면 이전 판의 값을 준다(이전 판도 큰 칼럼을 안 읽는다)
prior = add('s8', minutes=0, state='done', stage='완료', result=legacy_result(12, 'prior'), digest='8' * 64,
            web_dispatch={'promptVersion': '1.2', 'promptHash': 'b' * 64}, web_response={'raw': 'p' * 5000})
add('s8', minutes=5, state='canceled', stage='중복 요청 보존', web_response={'raw': 'dup' * 5000}, supersededBy=prior)
job = check('s8', first_reads=[{'result'}], label='superseded chain')
assert job['id'] == prior and job['report']['taskCount'] == 12 and job['dispatched'] is True

# 8. 같은 판의 digest가 바뀌면(정상 경로로는 생기지 않는다) report를 다시 계산한다
with SessionLocal() as db:
    db.execute(update(RootGeneration).where(RootGeneration.id == latest5).values(result=legacy_result(4, 'changed'), result_digest='9' * 64))
    db.commit()
job = check('s5', first_reads=[{'result'}], label='digest changed')
assert job['report']['taskCount'] == 4 and job['report']['issues'] == ['changed issue', 'e1', 'changed warning']

# 9. result는 있는데 digest가 없는 행은 캐시하지 않고 매번 계산한다(현재 코드로는 생기지 않는 옛 모양)
add('s9', minutes=0, state='failed', stage='실패', result=legacy_result(3))
expected = legacy_latest('s9')
for _ in range(2):
    job, heavy = poll('s9')
    assert job == expected and job['published'] is False and job['report']['taskCount'] == 3
    assert heavy == [{'result'}], heavy

print('root generation columns: polling skips large JSON, responses unchanged')

"""Root-learning product API. Legacy question and learner tables are read-only here."""
import copy
from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from studyez_contracts.roots import document_hash
from app.auth import CurrentUser, require_admin, require_approved_user
from app.database import get_db
from app.models import Lecture
from app.models.root_learning import RootContent, RootControl, RootSession, RootEvent
from app.root_learning import content, policy, state, planning

router = APIRouter()
BASE = '/root-learning/lectures/{subject}/{run_id}'


def now():
    return datetime.now(UTC)


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Start(Strict):
    requestId: str = Field(pattern=r'^[A-Za-z0-9_-]{1,64}$')


class Action(Start):
    version: int = Field(ge=0)
    kind: Literal['reveal', 'rate', 'skip', 'map', 'undo']
    attempted: bool = False
    response: str = Field(default='', max_length=10000)
    helped: bool = False
    grade: Literal['missed', 'partial', 'independent'] = 'missed'
    stimulusHashes: list[str] = Field(default_factory=list,max_length=64)


class Publication(Strict):
    revision: str = Field(pattern=r'^[A-Za-z0-9_-]{1,64}$')
    reviewed: bool
    enabled: bool
    allowedUsers: list[str] = Field(default_factory=list, max_length=1000)


def active(db, subject, run_id, user):
    if not content.allowed(db, subject, run_id, user):
        raise HTTPException(404, '공개된 뿌리 학습 범위가 없습니다.')
    control = db.get(RootControl, (subject, run_id))
    row = db.get(RootContent, (subject, run_id, control.revision))
    if not row or not row.reviewed:
        raise HTTPException(404, '검토된 뿌리 학습 자료가 없습니다.')
    return row


def checked_session(db, session_id, user):
    row = db.get(RootSession, session_id)
    if not row or row.user_id != user.id:
        raise HTTPException(404, '학습 회차가 없습니다.')
    doc = active(db, row.subject, row.run_id, user)
    if doc.revision != row.revision:
        raise HTTPException(409, '활성 자료 판이 바뀌었습니다. 원래 기록은 보존했습니다. 오늘 학습을 다시 열어 주세요.')
    return row, doc


def overview_data(db, row, user, when):
    configured = policy.configured_policy()
    if configured is None:
        return {'revision': row.revision, 'title': row.document['title'], 'policyReady': False,
                'message': '초기 추천·복습 정책 선택 대기', 'summary': None, 'plan': None, 'sessionId': None}
    events = content.events_for(db, row.subject, row.run_id, user.id)
    available, problems = content.availability(db, row, user.id)
    sessions = db.scalars(select(RootSession).where(RootSession.user_id == user.id,
        RootSession.subject == row.subject, RootSession.run_id == row.run_id, RootSession.revision == row.revision,
        RootSession.day == policy.study_day(when, configured).isoformat()).order_by(RootSession.created_at.desc())).all()
    pending = next((s for s in sessions if s.policy == configured and s.state['index'] < len(s.tasks)), None)
    return {'revision': row.revision, 'title': row.document['title'], 'policyReady': True, 'policy': configured,
            'scope': row.document['review']['scope'], 'summary': state.summary(row.document, events, available, when, configured),
            'plan': planning.plan(row.document, events, available, when, configured),
            'sessionId': pending.id if pending else None, 'preparationProblems': len(problems)}


@router.get('/root-learning')
def catalog(user: CurrentUser = Depends(require_approved_user), db: Session = Depends(get_db)):
    rows = []
    if content.globally_enabled():
        for control in db.scalars(select(RootControl).where(RootControl.enabled.is_(True))):
            if not content.allowed(db, control.subject, control.run_id, user):
                continue
            row = db.get(RootContent, (control.subject, control.run_id, control.revision))
            if row and row.reviewed:
                rows.append({'subject': row.subject, 'runId': row.run_id, **overview_data(db, row, user, now())})
    return {'lectures': rows, 'canManage': user.is_admin}


@router.get(BASE)
def overview(subject: str, run_id: str, user: CurrentUser = Depends(require_approved_user), db: Session = Depends(get_db)):
    return overview_data(db, active(db, subject, run_id, user), user, now())


@router.get('/admin' + BASE)
def versions(subject: str, run_id: str, user: CurrentUser = Depends(require_admin), db: Session = Depends(get_db)):
    rows = db.scalars(select(RootContent).where(RootContent.subject == subject, RootContent.run_id == run_id)
                      .order_by(RootContent.created_at.desc())).all()
    control = db.get(RootControl, (subject, run_id))
    return {'versions': [{'revision': r.revision, 'title': r.document['title'], 'reviewed': r.reviewed,
                          'digest': r.digest} for r in rows], 'enabled': bool(control and control.enabled),
            'activeRevision': control.revision if control else None}


@router.post('/admin' + BASE)
def register(subject: str, run_id: str, payload: dict, user: CurrentUser = Depends(require_admin), db: Session = Depends(get_db)):
    if not db.get(Lecture, (subject, run_id)):
        raise HTTPException(404, '강의가 없습니다.')
    try:
        doc = content.validate_registration(db, subject, run_id, payload)
    except (ValueError, KeyError, TypeError) as error:
        raise HTTPException(422, str(error))
    old = db.get(RootContent, (subject, run_id, doc['revision']))
    digest = document_hash(doc)
    if old:
        if old.digest != digest:
            raise HTTPException(409, '같은 판의 내용은 변경할 수 없습니다. 새 판을 등록하세요.')
        return {'revision': old.revision, 'digest': old.digest}
    db.add(RootContent(subject=subject, run_id=run_id, revision=doc['revision'], document=doc, digest=digest, reviewed=False))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, '동시에 등록되었습니다. 판 목록을 다시 조회하세요.')
    return {'revision': doc['revision'], 'digest': digest}


@router.put('/admin' + BASE + '/publication')
def publish(subject: str, run_id: str, payload: Publication, user: CurrentUser = Depends(require_admin), db: Session = Depends(get_db)):
    lecture = db.get(Lecture, (subject, run_id))
    if not lecture:
        raise HTTPException(404, '강의가 없습니다.')
    db.refresh(lecture, with_for_update=True)
    row = db.get(RootContent, (subject, run_id, payload.revision))
    if not row:
        raise HTTPException(404, '등록된 판이 없습니다.')
    if payload.enabled and (not payload.reviewed or row.document['review']['provenance']['status'] != 'reviewed' or not row.document['tasks']):
        raise HTTPException(409, '내용 검토 기록과 준비된 과제를 확인한 판만 활성화할 수 있습니다.')
    # Recheck equivalence and current shared-bank identity at publication time.
    if payload.enabled:
        try:
            content.validate_registration(db, subject, run_id, row.document)
        except ValueError as error:
            raise HTTPException(409, str(error))
    row.reviewed = payload.reviewed
    control = db.get(RootControl, (subject, run_id))
    if not control:
        control = RootControl(subject=subject, run_id=run_id)
        db.add(control)
    control.revision, control.enabled, control.allowed_users = row.revision, payload.enabled, payload.allowedUsers
    db.add(RootEvent(user_id=user.id, request_id=str(uuid4()), session_id='', subject=subject, run_id=run_id,
        revision=row.revision, kind='publication', payload=payload.model_dump(),
        result={'enabled': payload.enabled, 'revision': row.revision}))
    db.commit()
    return {'enabled': control.enabled, 'revision': control.revision}


@router.post(BASE + '/sessions')
def start(subject: str, run_id: str, payload: Start, user: CurrentUser = Depends(require_approved_user), db: Session = Depends(get_db)):
    row = active(db, subject, run_id, user)
    request = payload.model_dump()
    previous = db.get(RootEvent, (user.id, payload.requestId))
    if previous:
        if (previous.kind, previous.subject, previous.run_id, previous.payload.get('_request')) != ('start', subject, run_id, request):
            raise HTTPException(409, '같은 요청 ID의 다른 작업입니다.')
        return previous.result
    when = now()
    info = overview_data(db, row, user, when)
    if not info['policyReady']:
        raise HTTPException(409, info['message'])
    existing = db.get(RootSession, info['sessionId']) if info['sessionId'] else None
    if existing:
        session = existing
    else:
        tasks = info['plan']['tasks']
        if not tasks:
            raise HTTPException(409, '오늘 추천할 준비된 과제가 없습니다. 남은 범위와 준비 상태를 확인하세요.')
        day = policy.study_day(when, info['policy']).isoformat()
        identity = document_hash([user.id, subject, run_id, row.revision, day, info['policy'], tasks])
        session = db.get(RootSession, identity)
        if session is None:
            session = RootSession(id=identity, user_id=user.id, subject=subject, run_id=run_id,
                revision=row.revision, day=day, policy=info['policy'], tasks=tasks,
                state={'index': 0, 'reveals': {}, 'mapSeen': False, 'undo': None, 'exposedRelations': []}, version=0)
            db.add(session)
        elif session.state['index'] >= len(session.tasks):
            raise HTTPException(409, '같은 오늘 목록은 이미 끝났습니다. 추가 과제가 생기면 다시 계획합니다.')
    result = {'sessionId': session.id, 'version': session.version}
    db.add(RootEvent(user_id=user.id, request_id=payload.requestId, session_id=session.id,
        subject=subject, run_id=run_id, revision=row.revision, kind='start', payload={'_request': request}, result=result, created_at=when))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, '다른 탭에서 시작되었습니다. 다시 불러오세요.')
    return result


def project_session(db, row, doc, user, when):
    available, problems = content.availability(db, doc, user.id)
    index = row.state['index']
    task = row.tasks[index] if index < len(row.tasks) else None
    expired = row.day != policy.study_day(when, row.policy).isoformat()
    blocked = '학습일이 바뀌었습니다. 오늘 학습을 다시 계획하세요.' if expired else problems.get(task['task_id']) if task else None
    out = {'sessionId': row.id, 'revision': row.revision, 'version': row.version, 'day': row.day, 'policy': row.policy,
           'position': index, 'count': len(row.tasks), 'finished': task is None, 'blocked': blocked,
           'canUndo': bool(row.state.get('undo')) and not expired, 'mapSeen': row.state['mapSeen'], 'task': None,
           'summary': state.summary(doc.document, content.events_for(db, row.subject, row.run_id, user.id), available, when, row.policy)}
    if task and task['task_id'] in available and not expired:
        q = content.question(doc.document, task)
        reveal = row.state['reveals'].get(task['task_id'])
        out['task'] = {'id': task['task_id'], 'question': content.front(q),
                       'answer': revealed_answer(db, doc, q) if reveal else None,
                       'response': reveal['response'] if reveal else None,
                       'attempted': reveal['attempted'] if reveal else None,
                       'helped': row.state['mapSeen'] or (reveal['helped'] if reveal else prior_exposure(doc.document, task, q, row.state))}
    return out


def revealed_answer(db, doc, q):
    from app.models.root_generation import RootGeneration
    from app.storage import ObjectStorage
    answer = content.answer(q)
    generation = db.scalars(select(RootGeneration).where(RootGeneration.subject == doc.subject,
        RootGeneration.run_id == doc.run_id, RootGeneration.result_digest.is_not(None))).all()
    generation = next((g for g in generation if g.packet['revision'] == doc.revision), None)
    if generation:
        result = generation.result
        answer['reviewNotes'] = [
            {'source': label, **r} for label, checks in [('원본 대조', result['sourceAudit']['question_checks']), ('독립 정답 검수', result['medical'])]
            for r in checks['reviews'] if r['question_id'] == q['question_id'] and r['verdict'] != 'ok']
        answer['reviewIssues'] = result['sourceAudit']['input_issues'] + result['validation']['errors'] + result['validation']['warnings']
        answer['sourceLinks'] = [{'label': s['filename'], 'url': ObjectStorage().presign_download(s['snapshotKey'], filename=s['filename'])}
                                 for s in generation.packet['sources']]
    return answer


def prior_exposure(doc, task, q, session_state):
    direction = next(d for t in state.targets(doc) for d in t['directions'] if d['direction_id'] == task['direction_id'])
    return bool(q.get('options')) or bool(set(direction['relation_ids']) & set(session_state.get('exposedRelations', [])))


@router.get('/root-learning/sessions/{session_id}')
def read_session(session_id: str, user: CurrentUser = Depends(require_approved_user), db: Session = Depends(get_db)):
    row, doc = checked_session(db, session_id, user)
    return project_session(db, row, doc, user, now())


@router.post('/root-learning/sessions/{session_id}/events')
def act(session_id: str, payload: Action, user: CurrentUser = Depends(require_approved_user), db: Session = Depends(get_db)):
    row, doc = checked_session(db, session_id, user)
    request = payload.model_dump()
    if not request['stimulusHashes']:request.pop('stimulusHashes')
    previous = db.get(RootEvent, (user.id, payload.requestId))
    if previous:
        if previous.session_id != session_id or previous.payload.get('_request') != request:
            raise HTTPException(409, '같은 요청 ID의 다른 작업입니다.')
        return previous.result
    when = now()
    if row.day != policy.study_day(when, row.policy).isoformat():
        raise HTTPException(409, '학습일이 바뀌었습니다. 원래 요청을 보존하고 오늘 학습을 다시 여세요.')
    if payload.version != row.version:
        raise HTTPException(409, '다른 탭에서 변경되었습니다. 서버 기록을 다시 불러오세요.')
    session_state = copy.deepcopy(row.state)
    task = row.tasks[session_state['index']] if session_state['index'] < len(row.tasks) else None
    available, _ = content.availability(db, doc, user.id)
    data = {'_request': request, 'policy': row.policy, 'exam_date': doc.document['exam_date']}
    if payload.kind == 'map':
        session_state['mapSeen'] = True
    elif payload.kind == 'undo':
        undo = session_state.get('undo')
        if not undo:
            raise HTTPException(409, '취소할 직전 평가가 없습니다.')
        data['undo'] = undo['requestId']
        session_state.update(index=undo['index'], undo=None)
    elif not task:
        raise HTTPException(409, '이 회차의 마지막 질문입니다.')
    elif payload.kind == 'skip':
        session_state.update(index=session_state['index'] + 1, undo=None)
        data.update(task_id=task['task_id'], direction_id=task['direction_id'])
    else:
        if task['task_id'] not in available:
            raise HTTPException(409, '문항/개인 설정이 바뀌었습니다. 연결을 다시 확인하거나 이 과제를 보류하세요.')
        q = content.question(doc.document, task)
        reveal = session_state['reveals'].get(task['task_id'])
        data.update(task_id=task['task_id'], direction_id=task['direction_id'])
        if payload.kind == 'reveal':
            if reveal:
                raise HTTPException(409, '이미 답을 확인했습니다.')
            expected=[s['sha256']for s in q.get('stimuli',[])]
            if payload.attempted and expected and payload.stimulusHashes!=expected:
                raise HTTPException(409,'문항 그림 확인이 필요합니다. 새로고침 후 그림을 확인하거나 답만 보기를 선택하세요.')
            helped = payload.helped or session_state['mapSeen'] or prior_exposure(doc.document, task, q, session_state)
            data.update(attempted=payload.attempted, response=payload.response, helped=helped)
            session_state['reveals'][task['task_id']] = {k: data[k] for k in ('attempted', 'response', 'helped')}
            exposed = set(session_state.get('exposedRelations', []))
            for mapping in doc.document['review']['mappings']:
                if mapping['question_id'] == task['question_id']:
                    for field in ('tested_relation_ids', 'provided_relation_ids', 'explanation_relation_ids'):
                        exposed.update(mapping[field])
            session_state['exposedRelations'] = sorted(exposed)
            session_state['undo'] = None
        else:
            if not reveal:
                raise HTTPException(409, '답을 먼저 확인하세요.')
            helped = payload.helped or reveal['helped'] or session_state['mapSeen']
            if payload.grade == 'independent' and (helped or not reveal['attempted']):
                raise HTTPException(422, '답만 보거나 도움을 본 회상은 독립 회상으로 기록할 수 없습니다.')
            data.update(grade=payload.grade, helped=helped)
            session_state.update(undo={'requestId': payload.requestId, 'index': session_state['index']}, index=session_state['index'] + 1)
    result = {'sessionId': row.id, 'version': row.version + 1}
    changed = db.execute(update(RootSession).where(RootSession.id == row.id, RootSession.version == row.version)
                         .values(state=session_state, version=row.version + 1))
    if changed.rowcount != 1:
        db.rollback()
        raise HTTPException(409, '다른 탭의 변경을 먼저 불러오세요.')
    db.add(RootEvent(user_id=user.id, request_id=payload.requestId, session_id=row.id, subject=row.subject,
        run_id=row.run_id, revision=row.revision, kind=payload.kind, payload=data, result=result, created_at=when))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, '동시 요청이 있습니다. 서버 기록을 다시 불러오세요.')
    return result


@router.get('/root-learning/sessions/{session_id}/map')
def read_map(session_id: str, user: CurrentUser = Depends(require_approved_user), db: Session = Depends(get_db)):
    row, doc = checked_session(db, session_id, user)
    if not row.state['mapSeen']:
        raise HTTPException(409, '지도 답 노출을 먼저 확인하세요.')
    return {'concepts': doc.document['review']['concepts'], 'relations': doc.document['review']['relations'],
            'targets': state.targets(doc.document), 'scope': doc.document['review']['scope'],
            'readyDirectionIds':sorted({t['direction_id']for t in doc.document['tasks']}),
            'points': doc.document['review']['points'], 'coverage': doc.document['review']['coverage']}

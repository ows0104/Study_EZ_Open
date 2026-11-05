"""Real lecture connection learning; never writes QuizBank or BankState."""
import copy
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.auth import CurrentUser, require_admin, require_approved_user
from app.database import get_db
from app.models import Lecture
from app.models.connections import ConnectionContent, ConnectionEvent, ConnectionState

router = APIRouter()
BASE = '/lectures/{subject}/{run_id}/connections'


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Prompt(Strict):
    question: str = Field(min_length=1, max_length=10000)
    answers: list[str] = Field(min_length=1, max_length=100)
    explanation: str = Field(max_length=20000)


class Bundle(Strict):
    id: str = Field(pattern=r'^[A-Za-z0-9_-]{1,64}$')
    title: str
    type: str
    structure: str
    role: str
    root: Prompt
    follow: Prompt
    connection: str
    next: str
    sources: str
    original: str
    structural: str
    exam: str
    clinical: str
    gap: str


class Document(Strict):
    revision: str = Field(pattern=r'^[A-Za-z0-9_-]{1,64}$')
    title: str = Field(min_length=1, max_length=300)
    scope: str = Field(min_length=1, max_length=3000)
    bundles: list[Bundle] = Field(min_length=1, max_length=500)

    @model_validator(mode='after')
    def unique(self):
        if len({b.id for b in self.bundles}) != len(self.bundles):
            raise ValueError('중복 질문 ID')
        return self


class Publication(Strict):
    published: bool


class Action(Strict):
    requestId: str = Field(pattern=r'^[A-Za-z0-9_-]{1,64}$')
    version: int = Field(ge=0)
    kind: Literal['reveal', 'rate', 'map', 'select']
    index: int = Field(default=0, ge=0)
    step: Literal['root', 'follow'] = 'root'
    response: str = Field(default='', max_length=10000)
    marks: list[Literal['', 'recalled', 'partial', 'learned']] = Field(default_factory=list, max_length=100)


def content(db, subject, run_id, revision, user):
    row = db.get(ConnectionContent, (subject, run_id, revision))
    if not row or (not row.published and not user.is_admin):
        raise HTTPException(404, '공개된 연결 학습 자료가 없습니다.')
    return row


def empty():
    return {'current': 0, 'reviewSeen': False, 'entries': {}}


def project(doc, state, version):
    index = state['current']
    b = doc['bundles'][index]
    entry = state['entries'].get(b['id'], {})
    task = {'id': b['id'], 'root': {'question': b['root']['question']}}
    for step in ('root', 'follow'):
        if step == 'root' or 'root' in entry:
            task[step] = {'question': b[step]['question']}
        if step in entry:
            task[step] = {**b[step], **entry[step]}
    return {'revision': doc['revision'], 'title': doc['title'], 'scope': doc['scope'],
            'version': version, 'state': state, 'task': task, 'count': len(doc['bundles']),
            'map': doc['bundles'] if state['reviewSeen'] else None}


@router.get(BASE)
def overview(subject: str, run_id: str, user: CurrentUser = Depends(require_approved_user), db: Session = Depends(get_db)):
    query = select(ConnectionContent).where(ConnectionContent.subject == subject, ConnectionContent.run_id == run_id)
    if not user.is_admin:
        query = query.where(ConnectionContent.published.is_(True))
    rows = db.scalars(query.order_by(ConnectionContent.created_at.desc())).all()
    return {'canManage': user.is_admin, 'versions': [{'revision': r.revision, 'title': r.document['title'],
        'scope': r.document['scope'], 'count': len(r.document['bundles']), 'published': r.published} for r in rows]}


@router.post('/admin' + BASE)
def register(subject: str, run_id: str, payload: Document, user: CurrentUser = Depends(require_admin), db: Session = Depends(get_db)):
    if not db.get(Lecture, (subject, run_id)):
        raise HTTPException(404, '강의가 없습니다.')
    key = (subject, run_id, payload.revision)
    old = db.get(ConnectionContent, key)
    if old:
        if old.document != payload.model_dump():
            raise HTTPException(409, '같은 판의 내용을 바꿀 수 없습니다. 새 판으로 등록하세요.')
        return {'revision': old.revision}
    db.add(ConnectionContent(subject=subject, run_id=run_id, revision=payload.revision, document=payload.model_dump()))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, '동시에 등록되었습니다. 다시 조회하세요.')
    return {'revision': payload.revision}


@router.put('/admin' + BASE + '/{revision}/publication')
def publish(subject: str, run_id: str, revision: str, payload: Publication, user: CurrentUser = Depends(require_admin), db: Session = Depends(get_db)):
    row = content(db, subject, run_id, revision, user)
    row.published = payload.published
    db.commit()
    return {'published': row.published}


@router.get(BASE + '/{revision}')
def read(subject: str, run_id: str, revision: str, user: CurrentUser = Depends(require_approved_user), db: Session = Depends(get_db)):
    doc = content(db, subject, run_id, revision, user).document
    row = db.get(ConnectionState, (user.id, subject, run_id, revision))
    return project(doc, row.state if row else empty(), row.version if row else 0)


@router.post(BASE + '/{revision}/actions')
def act(subject: str, run_id: str, revision: str, payload: Action, user: CurrentUser = Depends(require_approved_user), db: Session = Depends(get_db)):
    doc = content(db, subject, run_id, revision, user).document
    previous = db.get(ConnectionEvent, (user.id, payload.requestId))
    serialized = payload.model_dump()
    if previous:
        if (previous.subject, previous.run_id, previous.revision, previous.payload) != (subject, run_id, revision, serialized):
            raise HTTPException(409, '요청 ID가 다른 작업에 사용되었습니다.')
        return previous.result
    key = (user.id, subject, run_id, revision)
    row = db.get(ConnectionState, key)
    version = row.version if row else 0
    if payload.version != version:
        raise HTTPException(409, '다른 탭에서 학습 기록이 바뀌었습니다. 다시 불러오세요.')
    state = copy.deepcopy(row.state if row else empty())
    if payload.index >= len(doc['bundles']):
        raise HTTPException(422, '질문 범위 밖입니다.')
    b = doc['bundles'][payload.index]
    if payload.kind == 'map':
        state['reviewSeen'] = True
    elif payload.kind == 'select':
        state['current'] = payload.index
    else:
        entry = state['entries'].setdefault(b['id'], {})
        if payload.step == 'follow' and 'root' not in entry:
            raise HTTPException(409, '첫 답을 먼저 확인하세요.')
        if payload.kind == 'reveal':
            entry.setdefault(payload.step, {'response': payload.response, 'marks': [''] * len(b[payload.step]['answers'])})
        else:
            if payload.step not in entry or len(payload.marks) != len(b[payload.step]['answers']):
                raise HTTPException(409, '답 공개와 항목 수를 확인하세요.')
            entry[payload.step]['marks'] = payload.marks
    result = project(doc, state, version + 1)
    try:
        if row:
            changed = db.execute(update(ConnectionState).where(
                ConnectionState.user_id == user.id, ConnectionState.subject == subject,
                ConnectionState.run_id == run_id, ConnectionState.revision == revision,
                ConnectionState.version == version).values(state=state, version=version + 1))
            if changed.rowcount != 1:
                db.rollback()
                raise HTTPException(409, '다른 탭의 변경을 먼저 불러오세요.')
        else:
            db.add(ConnectionState(user_id=user.id, subject=subject, run_id=run_id, revision=revision, state=state, version=1))
        db.add(ConnectionEvent(user_id=user.id, request_id=payload.requestId, subject=subject, run_id=run_id,
                               revision=revision, payload=serialized, result=result))
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, '동시 요청이 있습니다. 다시 불러오세요.')
    return result

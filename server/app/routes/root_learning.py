"""Root-learning product API. Legacy question and learner tables are read-only here."""
import copy
import logging
import re
from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, defer
from studyez_contracts.roots import document_hash
from app.auth import CurrentUser, require_admin, require_approved_user
from app.database import get_db
from app import bank_personal
from app.models import BankFeedback, BankPersonalEdit, Lecture
from app.models.root_learning import RootContent, RootControl, RootSession, RootEvent
from app.root_learning import content, light, policy, state, planning

log = logging.getLogger(__name__)
router = APIRouter()
BASE = '/root-learning/lectures/{subject}/{run_id}'
PREPARE_AHEAD = 4


def now():
    return datetime.now(UTC)


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Start(Strict):
    requestId: str = Field(pattern=r'^[A-Za-z0-9_-]{1,64}$')


class Action(Start):
    version: int = Field(ge=0)
    kind: Literal['reveal', 'rate', 'skip', 'exclude', 'map', 'undo']
    attempted: bool = False
    response: str = Field(default='', max_length=10000)
    helped: bool = False
    grade: Literal['missed', 'partial', 'independent'] = 'missed'
    stimulusHashes: list[str] = Field(default_factory=list,max_length=64)
    choicesShown: bool | None = None
    selfRating: Literal['Again', 'Hard', 'Good', 'Easy'] | None = None


class Publication(Strict):
    revision: str = Field(pattern=r'^[A-Za-z0-9_-]{1,64}$')
    reviewed: bool
    enabled: bool
    allowedUsers: list[str] = Field(default_factory=list, max_length=1000)


def active(db, subject, run_id, user):
    if not content.allowed(db, subject, run_id, user):
        raise HTTPException(404, '공개된 Main Quiz 학습 범위가 없습니다.')
    control = db.get(RootControl, (subject, run_id))
    # 그림 바이트를 뺀 사본(light.py, 2026-11-12 저장 방식). 원본 6–12 MB를 요청마다 읽지 않는다.
    # 그림이 필요한 문항 하나는 learner_front·snapshot_question이 되붙인다.
    row = light.revision_row(db, subject, run_id, control.revision)
    if row is None:
        raise HTTPException(404, '검토된 Main Quiz 학습 자료가 없습니다.')
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
    # 오늘 학습 중요도 필터(2026-11-12): only today's plan is filtered; summary and progress keep every task.
    chosen = content.focus_for(db, row.subject, user.id)
    tiers = content.task_tiers(row.document, state.personal_tiers(row.document, events))
    narrowed = len(chosen) < len(policy.TIERS)
    pending = next((s for s in sessions if s.policy == configured and s.state['index'] < len(s.tasks)
                    and s.state.get('focus', list(policy.TIERS)) == chosen), None)
    focused = {t for t in available if tiers[t] in chosen} if narrowed else None
    planned = planning.plan(row.document, events, available, when, configured, focus=focused)
    return {'revision': row.revision, 'title': row.document['title'], 'policyReady': True, 'policy': configured,
            'scope': content.learner_scope(row.document), 'summary': state.summary(row.document, events, available, when, configured),
            'plan': planned,
            'focus': {'tiers': chosen, 'counts': {name: sum(tiers[t] == name for t in available) for name in policy.TIERS}},
            'questionProgress': state.question_progress(row.document, events, available, when, configured, planned),
            'sessionId': pending.id if pending else None, 'preparationProblems': len(problems)}


@router.get('/main-quiz/lectures/{subject}/{run_id}/entry')
def main_quiz_entry(subject: str, run_id: str, user: CurrentUser = Depends(require_approved_user), db: Session = Depends(get_db)):
    """Read-only dispatch; publication/account/stop guards remain authoritative."""
    if not db.get(Lecture, (subject, run_id)):
        raise HTTPException(404, '강의가 없습니다.')
    if content.allowed(db, subject, run_id, user):
        control = db.get(RootControl, (subject, run_id))
        row = light.revision_row(db, subject, run_id, control.revision)
        if row is not None:
            return {'mode': 'structured', 'overview': overview_data(db, row, user, now())}
    return {'mode': 'legacy'}


@router.get('/root-learning')
def catalog(user: CurrentUser = Depends(require_approved_user), db: Session = Depends(get_db)):
    rows = []
    if content.globally_enabled():
        keys = [(c.subject, c.run_id) for c in db.scalars(select(RootControl).where(RootControl.enabled.is_(True)))
                if content.allowed(db, c.subject, c.run_id, user)]
        # 그림 바이트를 뺀 판별 사본(light.py). 요약·계획 계산은 그림을 읽지 않는다.
        docs = light.current_rows(db, keys)
        for key in keys:
            row = docs.get(key)
            if row is None:
                continue
            try:
                rows.append({'subject': row.subject, 'runId': row.run_id, **overview_data(db, row, user, now())})
            except Exception:
                # 한 강의의 계획 계산 실패가 목록 전체를 500으로 만들었다(2026-11-12 운영). 그 강의만 뺀다 —
                # 화면은 시간표의 학습률(mastery)로 그린다. 그 강의를 열면 원래 오류가 그대로 보인다.
                log.exception('Main-Quiz 목록 요약 실패 %s/%s', *key)
    return {'lectures': rows, 'canManage': user.is_admin}


@router.get(BASE)
def overview(subject: str, run_id: str, user: CurrentUser = Depends(require_approved_user), db: Session = Depends(get_db)):
    return overview_data(db, active(db, subject, run_id, user), user, now())


@router.get('/admin' + BASE)
def versions(subject: str, run_id: str, user: CurrentUser = Depends(require_admin), db: Session = Depends(get_db)):
    # Each revision's document carries the whole bank snapshot; the list needs only its title.
    rows = db.execute(select(RootContent.revision, RootContent.document['title'].as_string(), RootContent.reviewed,
                             RootContent.digest).where(RootContent.subject == subject, RootContent.run_id == run_id)
                      .order_by(RootContent.created_at.desc())).all()
    control = db.get(RootControl, (subject, run_id))
    return {'versions': [{'revision': revision, 'title': title, 'reviewed': reviewed, 'digest': digest}
                         for revision, title, reviewed, digest in rows], 'enabled': bool(control and control.enabled),
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


RANGE = re.compile(r'^bytes=(\d*)-(\d*)$')
# (subject, run_id, revision, source_id) -> (source record, byte size). A reviewed revision's
# document is immutable and its sources are pinned by sha256, so the frozen file for one key
# never changes. PDF.js asks for many byte ranges per page; each one reloaded the whole
# document JSON, the generation row and an R2 HEAD (about 0.7 s apiece in production).
_SOURCES = {}


def frozen_source(db, subject, run_id, user, source_id, storage):
    if not content.allowed(db, subject, run_id, user):
        raise HTTPException(404, '공개된 뿌리 학습 범위가 없습니다.')
    control = db.get(RootControl, (subject, run_id))
    key = (subject, run_id, control.revision, source_id)
    cached = _SOURCES.get(key)
    if cached:
        return cached
    from app.root_learning.evidence import frozen_pdf
    doc = active(db, subject, run_id, user)
    source = frozen_pdf(doc, active_generation(db, doc, light=True), source_id)
    if source is None:
        raise HTTPException(404, '참고 자료가 없습니다.')
    head = storage.head(source['snapshotKey'])
    if head is None:
        raise HTTPException(404, '참고 자료 파일이 저장소에 없습니다.')
    if len(_SOURCES) >= 64:
        _SOURCES.clear()
    _SOURCES[key] = cached = (source, int(head['ContentLength']))
    return cached


@router.get(BASE + '/sources/{source_id}')
def read_source(subject: str, run_id: str, source_id: str, range_header: str | None = Header(None, alias='Range'),
                user: CurrentUser = Depends(require_approved_user), db: Session = Depends(get_db)):
    """Read-only stream of the frozen reference PDF for PDF.js (R2 has no CORS rule).

    Same audience as the signed 원본 링크: users allowed to study the active revision.
    Supports a single byte range so the viewer only pulls the pages it draws."""
    from app.storage import ObjectStorage
    storage = ObjectStorage()
    source, size = frozen_source(db, subject, run_id, user, source_id, storage)
    headers = {'Accept-Ranges': 'bytes', 'Cache-Control': 'private, max-age=3600', 'ETag': f'"{source["sha256"]}"'}
    span = None
    if range_header:
        match = RANGE.match(range_header.strip())
        if not match or match.groups() == ('', ''):
            raise HTTPException(416, '잘못된 범위 요청입니다.', headers={'Content-Range': f'bytes */{size}'})
        first, last = match.groups()
        start, end = (size - int(last), size - 1) if first == '' else (int(first), min(int(last), size - 1) if last else size - 1)
        start = max(start, 0)
        if size == 0 or start > end or start >= size:
            raise HTTPException(416, '잘못된 범위 요청입니다.', headers={'Content-Range': f'bytes */{size}'})
        span = (start, end)
    opened = storage.open_stream(source['snapshotKey'], byte_range=span)
    if opened is None:
        raise HTTPException(404, '참고 자료 파일이 저장소에 없습니다.')
    chunks, length = opened
    headers['Content-Length'] = str(length)
    if span:
        headers['Content-Range'] = f'bytes {span[0]}-{span[1]}/{size}'
    return StreamingResponse(chunks, status_code=206 if span else 200, media_type='application/pdf', headers=headers)


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
        fresh = {'index': 0, 'reveals': {}, 'mapSeen': False, 'undo': None, 'exposedRelations': []}
        key = [user.id, subject, run_id, row.revision, day, info['policy'], tasks]
        # Every tier chosen: the former state and session ID exactly. A narrowed choice is its own session.
        if len(info['focus']['tiers']) < len(policy.TIERS):
            fresh['focus'] = info['focus']['tiers']
            key.append({'focus': info['focus']['tiers']})
        identity = document_hash(key)
        session = db.get(RootSession, identity)
        if session is None:
            session = RootSession(id=identity, user_id=user.id, subject=subject, run_id=run_id,
                revision=row.revision, day=day, policy=info['policy'], tasks=tasks, state=fresh, version=0)
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
    events = content.events_for(db, row.subject, row.run_id, user.id)
    blocked = '학습일이 바뀌었습니다. 오늘 학습을 다시 계획하세요.' if expired else problems.get(task['task_id']) if task else None
    out = {'sessionId': row.id, 'revision': row.revision, 'version': row.version, 'day': row.day, 'policy': row.policy,
           'position': index, 'count': len(row.tasks), 'finished': task is None, 'blocked': blocked,
           'canUndo': bool(undo_stack(row.state)) and not expired, 'mapSeen': row.state['mapSeen'], 'task': None,
           'summary': state.summary(doc.document, events, available, when, row.policy)}
    if task and task['task_id'] in available and not expired:
        q = content.question(doc.document, task)
        shown = content.with_tier(with_personal(q, personal_edits(db, doc, user.id)), state.personal_tiers(doc.document, events))
        reveal = row.state['reveals'].get(task['task_id'])
        out['task'] = {'id': task['task_id'], 'question': learner_front(doc, shown, db),
                       'answer': revealed_answer(db, doc, shown) if reveal else None,
                       'response': reveal['response'] if reveal else None,
                       'attempted': reveal['attempted'] if reveal else None,
                       'helped': row.state['mapSeen'] or (reveal['helped'] if reveal else prior_exposure(doc.document, task, q, row.state))}
    return out


def active_generation(db, doc, *, light=True):
    """The revision's generation record without its large result/web_response JSON (both deferred).
    Learner paths read only packet/web_dispatch (source snapshots) and the review notes, which
    revealed_answer takes from review_notes (extracted once per record). `light` is kept for callers."""
    from app.models.root_generation import RootGeneration
    query = select(RootGeneration).where(RootGeneration.subject == doc.subject,
        RootGeneration.run_id == doc.run_id, RootGeneration.result_digest.is_not(None),
        RootGeneration.packet['revision'].as_string()==doc.revision)
    query = query.options(defer(RootGeneration.result), defer(RootGeneration.web_response))
    return db.scalars(query).first()


_UNSET = object()


# ── 문제 수정·제보 (2026-11-08) ──────────────────────────────────────────────
# 기존 Quiz Bank와 같은 표를 쓴다: 개인 수정본은 bank_personal_edit(내 계정에만), 제보는 bank_feedback.
# 개인 수정은 문제은행 없이 선 판(standalone)에만 적용한다. 문제은행과 연결된 판은 기존 규칙상 개인 수정본이 있으면
# 그 과제를 연결 미확인으로 막으므로(content.availability) 여기서는 제보만 받는다.

def learner_front(doc, q, db=None):
    """Question front plus the target retention new ratings aim for (Quiz Bank 「목표 N%」)."""
    plans = {p['concept_id']: p for p in doc.document['bank_snapshot'].get('retrieval_plan', [])}
    personal = q['tier'] if q.get('personalTier') else None
    target = policy.target_retention(q, plans.get(q.get('concept_id')), policy.target_parameters(), personal)
    from app.root_learning import choices
    # 단답·나열 「선지 보기」(2026-11-12): 이 판·이 문항 글에 맞는 선지가 있을 때만 붙는다.
    shown = light.hydrate(db, doc, q) if db is not None else q
    return choices.attach_front(db, doc, q, {**content.front(shown), 'targetMastery': target})


def personal_editable(doc):
    return doc.document['bank_source'] == 'standalone'


def personal_edits(db, doc, user_id):
    if not personal_editable(doc):
        return {}
    return {e.question_id: e for e in db.scalars(select(BankPersonalEdit).where(
        BankPersonalEdit.user_id == user_id, BankPersonalEdit.subject == doc.subject,
        BankPersonalEdit.run_id == doc.run_id))}


def with_personal(q, edits):
    return bank_personal.apply_edit(q, edits.get(q['question_id']))


def feedback_build(doc):
    """bank_feedback.build_id(64자)에 Main-Quiz 판을 적는다. 관리자 신고함이 이 값으로 문면과 옛 판을 가른다."""
    return ('root:' + doc.revision)[:64]


def snapshot_question(db, doc, question_id):
    """원본 그대로의 문항(그림 포함). 개인 수정의 `revision`·`same_source`와 제보의 원문이 문항 전체로 비교·보관한다."""
    q = next((q for q in doc.document['bank_snapshot']['questions'] if q['question_id'] == question_id), None)
    if q is None:
        raise HTTPException(404, '문항을 찾을 수 없습니다.')
    return light.hydrate(db, doc, q)


class RootPersonalEdit(Strict):
    action: Literal['save', 'reset'] = 'save'
    revision: str = Field(min_length=64, max_length=64)
    question: str = Field(min_length=1, max_length=12000)
    answer: str = Field(min_length=1, max_length=12000)
    report: bool = False
    category: str = Field(default='content', max_length=16)
    comment: str = Field(default='', max_length=2000)


@router.get(BASE + '/questions/{question_id}/personal')
def read_personal(subject: str, run_id: str, question_id: str, user: CurrentUser = Depends(require_approved_user),
                  db: Session = Depends(get_db)):
    doc = active(db, subject, run_id, user)
    original = snapshot_question(db, doc, question_id)
    edit = db.get(BankPersonalEdit, (user.id, subject, run_id, question_id)) if personal_editable(doc) else None
    valid = edit is not None and bank_personal.same_source(edit.original, original)
    current = bank_personal.apply_edit(original, edit) if valid else original
    return {'original': {'question': original['question'], 'answer': original['answer'], 'explanation': original.get('explanation', '')},
            'draft': {'question': current['question'], 'answer': current['answer'], 'explanation': current.get('explanation', '')},
            'edited': valid, 'comment': edit.comment if valid else '', 'revision': bank_personal.revision(original),
            'personalAdded': False, 'editable': personal_editable(doc)}


@router.put(BASE + '/questions/{question_id}/personal')
def save_personal(subject: str, run_id: str, question_id: str, payload: RootPersonalEdit,
                  user: CurrentUser = Depends(require_approved_user), db: Session = Depends(get_db)):
    from app.routes.bank_api.feedback import FEEDBACK_CATEGORIES
    if payload.category not in FEEDBACK_CATEGORIES:
        raise HTTPException(422, '제보 유형을 확인하세요.')
    doc = active(db, subject, run_id, user)
    original = snapshot_question(db, doc, question_id)
    if payload.revision != bank_personal.revision(original):
        raise HTTPException(409, '문항이 바뀌었습니다. 수정창을 다시 열어 주세요.')
    question, answer = payload.question.strip(), payload.answer.strip()
    if not question or not answer:
        raise HTTPException(422, '발문과 정답을 비워 둘 수 없습니다.')
    changed = question != original['question'] or answer != original['answer']
    editable = personal_editable(doc)
    if changed and not editable:
        raise HTTPException(409, '이 Main-Quiz는 문제은행과 연결된 판이라 개인 수정은 할 수 없습니다. 제보만 보낼 수 있습니다.')
    comment = payload.comment.strip()
    edit = db.get(BankPersonalEdit, (user.id, subject, run_id, question_id)) if editable else None
    if editable:
        if payload.action == 'reset' or (not changed and not comment):
            if edit:
                db.delete(edit)
                edit = None
        else:
            if edit is None:
                edit = BankPersonalEdit(user_id=user.id, subject=subject, run_id=run_id, question_id=question_id)
                db.add(edit)
            edit.original, edit.question, edit.answer, edit.comment = original, question, answer, comment
    reported = payload.action == 'save'
    if reported:
        correction = None
        note = comment
        if changed:
            note += f"\n\n[개인 수정 제안]\n발문: {question}\n정답: {answer}"
            correction = {'original': original, 'proposed': {'question': question, 'answer': answer},
                          'changedFields': [k for k, v in (('question', question), ('answer', answer)) if v != original[k]]}
        db.add(BankFeedback(user_id=user.id, subject=subject, run_id=run_id, build_id=feedback_build(doc),
                            question_id=question_id, category=payload.category, comment=note.strip(),
                            highlighted=payload.report, correction=correction))
    db.commit()
    current = content.with_tier(bank_personal.apply_edit(original, edit), content.tiers_for(db, doc, user.id))
    return {'question': learner_front(doc, current, db), 'answer': revealed_answer(db, doc, current),
            'reported': reported, 'highlighted': reported and payload.report}


# ── 내 중요도 (2026-11-09) ──────────────────────────────────────────────────
# Quiz Bank 풀이의 「내 중요도」와 같은 선택. 내 계정·이 판에만 적용하고 append-only root_event(kind='tier')로
# 남긴다(표 추가 없음). 그 문항의 목표 기억률을 바꾼다(Quiz Bank target_for): state.replay · policy.target_retention.
# 목표 기억률 간격은 이 기능과 함께 들어온 새 평가(roots-four-rating/2)에만 적용한다.

class RootTier(Start):
    tier: Literal['Essential', 'Core', 'Important', 'Optional'] | None


@router.put(BASE + '/questions/{question_id}/tier')
def save_tier(subject: str, run_id: str, question_id: str, payload: RootTier,
              user: CurrentUser = Depends(require_approved_user), db: Session = Depends(get_db)):
    doc = active(db, subject, run_id, user)
    original = snapshot_question(db, doc, question_id)
    request = payload.model_dump()
    previous = db.get(RootEvent, (user.id, payload.requestId))
    if previous:
        if previous.kind != 'tier' or previous.payload.get('_request') != {**request, 'question_id': question_id}:
            raise HTTPException(409, '같은 요청 ID의 다른 작업입니다.')
        return previous.result
    base = content.original_tier(original)
    chosen = None if payload.tier == (base or 'Core') else payload.tier
    when = now()
    events = content.events_for(db, subject, run_id, user.id)
    data = {'_request': {**request, 'question_id': question_id}, 'question_id': question_id, 'tier': chosen,
            'originalTier': base, 'tierPolicy': policy.TIER_POLICY, 'seq': 1 + sum(e['kind'] == 'tier' for e in events)}
    events.append({'id': payload.requestId, 'revision': doc.revision, 'kind': 'tier', 'payload': data, 'at': when})
    current = content.with_tier(with_personal(original, personal_edits(db, doc, user.id)),
                                state.personal_tiers(doc.document, events))
    questions = {t['task_id']: t['question_id'] for t in doc.document['tasks']}
    # Only target-scheduled ratings move with the tier; earlier ones keep their own schedule.
    rescheduled = any(e['kind'] == 'rate' and e['revision'] == doc.revision and e['payload'].get('targetParameters')
                      and questions.get(e['payload'].get('task_id')) == question_id for e in events)
    result = {'question': learner_front(doc, current, db), 'rescheduled': rescheduled}
    db.add(RootEvent(user_id=user.id, request_id=payload.requestId, session_id='', subject=subject, run_id=run_id,
                     revision=doc.revision, kind='tier', payload=data, result=result, created_at=when))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, '동시 요청이 있습니다. 다시 시도하세요.')
    return result


# ── 오늘 학습 중요도 필터 (2026-11-12) ─────────────────────────────────────────
# 과목마다 마지막 선택을 append-only root_event(kind='focus')로 남긴다(표 추가 없음).
# 오늘 계획만 거른다. 학습 목표·진척·기록·복습 일정은 그대로다(docs/changes/2026-11-12-tier-filter).

class RootFocus(Start):
    tiers: list[Literal['Essential', 'Core', 'Important', 'Optional']] = Field(min_length=1, max_length=4)


@router.put(BASE + '/focus')
def save_focus(subject: str, run_id: str, payload: RootFocus,
               user: CurrentUser = Depends(require_approved_user), db: Session = Depends(get_db)):
    doc = active(db, subject, run_id, user)
    if len(set(payload.tiers)) != len(payload.tiers):
        raise HTTPException(422, '같은 중요도가 두 번 있습니다.')
    request = payload.model_dump()
    previous = db.get(RootEvent, (user.id, payload.requestId))
    if previous:
        if previous.kind != 'focus' or previous.payload.get('_request') != request:
            raise HTTPException(409, '같은 요청 ID의 다른 작업입니다.')
        return overview_data(db, doc, user, now())
    tiers = [t for t in policy.TIERS if t in payload.tiers]
    seq = 1 + max((e.payload.get('seq', 0) for e in content.focus_events(db, subject, user.id)), default=0)
    db.add(RootEvent(user_id=user.id, request_id=payload.requestId, session_id='', subject=subject, run_id=run_id,
                     revision=doc.revision, kind='focus', payload={'_request': request, 'tiers': tiers, 'seq': seq},
                     result={'tiers': tiers}, created_at=now()))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, '동시 요청이 있습니다. 다시 시도하세요.')
    return overview_data(db, doc, user, now())


def question_issues(issues, question_id):
    """Run-wide audit notes that name this question. The rest stay in the generation record, not on every answer."""
    named = re.compile(r'(?<![A-Za-z0-9_])' + re.escape(question_id) + r'(?![A-Za-z0-9_])')
    return [i for i in issues if named.search(i if isinstance(i, str) else str(i))]


def revealed_answer(db, doc, q, generation=_UNSET):
    answer = content.answer(q)
    if generation is _UNSET:
        generation = active_generation(db, doc)
    if generation:
        # 출제 기록 result(판당 3.6–9.5 MB)를 요청마다 읽지 않는다 — 판마다 한 번 뽑은 메모(review_notes, 2026-11-12).
        from app.root_learning import review_notes
        notes = review_notes.for_generation(db, generation)
        answer['reviewNotes'] = [r for r in notes['notes'] if r['question_id'] == q['question_id']]
        answer['reviewIssues'] = question_issues(notes['issues'], q['question_id'])
    # Quiz Bank와 같은 자료 충돌·자료 밖(EXT) 표시. 판 문서에 고정된 충돌 기록만 쓴다(2026-11-08).
    conflict = next((c for c in doc.document['bank_snapshot'].get('source_conflicts', [])
                     if q.get('conflict_id') and c.get('conflict_id') == q['conflict_id']), None)
    answer['conflict'] = (conflict or {}).get('description', '')
    answer['external'] = any(r.get('source_id') == 'EXT' for r in q.get('source_refs', []))
    from app.root_learning.evidence import attach_evidence
    attach_evidence(db, doc, q, generation, answer)
    from app.root_learning import choices
    choices.attach_answer(db, doc, q, answer)
    return answer


def recall_choice_entry(db, doc, q):
    from app.root_learning import choices
    return choices.entry(db, doc, q)


def prior_exposure(doc, task, q, session_state, choices_shown=None, recall_choices=False):
    direction = next(d for t in state.targets(doc) for d in t['directions'] if d['direction_id'] == task['direction_id'])
    choice_help = bool(q.get('options')) if choices_shown is None else (
        bool(q.get('options')) and q.get('mcq_mode') != 'comparison' and choices_shown)
    # 단답·나열에 덧붙인 선지를 편 풀이도 도움받은 풀이다. 선지가 실제로 있는 문항일 때만 센다.
    choice_help = choice_help or bool(choices_shown and recall_choices)
    if state.per_task(doc):
        # root-generation/4 (spec R8): sibling questions of one direction ask different parts, so only an
        # earlier exposure of this same task in the session counts, not the direction's relations.
        return choice_help or task['task_id'] in session_state.get('reveals', {})
    return choice_help or bool(set(direction['relation_ids']) & set(session_state.get('exposedRelations', [])))


def task_fingerprint(doc, task):
    """root-generation/4 events record their question fingerprint so a later revision can carry history
    per unchanged question (state.replay_tasks). Older documents record nothing new."""
    if not state.per_task(doc):
        return {}
    if isinstance(doc, light.LightDocument):
        # 사본은 원본(그림 포함)으로 계산한 지문을 들고 다닌다. 사본으로 다시 계산하면 값이 달라진다.
        return {'question_sha256': doc.task_fingerprints[task['task_id']]}
    from studyez_contracts.roots import task_fingerprints
    return {'question_sha256': task_fingerprints(doc)[task['task_id']]}


@router.get('/root-learning/sessions/{session_id}')
def read_session(session_id: str, user: CurrentUser = Depends(require_approved_user), db: Session = Depends(get_db)):
    row, doc = checked_session(db, session_id, user)
    return project_session(db, row, doc, user, now())


@router.get('/root-learning/sessions/{session_id}/prepare')
def prepare(session_id: str, start: int | None = Query(None, ge=0), count: int = Query(PREPARE_AHEAD, ge=1, le=8),
            user: CurrentUser = Depends(require_approved_user), db: Session = Depends(get_db)):
    """Read-only look-ahead of this session's fixed task list; it records nothing.

    A reveal, rating or skip is still a fact only once /events stores it. The page holds
    these frames so Space and a rating draw at once while the event is confirmed behind it
    (each answer used to wait for the event, then this projection, then the overview)."""
    row, doc = checked_session(db, session_id, user)
    out = {'sessionId': row.id, 'revision': row.revision, 'frames': []}
    if row.day != policy.study_day(now(), row.policy).isoformat():
        return out
    begin = row.state['index'] if start is None else start
    available, problems = content.availability(db, doc, user.id)
    generation = active_generation(db, doc)
    edits = personal_edits(db, doc, user.id)
    tiers = content.tiers_for(db, doc, user.id)
    for position in range(begin, min(begin + count, len(row.tasks))):
        task = row.tasks[position]
        frame = {'position': position, 'taskId': task['task_id'], 'blocked': problems.get(task['task_id']), 'task': None}
        if task['task_id'] in available:
            q = content.question(doc.document, task)
            shown = content.with_tier(with_personal(q, edits), tiers)
            frame['task'] = {'id': task['task_id'], 'question': learner_front(doc, shown, db),
                             'answer': revealed_answer(db, doc, shown, generation),
                             'helped': row.state['mapSeen'] or prior_exposure(doc.document, task, q, row.state)}
        out['frames'].append(frame)
    return out


def undo_stack(state):
    """회차 안에서 Z로 되돌릴 행동들(2026-11-11 사용자 지시: 어느 화면에서든 끝없이, 모든 게 돌아가게).
    옛 세션의 한 칸 `undo`는 평가 한 항목으로 읽는다."""
    if 'undoStack' in state:
        return list(state['undoStack'])
    old = state.get('undo')
    return [{'requestId': old['requestId'], 'kind': 'rate', 'index': old['index']}] if old else []


def set_undo_stack(state, stack):
    state['undoStack'] = stack
    top = stack[-1] if stack else None
    # 롤백한 옛 코드는 `undo` 한 칸만 읽는다. 맨 위가 평가·보류일 때만 그 칸을 남긴다.
    state['undo'] = {'requestId': top['requestId'], 'index': top['index']} if top and top['kind'] != 'reveal' else None


@router.post('/root-learning/sessions/{session_id}/events')
def act(session_id: str, payload: Action, user: CurrentUser = Depends(require_approved_user), db: Session = Depends(get_db)):
    row, doc = checked_session(db, session_id, user)
    request = payload.model_dump()
    if not request['stimulusHashes']:request.pop('stimulusHashes')
    if request['choicesShown'] is None:request.pop('choicesShown')
    if request['selfRating'] is None:request.pop('selfRating')
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
    excluded = content.excluded_ids(content.events_for(db, row.subject, row.run_id, user.id), row.revision)
    start_index = session_state['index']
    data = {'_request': request, 'policy': row.policy, 'exam_date': doc.document['exam_date']}
    if payload.kind == 'map':
        session_state['mapSeen'] = True
    elif payload.kind == 'undo':
        stack = undo_stack(session_state)
        if not stack:
            raise HTTPException(409, '되돌릴 행동이 없습니다.')
        top = stack.pop()
        data['undo'] = top['requestId']
        if top['kind'] == 'reveal':
            # 답 보기도 없던 일로: 다시 문제 화면, 이번에 새로 노출된 관계도 뺀다. 이벤트는 undo로 표시만 한다.
            session_state['reveals'].pop(top['taskId'], None)
            added = set(top['added'])
            session_state['exposedRelations'] = [r for r in session_state.get('exposedRelations', []) if r not in added]
        else:
            session_state['index'] = top['index']
        set_undo_stack(session_state, stack)
    elif not task:
        raise HTTPException(409, '이 회차의 마지막 질문입니다.')
    elif payload.kind in ('skip', 'exclude'):
        set_undo_stack(session_state, undo_stack(session_state) + [
            {'requestId': payload.requestId, 'kind': payload.kind, 'index': session_state['index']}])
        session_state['index'] += 1
        data.update(task_id=task['task_id'], direction_id=task['direction_id'], **task_fingerprint(doc.document, task))
        if payload.kind == 'exclude':
            data['question_id'] = task['question_id']
            excluded.add(task['question_id'])
    else:
        if task['task_id'] not in available:
            raise HTTPException(409, '문항/개인 설정이 바뀌었습니다. 연결을 다시 확인하거나 이 과제를 보류하세요.')
        q = content.question(doc.document, task)
        reveal = session_state['reveals'].get(task['task_id'])
        data.update(task_id=task['task_id'], direction_id=task['direction_id'], **task_fingerprint(doc.document, task))
        if payload.kind == 'reveal':
            if reveal:
                raise HTTPException(409, '이미 답을 확인했습니다.')
            expected=[s['sha256']for s in q.get('stimuli',[])]
            if payload.attempted and expected and payload.stimulusHashes!=expected:
                raise HTTPException(409,'문항 그림 확인이 필요합니다. 새로고침 후 그림을 확인하거나 답만 보기를 선택하세요.')
            helped = payload.helped or session_state['mapSeen'] or prior_exposure(
                doc.document, task, q, session_state, payload.choicesShown,
                recall_choices=bool(payload.choicesShown) and recall_choice_entry(db, doc, q) is not None)
            data.update(attempted=payload.attempted, response=payload.response, helped=helped)
            session_state['reveals'][task['task_id']] = {k: data[k] for k in ('attempted', 'response', 'helped')}
            before = set(session_state.get('exposedRelations', []))
            exposed = set(before)
            for mapping in doc.document['review']['mappings']:
                if mapping['question_id'] == task['question_id']:
                    for field in ('tested_relation_ids', 'provided_relation_ids', 'explanation_relation_ids'):
                        exposed.update(mapping[field])
            session_state['exposedRelations'] = sorted(exposed)
            set_undo_stack(session_state, undo_stack(session_state) + [
                {'requestId': payload.requestId, 'kind': 'reveal', 'taskId': task['task_id'], 'added': sorted(exposed - before)}])
        else:
            if not reveal:
                raise HTTPException(409, '답을 먼저 확인하세요.')
            helped = payload.helped or reveal['helped'] or session_state['mapSeen']
            if payload.selfRating is None and payload.grade == 'independent' and (helped or not reveal['attempted']):
                raise HTTPException(422, '답만 보거나 도움을 본 회상은 독립 회상으로 기록할 수 없습니다.')
            grade = {'Again': 'missed', 'Hard': 'partial', 'Good': 'independent', 'Easy': 'independent'}.get(payload.selfRating, payload.grade)
            # Self-assessment stays available; exposure remains a separate fact.
            data.update(grade=grade, helped=(helped or not reveal['attempted']) if payload.selfRating is not None else helped)
            if payload.selfRating is not None:
                data.update(selfRating=payload.selfRating, ratingPolicy=policy.TARGET_RATING_POLICY,
                            ratingParameters=copy.deepcopy(policy.FOUR_RATING_PARAMETERS),
                            targetParameters=policy.target_parameters())
            set_undo_stack(session_state, undo_stack(session_state) + [
                {'requestId': payload.requestId, 'kind': 'rate', 'index': session_state['index']}])
            session_state['index'] += 1
    if payload.kind != 'undo' and session_state['index'] > start_index:
        # 앞으로 넘어갈 때 Main-Quiz에서 제외한 문항의 과제는 건너뛴다. Z는 저장한 원래 위치로 돌아간다.
        while session_state['index'] < len(row.tasks) and row.tasks[session_state['index']]['question_id'] in excluded:
            session_state['index'] += 1
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
    task = row.tasks[row.state['index']] if row.state['index'] < len(row.tasks) else None
    current = next((t['concept_ids'] for t in state.targets(doc.document) if task and
                    any(d['direction_id'] == task['direction_id'] for d in t['directions'])), [])
    return {'concepts': doc.document['review']['concepts'], 'relations': doc.document['review']['relations'], 'currentConceptIds': current,
            'targets': state.targets(doc.document), 'scope': content.learner_scope(doc.document),
            'readyDirectionIds':sorted({t['direction_id']for t in doc.document['tasks']}),
            'points': doc.document['review']['points'], 'coverage': doc.document['review']['coverage']}

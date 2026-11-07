"""Queue explicit map/point requests and atomically publish their verified artifacts."""
from datetime import UTC, datetime
import hashlib
from pathlib import PurePath
from uuid import uuid4
from typing import Literal
import json
import re
import io
from collections import OrderedDict
from copy import deepcopy
from threading import Lock
from boto3.exceptions import S3UploadFailedError
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Text, case, cast, inspect as sa_inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, defer
from app.auth import CurrentUser, require_admin, require_runner
from app.database import get_db
from app.models import Asset, Lecture, PrequizJob, JOB_BANK, JOB_BUTTON, JOB_QUEUED, JOB_DONE
from app.models.root_generation import RootGeneration
from app.models.root_learning import RootContent, RootControl, RootEvent
from app.jobs.queue import open_job_of
from app.storage import ObjectStorage, StorageNotConfigured
from app.root_learning.content import globally_enabled
from app.routes.bank_api.common import bank_sources
from studyez_contracts.roots import document_hash
from studyez_contracts.roots.automation import packet_hash, validate_result
from studyez_contracts.roots.generation_v2 import VERSION as SOURCE_FORMAT

router = APIRouter()
BASE = '/admin/root-learning/lectures/{subject}/{run_id}/generation'
DUPLICATE_STAGE = '중복 요청 보존 · 기존 검수 상한 유지'


class RequestIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    requestId: str = Field(pattern=r'^[A-Za-z0-9_-]{1,64}$')
    conceptMap: str = Field(default='', max_length=500000)
    points: str = Field(default='', max_length=500000)
    inputMode: Literal['provided','source'] = 'provided'
    scope: str = Field(default='', max_length=10000)
    examDate: str | None = None
    privatePilot: bool = True
    resume: bool = False
    authoring: Literal['cli','web'] = 'web'
    parallelAuthoring: bool = False


def control_hash(db, subject, run_id):
    row = db.get(RootControl, (subject, run_id))
    return document_hash([row.revision, row.enabled, row.allowed_users] if row else None)


def assets_now(db, subject, run_id):
    rows = bank_sources(db, db.get(Lecture, (subject, run_id)))
    if not any(s['kind'] == 'notes_current' for s in rows):
        raise HTTPException(409, '등록된 올해 강의 원본이 필요합니다.')
    storage = ObjectStorage()
    result = []
    for source in rows:
        asset = db.get(Asset, source['assetId'])
        if PurePath(asset.filename).suffix.lower() not in ('.pdf', '.md', '.txt'):
            raise HTTPException(422, '원본 자료는 PDF·MD·TXT 형식을 사용하세요.')
        body = storage.get_bytes(asset.object_key)
        if body is None:
            raise HTTPException(409, '등록된 원본 파일을 읽지 못했습니다.')
        result.append({'id': source['id'], 'assetId': asset.id, 'kind': asset.kind,
            'filename': asset.filename, 'sizeBytes': len(body), 'sha256': hashlib.sha256(body).hexdigest(),
            'originalKey': asset.object_key, 'uploadedAt': asset.uploaded_at.isoformat(), '_body': body})
    return result


def generation_input(packet):
    """Compare effective frozen inputs, not how an automatic date was selected."""
    return {**{k: packet.get(k) for k in ('subject','runId','title','conceptMap','points','scope','examDate')},
        'inputMode':packet.get('inputMode','provided'),'authoring':packet.get('authoring','cli'),
        'parallelAuthoring':packet.get('parallelAuthoring',False),
        'sources':[{k:v for k,v in s.items() if k!='snapshotKey'} for s in packet['sources']]}


def equivalent_generation(db, packet, *, before=None):
    rows=db.scalars(select(RootGeneration).where(RootGeneration.subject==packet['subject'],
        RootGeneration.run_id==packet['runId']).order_by(RootGeneration.created_at,RootGeneration.id)).all()
    for candidate in rows:
        if before is not None and (candidate.created_at,candidate.id)>=(before.created_at,before.id):continue
        if generation_input(candidate.packet)==generation_input(packet):return candidate
    return None


# 폴링 경로가 참/거짓만 쓰거나(web_*) 판이 바뀔 때만 쓰는(result) 큰 JSON. 운영 Supabase에서는
# 2.5MB result를 매 폴링 끌어오는 것이 2초대였다. 접근하면 SQLAlchemy가 그때 읽으므로 값은 같다.
HEAVY = ('result', 'web_dispatch', 'web_response')
LIGHT = tuple(defer(getattr(RootGeneration, name)) for name in HEAVY)


def present(column):
    """SQL에서 Python bool(dict | None)과 같은 참/거짓: SQL NULL·JSON null·{}는 거짓."""
    return case((column.is_(None), False), (cast(column, Text).in_(('null', '{}')), False), else_=True)


PRESENT = tuple(present(getattr(RootGeneration, name)).label('has_' + name) for name in HEAVY)


def heavy_flags(db, row):
    """{'result': bool, ...}. 이미 적재된 칼럼은 그 값으로, 아니면 참/거짓만 질의한다."""
    unloaded = sa_inspect(row).unloaded
    if not unloaded.intersection(HEAVY):
        return {name: bool(getattr(row, name)) for name in HEAVY}
    values = db.execute(select(*PRESENT).where(RootGeneration.id == row.id)).one()
    return {name: bool(getattr(row, name)) if name not in unloaded else bool(value) for name, value in zip(HEAVY, values)}


def canonical_generation(db, row):
    seen=set()
    while row.packet.get('supersededBy'):
        if row.id in seen:raise HTTPException(409,'중복 작업 연결을 확인해야 합니다.')
        seen.add(row.id)
        prior=db.get(RootGeneration,row.packet['supersededBy'],options=LIGHT)
        if (prior is None or prior.user_id!=row.user_id or prior.packet['privatePilot']!=row.packet['privatePilot']
            or generation_input(prior.packet)!=generation_input(row.packet)
            or (prior.created_at,prior.id)>=(row.created_at,row.id)):
            raise HTTPException(409,'중복 작업의 입력·소유자가 다릅니다.')
        row=prior
    return row


def retain_duplicate(db, row):
    """Keep a dispatched duplicate and its response without new authoring rounds."""
    prior=equivalent_generation(db,row.packet,before=row)
    if prior is None:return None
    prior=canonical_generation(db,prior)
    if prior.user_id!=row.user_id or prior.packet['privatePilot']!=row.packet['privatePilot']:
        raise HTTPException(409,'같은 입력의 기존 작업이 있습니다. 공개 범위는 등록된 판의 공개 관리에서 바꾸세요.')
    job=db.get(PrequizJob,row.job_id)
    archived=job.state=='canceled' and job.stage==DUPLICATE_STAGE and row.packet.get('supersededBy')==prior.id
    if (job.state not in ('held','queued') and not archived) or job.cancel_requested:
        raise HTTPException(409,'실행·취소된 중복 작업은 자동으로 바꾸지 않습니다.')
    row.packet={**row.packet,'supersededBy':prior.id}
    row.packet={**row.packet,'inputHash':packet_hash(row.packet)}
    # Closed request, retained content: a held duplicate would block the original
    # request and ordinary Main-Quiz jobs forever through the shared open queue.
    job.state,job.stage='canceled',DUPLICATE_STAGE
    job.message='같은 입력의 기존 작업을 사용합니다. 새 웹 응답은 보존하고 추가 출제·검수는 시작하지 않습니다.'
    job.resume_at=None
    return prior


def build_report(result):
    if result.get('policy')in('verified-main-quiz-replacement/1','verified-main-quiz-curation/1'):
        from app.root_learning.replacement_import import report as replacement_report
        return replacement_report(result)
    return {'repairRounds': result['manifest']['repairRounds'], 'taskCount': len(result['document']['tasks']),
            'targetCount': len(result['brief']['targets']),
            'issues': result['sourceAudit']['input_issues'] + result['validation']['errors'] + result['validation']['warnings'],
            'questionNotes': [{'source': label, **r} for label, checks in [('원본 대조', result['sourceAudit']['question_checks']), ('독립 정답 검수', result['medical'])]
                for r in checks['reviews'] if r['verdict'] != 'ok'],
            'coverage': result['sourceAudit']['review']['coverage']}


# 게시된 판의 result는 바뀌지 않는다(put_result·대체판 등록이 다른 digest를 거부). 그래서 report를
# (판 id, result_digest)마다 한 번만 만든다. 인스턴스마다 따로이고, 다시 뜨면 한 번 더 읽는다.
REPORTS: OrderedDict = OrderedDict()
REPORTS_MAX = 128
REPORTS_LOCK = Lock()


def generation_report(row):
    if row.result_digest is None:
        return build_report(row.result)
    key = (row.id, row.result_digest)
    with REPORTS_LOCK:
        if key in REPORTS:
            REPORTS.move_to_end(key)
            return deepcopy(REPORTS[key])
    report = build_report(row.result)
    with REPORTS_LOCK:
        REPORTS[key] = deepcopy(report)
        while len(REPORTS) > REPORTS_MAX: REPORTS.popitem(last=False)
    return report


def public_job(db, row, flags=None):
    canonical=canonical_generation(db,row)
    if canonical is not row or flags is None: flags=heavy_flags(db,canonical)
    row=canonical
    job = db.get(PrequizJob, row.job_id)
    report = generation_report(row) if flags['result'] else None
    return {'id': row.id, 'requestId':row.request_id, 'jobId': row.job_id, 'state': job.state, 'stage': job.stage, 'message': job.message,
            'published': row.result_digest is not None, 'revision': row.packet['revision'],
            'privatePilot': row.packet['privatePilot'], 'featureEnabled': globally_enabled(),
            'createdAt': row.created_at.isoformat(),
            'input': {**{k: row.packet[k] for k in ('conceptMap', 'points', 'scope')},
                'examDate':row.packet.get('requestedExamDate',row.packet['examDate']),
                'inputMode':row.packet.get('inputMode','provided')}, 'report': report,
            'authoring':row.packet.get('authoring','cli'), 'parallelAuthoring':row.packet.get('parallelAuthoring',False), 'awaitingWeb':row.packet.get('authoring')=='web' and not flags['web_response'] and job.state=='held' and not job.cancel_requested and job.stage=='ChatGPT 응답 대기',
            'dispatched':flags['web_dispatch']}


def resume_job(db, row):
    if row.packet.get('supersededBy'):raise HTTPException(409,'중복 요청은 기존 작업에서 재개하세요.')
    job = db.get(PrequizJob, row.job_id)
    if job.state in ('failed', 'held', 'canceled') and not row.result_digest:
        if row.packet.get('authoring')=='web' and not row.web_response:
            raise HTTPException(409, '웹 응답이 필요합니다. 전송을 반복하지 않고 완성된 MD 파일을 전달하세요.')
        if open_job_of(db, row.subject, row.run_id, JOB_BANK) not in (None, job):
            raise HTTPException(409, '다른 문제은행 작업이 진행 중입니다.')
        job.state, job.cancel_requested, job.stage = JOB_QUEUED, False, '같은 입력·수정 상한으로 자동출제 재개'
        job.message=''
        job.finished_at, job.resume_at = None, None
        db.commit()


@router.get(BASE)
def latest(subject: str, run_id: str, user: CurrentUser = Depends(require_admin), db: Session = Depends(get_db)):
    # 3초마다 폴링하는 화면이 쓰는 것은 가장 최근 한 판이다. LIMIT이 없으면 그 강의의 모든 판이
    # 결과 집합에 들어온다. 큰 JSON(result·web_*)은 싣지 않고 참/거짓만 같은 SELECT에서 받는다.
    found = db.execute(select(RootGeneration, *PRESENT).options(*LIGHT)
                       .where(RootGeneration.subject == subject, RootGeneration.run_id == run_id)
                       .order_by(RootGeneration.created_at.desc()).limit(1)).first()
    if not found: return {'generation': None}
    row, *values = found
    return {'generation': public_job(db, row, dict(zip(HEAVY, map(bool, values))))}


@router.post(BASE)
def request(subject: str, run_id: str, payload: RequestIn, user: CurrentUser = Depends(require_admin), db: Session = Depends(get_db)):
    if payload.inputMode=='provided' and (not payload.conceptMap.strip() or not payload.points.strip()):
        raise HTTPException(422, 'Concept map과 출제포인트를 입력하세요.')
    if payload.parallelAuthoring and (payload.authoring!='cli' or payload.inputMode!='source'):
        raise HTTPException(422,'병렬 생성은 CLI 원본 모드에서만 사용합니다.')
    if payload.inputMode=='source' and (payload.conceptMap or payload.points or (payload.authoring!='web' and not payload.parallelAuthoring)):
        raise HTTPException(422,'원본 자동 준비는 웹 출제와 빈 지도·포인트 입력을 사용합니다.')
    if payload.examDate:
        from datetime import date
        try: date.fromisoformat(payload.examDate)
        except ValueError: raise HTTPException(422, '시험일 형식을 확인하세요.')
    lecture = db.get(Lecture, (subject, run_id))
    if not lecture:
        raise HTTPException(404, '강의가 없습니다.')
    db.refresh(lecture, with_for_update=True)
    raw = {'conceptMap': payload.conceptMap, 'points': payload.points, 'scope': payload.scope, 'examDate': payload.examDate,'authoring':payload.authoring}
    if payload.inputMode=='source':raw.update(inputMode='source',requestedExamDate=payload.examDate)
    if payload.parallelAuthoring:raw['parallelAuthoring']=True
    prior = db.scalars(select(RootGeneration).where(RootGeneration.user_id == user.id, RootGeneration.request_id == payload.requestId)).first()
    if prior:
        compare={k:v for k,v in raw.items() if not (payload.inputMode=='source' and k=='examDate')}
        if (prior.subject, prior.run_id) != (subject, run_id) or prior.packet.get('inputMode','provided')!=payload.inputMode or prior.packet.get('parallelAuthoring',False)!=payload.parallelAuthoring or any(prior.packet.get(k) != v for k, v in compare.items()) or prior.packet['privatePilot'] != payload.privatePilot:
            raise HTTPException(409, '같은 요청 ID의 입력이 달라졌습니다.')
        if payload.resume: resume_job(db, prior)
        return {'generation': public_job(db, prior), 'reused': True}
    if payload.inputMode=='source' and not payload.examDate:raw['examDate']=registered_exam_date(db,lecture)
    try:
        sources = assets_now(db, subject, run_id)
    except StorageNotConfigured as error:
        raise HTTPException(503, str(error))
    except (BotoCoreError,ClientError,OSError):
        raise HTTPException(503,'등록된 원본을 읽지 못했습니다. 자료와 기존 기록을 보존했으니 잠시 후 다시 시도하세요.')
    identity_sources = [{k: v for k, v in s.items() if k != '_body'} for s in sources]
    digest = document_hash([raw, identity_sources, lecture.title])
    existing = db.scalars(select(RootGeneration).where(RootGeneration.subject == subject, RootGeneration.run_id == run_id,
                                                     RootGeneration.input_digest == digest)).first()
    if existing is None:
        existing=equivalent_generation(db,{'subject':subject,'runId':run_id,'title':lecture.title,'sources':identity_sources,**raw})
    if existing:
        existing=canonical_generation(db,existing)
        if existing.packet['privatePilot'] != payload.privatePilot or existing.packet['owner'] != user.id:
            raise HTTPException(409, '같은 입력의 기존 작업이 있습니다. 공개 범위는 등록된 판의 공개 관리에서 바꾸세요.')
        if payload.resume: resume_job(db, existing)
        return {'generation': public_job(db, existing), 'reused': True}
    if open_job_of(db, subject, run_id, JOB_BANK):
        raise HTTPException(409, '기존 문제은행 작업이 끝난 뒤 요청하세요.')
    generation_id = uuid4().hex
    try:
        storage=ObjectStorage()
        for source in sources:
            suffix = PurePath(source['filename']).suffix.lower()
            key = f'lectures/root-generation/{generation_id}/{source["id"]}{suffix}'
            content_type={'.pdf':'application/pdf','.md':'text/markdown; charset=utf-8','.txt':'text/plain; charset=utf-8'}[suffix]
            storage.upload_fileobj(io.BytesIO(source.pop('_body')),key,content_type=content_type)
            source['snapshotKey'] = key
    except (BotoCoreError,ClientError,S3UploadFailedError,OSError):
        raise HTTPException(503,'출제용 원본 사본을 저장하지 못했습니다. 원본과 기존 학습은 보존했으며 전송은 시작하지 않았습니다. 잠시 후 다시 시도하세요.')
    packet = {'generationId': generation_id, 'revision': 'auto-' + generation_id, 'subject': subject, 'runId': run_id,
              'title': lecture.title, 'owner': user.id, 'privatePilot': payload.privatePilot, 'sources': sources, **raw,'inputMode':payload.inputMode}
    from studyez_contracts.roots.parallel import SOURCE_FORMAT as PARALLEL_FORMAT
    packet['sourceAssessmentFormat']=PARALLEL_FORMAT if payload.parallelAuthoring else SOURCE_FORMAT
    packet['inputHash'] = packet_hash(packet)
    job = PrequizJob(subject=subject, run_id=run_id, kind=JOB_BANK, origin=JOB_BUTTON, state='held' if payload.authoring=='web' else JOB_QUEUED,
                     requested_by=user.email or user.id, stage='ChatGPT 응답 대기' if payload.authoring=='web' else '문제은행·개념도·출제포인트 CLI 병렬 대기' if payload.parallelAuthoring else 'Concept map·포인트 자동출제 대기')
    db.add(job); db.flush()
    row = RootGeneration(id=generation_id, job_id=job.id, subject=subject, run_id=run_id, user_id=user.id,
        request_id=payload.requestId, input_digest=digest, packet=packet, baseline=control_hash(db, subject, run_id))
    db.add(row)
    db.add(RootEvent(user_id=user.id, request_id='gen-request-' + generation_id, session_id='', subject=subject, run_id=run_id,
        revision=packet['revision'], kind='generation', payload={'generationId': generation_id}, result={'jobId': job.id}))
    try: db.commit()
    except IntegrityError:
        db.rollback(); raise HTTPException(409, '동시에 등록되었습니다. 작업을 다시 조회하세요.')
    return {'generation': public_job(db, row), 'reused': False}


def registered_exam_date(db,lecture):
    from app.models import TimetableEvent
    event=db.get(TimetableEvent,lecture.timetable_event_id) if lecture.timetable_event_id else None
    course=(event.course if event else '').strip()
    if not course:return None
    exams=db.scalars(select(TimetableEvent).where(TimetableEvent.category=='exam',TimetableEvent.date>=lecture.date)
        .order_by(TimetableEvent.date)).all()
    chosen=next((e for e in exams if e.course==course or e.title.startswith(course)),None)
    return chosen.date.isoformat() if chosen else None


def pending_for_lecture(db, subject, run_id):
    job = open_job_of(db, subject, run_id, JOB_BANK)
    row = db.scalars(select(RootGeneration).where(RootGeneration.job_id == job.id)).first() if job else None
    return {'connectionGeneration': row.id, 'title': row.packet['title']} if row else None


def job_active(db, row):
    job = db.scalars(select(PrequizJob).where(PrequizJob.id == row.job_id).with_for_update()).first()
    if row.packet.get('supersededBy') or not job or job.state not in ('queued', 'running') or job.cancel_requested:
        raise HTTPException(409, '중지·취소·종료된 생성 작업입니다. 산출물은 보존했습니다.')
    return job


@router.get('/admin/root-generation/{generation_id}/input')
def get_input(generation_id: str, user: CurrentUser = Depends(require_runner), db: Session = Depends(get_db)):
    row = db.get(RootGeneration, generation_id)
    if not row: raise HTTPException(404, '생성 작업이 없습니다.')
    if row.result_digest: return {'published': True, 'revision': row.packet['revision']}
    job_active(db, row)
    packet = {**row.packet, 'sources': [{**s, 'downloadUrl': ObjectStorage().presign_download(s['snapshotKey'])} for s in row.packet['sources']]}
    if row.web_response: packet['webResponse'] = row.web_response
    return {'published': False, 'packet': packet}


def owned_web(db,generation_id,user):
    row=db.scalars(select(RootGeneration).where(RootGeneration.id==generation_id).with_for_update()).first()
    if not row or row.user_id!=user.id or row.packet.get('authoring')!='web':
        raise HTTPException(404,'내 웹 출제 요청이 없습니다.')
    return row


@router.get('/admin/root-generation/{generation_id}/web-input')
def web_input(generation_id:str,user:CurrentUser=Depends(require_admin),db:Session=Depends(get_db)):
    row=owned_web(db,generation_id,user)
    job=db.get(PrequizJob,row.job_id)
    if row.web_response or job.state!='held' or job.cancel_requested or job.stage!='ChatGPT 응답 대기':
        raise HTTPException(409,'웹 전송 대기 상태가 아닙니다. 기존 입력과 결과는 보존했습니다.')
    return {'packet':{**row.packet,'sources':[{**s,'downloadUrl':ObjectStorage().presign_download(s['snapshotKey'])} for s in row.packet['sources']]}}


class WebDispatch(BaseModel):
    model_config=ConfigDict(extra='forbid')
    promptVersion:str=Field(pattern=r'^1\.\d+$',max_length=16)
    promptHash:str=Field(pattern=r'^[a-f0-9]{64}$')


@router.post('/admin/root-generation/{generation_id}/web-dispatch')
def web_dispatch(generation_id:str,payload:WebDispatch,user:CurrentUser=Depends(require_admin),db:Session=Depends(get_db)):
    row=owned_web(db,generation_id,user)
    if row.web_dispatch:
        if row.web_dispatch['promptHash']!=payload.promptHash or row.web_dispatch['promptVersion']!=payload.promptVersion:
            raise HTTPException(409,'이미 기록된 전송 요청과 다릅니다. 기존 전송을 반복하지 않습니다.')
        return {'send':False}
    job=db.get(PrequizJob,row.job_id)
    if job.state!='held' or job.cancel_requested or job.stage!='ChatGPT 응답 대기':raise HTTPException(409,'전송이 중지되었습니다.')
    row.web_dispatch={**payload.model_dump(),'at':datetime.now(UTC).isoformat()}
    db.commit()
    return {'send':True}


@router.put('/admin/root-generation/{generation_id}/web-response')
def web_response(generation_id:str,payload:dict,user:CurrentUser=Depends(require_admin),db:Session=Depends(get_db)):
    from app.routes.bank_api.publication import ResponseIn
    from app.preview_links import conversation_url as valid_conversation_url,share_url as valid_share_url
    from studyez_contracts.bank.response_file import validate, metadata as file_metadata
    row=owned_web(db,generation_id,user)
    try:
        value=ResponseIn.model_validate(payload)
        if not value.response_file:raise ValueError('실제 문제은행 파일이 필요합니다.')
        metadata=validate(value.raw,value.response_file.filename,row.subject,row.run_id,value.response_file.model_dump(by_alias=True))
        if file_metadata(value.raw).get('generation_id')!=row.id:raise ValueError('다른 자동출제 요청의 파일입니다.')
        if not row.web_dispatch or value.prompt_version!=row.web_dispatch['promptVersion'] or metadata['promptVersion']!=value.prompt_version:
            raise ValueError('전송한 프롬프트와 파일의 판이 다릅니다.')
        if value.conversation_url and not valid_conversation_url(value.conversation_url,'chatgpt'):raise ValueError('대화 주소가 올바르지 않습니다.')
        if value.share_url and not valid_share_url(value.share_url,'chatgpt'):raise ValueError('공유 주소가 올바르지 않습니다.')
    except ValueError as error:raise HTTPException(422,str(error))
    response={'raw':value.raw,'responseFile':value.response_file.model_dump(by_alias=True),'promptVersion':value.prompt_version,
              'conversationUrl':value.conversation_url,'shareUrl':value.share_url}
    if row.web_response:
        if row.web_response['responseFile']!=response['responseFile'] or row.web_response['raw']!=response['raw']:
            raise HTTPException(409,'수신한 파일을 덮어쓸 수 없습니다.')
        return {'saved':True,'reused':True}
    job=db.get(PrequizJob,row.job_id)
    archived=job.state=='canceled' and job.stage==DUPLICATE_STAGE and row.packet.get('supersededBy')
    if job.cancel_requested or (not archived and (job.state!='held' or job.stage!='ChatGPT 응답 대기')):
        raise HTTPException(409,'중지·취소된 웹 출제입니다.')
    row.web_response=response
    row.packet={**row.packet,'webResponseHash':document_hash(response)}
    row.packet={**row.packet,'inputHash':packet_hash(row.packet)}
    duplicate=retain_duplicate(db,row)
    if duplicate is None:job.state,job.stage=JOB_QUEUED,'웹 파일 수신 완료 · 원본·정답 검수 대기'
    db.commit()
    return {'saved':True,'reused':False,**({'held':True,'generationId':duplicate.id}if duplicate else {})}


@router.put('/admin/root-generation/{generation_id}/result')
def put_result(generation_id: str, payload: dict, user: CurrentUser = Depends(require_runner), db: Session = Depends(get_db)):
    row = db.scalars(select(RootGeneration).where(RootGeneration.id == generation_id).with_for_update()).first()
    if not row: raise HTTPException(404, '생성 작업이 없습니다.')
    digest = document_hash(payload)
    if row.result_digest:
        if row.result_digest != digest: raise HTTPException(409, '같은 작업의 결과가 달라졌습니다.')
        return {'status': 'ready', 'revision': row.packet['revision'], 'reused': True}
    job = job_active(db, row)
    lecture = db.get(Lecture, (row.subject, row.run_id)); db.refresh(lecture, with_for_update=True)
    if control_hash(db, row.subject, row.run_id) != row.baseline:
        raise HTTPException(409, '그 사이 활성 판/공개 범위가 바뀌었습니다. 결과를 보존하고 확인하세요.')
    current = [{k: v for k, v in s.items() if k != '_body'} for s in assets_now(db, row.subject, row.run_id)]
    original = [{k: v for k, v in s.items() if k != 'snapshotKey'} for s in row.packet['sources']]
    if current != original: raise HTTPException(409, '요청 후 원본 자료가 바뀌었습니다. 기존 학습은 보존했습니다.')
    try: doc = validate_result(payload, row.packet)
    except (ValueError, KeyError, TypeError) as error: raise HTTPException(422, str(error))
    if not doc['tasks']: raise HTTPException(422, '학습 가능한 방향별 과제가 없습니다. 검토 결과를 확인하세요.')
    key = (row.subject, row.run_id, doc['revision'])
    if db.get(RootContent, key): raise HTTPException(409, '이미 다른 경로로 등록된 판입니다.')
    db.add(RootContent(subject=row.subject, run_id=row.run_id, revision=doc['revision'], document=doc,
                       digest=document_hash(doc), reviewed=True))
    control = db.get(RootControl, (row.subject, row.run_id))
    if not control:
        control = RootControl(subject=row.subject, run_id=row.run_id); db.add(control)
    control.revision, control.enabled = doc['revision'], True
    control.allowed_users = [row.user_id] if row.packet['privatePilot'] else []
    row.result, row.result_digest = payload, digest
    job.state, job.stage, job.finished_at = JOB_DONE, '', datetime.now(UTC)
    job.message = 'Concept map·포인트 자동출제 게시 완료 · 미해결 검수 기록 보존'
    db.add(RootEvent(user_id=row.user_id, request_id='gen-published-' + row.id, session_id='', subject=row.subject,
        run_id=row.run_id, revision=doc['revision'], kind='generated', payload={'generationId': row.id},
        result={'revision': doc['revision'], 'privatePilot': row.packet['privatePilot']}))
    db.commit()
    return {'status': 'ready', 'revision': doc['revision'], 'reused': False, 'featureEnabled': globally_enabled()}

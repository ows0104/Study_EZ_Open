"""Content registration and conservative legacy-bank availability checks."""
import os
import copy
import re
from sqlalchemy import select
from sqlalchemy.orm import defer
from studyez_contracts.roots import validate_document, document_hash, direction_hash
from app import bank_personal
from app.models import QuizBank, BankState, BankPersonalEdit
from app.models.root_learning import RootContent, RootControl, RootEvent


def learner_scope(document):
    """Show source limitations, keep authoring-environment diagnostics in the archive."""
    value=copy.deepcopy(document['review']['scope'])
    if document['review']['provenance']['method']in('verified-main-quiz-replacement/1','verified-main-quiz-curation/1'):
        operational=r'Python|checker|trampoline|permission denied|os error|독립\s*(?:의료|의학|정답)\s*검수.*(?:시행하지|수행하지|하지 않았)'
        value['limitations']=[text for text in value['limitations']if not re.search(operational,text,re.I)]
    return value


def globally_enabled():
    return os.getenv('STUDYEZ_ROOT_LEARNING_ENABLED', '').lower() == 'true'


def allowed(db, subject, run_id, user):
    control = db.get(RootControl, (subject, run_id))
    return bool(globally_enabled() and control and control.enabled and control.revision and
                (not control.allowed_users or user.id in control.allowed_users or user.is_admin))


def validate_registration(db, subject, run_id, payload):
    doc = validate_document(payload)
    if doc['review']['lecture_id'] != f'{subject}/{run_id}':
        raise ValueError('검토 묶음과 등록할 강의가 다릅니다.')
    if doc['bank_source'] == 'quizbank':
        row = db.get(QuizBank, (subject, run_id))
        if not row or row.build_id != doc['bank_build_id'] or document_hash(row.bank) != doc['review']['bank_sha256']:
            raise ValueError('현재 문제은행의 빌드/내용 지문과 일치하지 않습니다.')
    for link in doc['equivalences']:
        previous = db.get(RootContent, (subject, run_id, link['revision']))
        if not previous or not previous.reviewed:
            raise ValueError('동일성 연결은 검토된 이전 판이 필요합니다.')
        try:
            same = direction_hash(previous.document, link['from_direction']) == direction_hash(doc, link['to_direction'])
        except (StopIteration, KeyError):
            same = False
        if not same:
            raise ValueError('방향/답 범위/과제/출처가 다른 기록을 승계할 수 없습니다.')
    return doc


# (subject, run_id) -> (build_id, updated_at, document_hash(bank)). The bank is the
# whole question set; hashing its canonical JSON on every learner request held the
# single API CPU. Every ORM write to quiz_bank bumps updated_at (onupdate), so a
# changed bank misses the cache and is hashed again.
_BANK_HASHES = {}


def bank_hash(row):
    key = (row.subject, row.run_id)
    cached = _BANK_HASHES.get(key)
    if cached and row.updated_at is not None and cached[:2] == (row.build_id, row.updated_at):
        return cached[2]
    value = document_hash(row.bank)
    if row.updated_at is not None:
        _BANK_HASHES[key] = (row.build_id, row.updated_at, value)
    return value


# Columns availability never reads; still loaded on access if another caller needs them.
_UNUSED_BANK_COLUMNS = (QuizBank.raw_response, QuizBank.validation, QuizBank.review, QuizBank.usage)


def availability(db, content, user_id):
    doc = content.document
    tasks = {t['task_id']: t for t in doc['tasks']}
    if doc['bank_source'] == 'standalone':
        return set(tasks), {}
    row = db.get(QuizBank, (content.subject, content.run_id), options=[defer(c) for c in _UNUSED_BANK_COLUMNS])
    if not row or not row.open_to_students or row.status != 'ready':
        return set(), {tid: '원래 문제은행 공개/준비 상태 변경' for tid in tasks}
    if row.build_id != doc['bank_build_id'] or bank_hash(row) != doc['review']['bank_sha256']:
        return set(), {tid: '원래 문항 판 변경 · 연결 재검토 필요' for tid in tasks}
    legacy = db.get(BankState, (user_id, content.subject, content.run_id))
    state = legacy.state if legacy and legacy.build_id == row.build_id else {}
    suspended = set(state.get('suspended_question_ids', []))
    decisions = state.get('excluded_question_decisions', {})
    questions = {q['question_id']: q for q in row.bank['questions']}
    # One query for the learner's edits, not one round trip per task.
    edits = {e.question_id: e for e in db.scalars(select(BankPersonalEdit).where(
        BankPersonalEdit.user_id == user_id, BankPersonalEdit.subject == content.subject,
        BankPersonalEdit.run_id == content.run_id))}
    available, problems = set(), {}
    for tid, task in tasks.items():
        qid = task['question_id']
        if qid not in questions or qid in suspended or decisions.get(qid) == 'excluded':
            problems[tid] = '개인 제외/일시중지 또는 문항 없음'
        elif bank_personal.apply_edit(questions[qid], edits.get(qid)).get('personalEdited'):
            problems[tid] = '개인 수정본과 연결 목표의 일치 미확인'
        else:
            available.add(tid)
    if doc.get('generation_policy')=='root-generation/2':
        from studyez_contracts.roots.generation_v2 import task_dependencies
        deps=task_dependencies(doc)
        while True:
            blocked={tid for tid in available if any(p not in available for p in deps[tid])}
            if not blocked:break
            for tid in blocked:problems[tid]='명시적 선행 문항이 준비되지 않음'
            available-=blocked
    return available, problems


def events_for(db, subject, run_id, user_id):
    return [{'id': e.request_id, 'revision': e.revision, 'kind': e.kind, 'payload': e.payload, 'at': e.created_at}
            for e in db.scalars(select(RootEvent).where(RootEvent.user_id == user_id,
                RootEvent.subject == subject, RootEvent.run_id == run_id).order_by(RootEvent.created_at, RootEvent.request_id))]


def question(doc, task):
    return next(q for q in doc['bank_snapshot']['questions'] if q['question_id'] == task['question_id'])


def front(q):
    # Allowlist, never a blacklist of all possible authoring/answer metadata.
    from studyez_contracts.bank.cloze import normalize_cloze
    result={'question_id': q['question_id'], 'concept_id': '', 'tier': 'Core', 'importance': 0,
            'format': q.get('format', 'basic'), 'mcq_mode': q.get('mcq_mode', 'none'), 'retrieval_direction': '', 'question': normalize_cloze(q)['question'],
            'source_refs': [], 'conflict_id': '', 'options': [{'id': o['id'], 'text': o['text']} for o in q.get('options', [])],
            'matching_left': q.get('matching_left', []), 'matching_right': q.get('matching_right', []),
            'sequence_items': q.get('sequence_items', [])}
    if q.get('stimuli'):
        from studyez_contracts.roots.media import public_images
        result['stimuli']=public_images(q)
    return result


def answer(q):
    return {'answer': q['answer'], 'explanation': q.get('explanation', ''),
            'answerUnits': q.get('answer_units', []), 'correctOptionIds': q.get('correct_option_ids', []),
            'answerPairs': q.get('answer_pairs', []), 'correctOrder': q.get('correct_order', []),
            'slides': [], 'optionExplanations': q.get('option_explanations', [])}

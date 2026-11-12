"""Content registration and conservative legacy-bank availability checks."""
import os
import copy
import re
from sqlalchemy import select
from sqlalchemy.orm import defer
from studyez_contracts.roots import validate_document, document_hash, direction_hash, task_fingerprints
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


def published_for(db, keys, user):
    """Lectures whose reviewed Main Quiz this user may open. Reads no document JSON."""
    if not keys or not globally_enabled():
        return set()
    wanted = set(keys)
    controls = [c for c in db.scalars(select(RootControl).where(RootControl.enabled.is_(True),
        RootControl.revision.is_not(None), RootControl.subject.in_({s for s, _ in wanted}),
        RootControl.run_id.in_({r for _, r in wanted})))
        if (c.subject, c.run_id) in wanted and (not c.allowed_users or user.id in c.allowed_users or user.is_admin)]
    if not controls:
        return set()
    reviewed = set(db.execute(select(RootContent.subject, RootContent.run_id, RootContent.revision).where(
        RootContent.reviewed.is_(True), RootContent.run_id.in_({c.run_id for c in controls}))).all())
    return {(c.subject, c.run_id) for c in controls if (c.subject, c.run_id, c.revision) in reviewed}


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
        if doc.get('generation_policy') == 'root-generation/4':
            carried_questions(previous.document, doc, link)
            continue
        try:
            same = direction_hash(previous.document, link['from_direction']) == direction_hash(doc, link['to_direction'])
        except (StopIteration, KeyError):
            same = False
        if not same:
            raise ValueError('방향/답 범위/과제/출처가 다른 기록을 승계할 수 없습니다.')
    return doc


def carried_questions(previous, doc, link):
    """root-generation/4 carry-over (spec R8): per question content fingerprint, not `direction_hash`.

    The reviewed link names the old and new direction; history then continues only for the new
    direction's tasks whose question fingerprint is among the old direction's (state.replay_tasks).
    A changed question starts fresh. Only /4 revisions record the fingerprint on their events, so an
    older-policy revision cannot be linked (it would silently carry nothing)."""
    if previous.get('generation_policy') != 'root-generation/4':
        raise ValueError('문항 단위 판(root-generation/4)은 같은 형식의 이전 판 기록만 승계할 수 있습니다.')
    try:
        old = {v for k, v in task_fingerprints(previous).items()
               if next(t for t in previous['tasks'] if t['task_id'] == k)['direction_id'] == link['from_direction']}
        new = {k for k, v in task_fingerprints(doc).items()
               if v in old and next(t for t in doc['tasks'] if t['task_id'] == k)['direction_id'] == link['to_direction']}
    except (StopIteration, KeyError):
        new = set()
    if not new:
        raise ValueError('같은 내용의 문항이 없어 기록을 승계할 수 없습니다.')
    return new


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


def excluded_ids(events, revision):
    """Main-Quiz 「이 문제 제외」(2026-11-12): 이 판에서 제외한 문항 ID. Z로 되돌린 제외는 events_for가 이미 뺐다.
    판(revision)별이다 — 새 판의 같은 ID에는 승계하지 않는다."""
    return {e['payload']['question_id'] for e in events if e['kind'] == 'exclude' and e['revision'] == revision}


def availability(db, content, user_id):
    doc = content.document
    tasks = {t['task_id']: t for t in doc['tasks']}
    excluded = excluded_ids(events_for(db, content.subject, content.run_id, user_id), content.revision)
    if doc['bank_source'] == 'standalone':
        # Main-Quiz documents are standalone. They take the same prerequisite rule as a bank source
        # (2026-11-12: an excluded prerequisite left its dependents available and order_plan raised 500).
        return close_prerequisites(doc, {tid for tid, t in tasks.items() if t['question_id'] not in excluded},
                                   {tid: '개인 제외' for tid, t in tasks.items() if t['question_id'] in excluded})
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
        if qid not in questions or qid in suspended or qid in excluded or decisions.get(qid) == 'excluded':
            problems[tid] = '개인 제외/일시중지 또는 문항 없음'
        elif bank_personal.apply_edit(questions[qid], edits.get(qid)).get('personalEdited'):
            problems[tid] = '개인 수정본과 연결 목표의 일치 미확인'
        else:
            available.add(tid)
    return close_prerequisites(doc, available, problems)


def close_prerequisites(doc, available, problems):
    """/2·/4: a task whose prerequisite task is not available is not available either (transitively).
    `planning.order_plan` requires every unassessed prerequisite of a planned task to be available."""
    if doc.get('generation_policy') in ('root-generation/2', 'root-generation/4'):
        from studyez_contracts.roots.generation_v2 import task_dependencies
        deps = task_dependencies(doc)
        while True:
            blocked = {tid for tid in available if any(p not in available for p in deps[tid])}
            if not blocked:
                break
            for tid in blocked:
                problems[tid] = '명시적 선행 문항이 준비되지 않음'
            available -= blocked
    return available, problems


def events_for(db, subject, run_id, user_id):
    """학습 집계의 입력. Z로 되돌린 답 보기·평가·보류는 없던 일로 뺀다(2026-11-11). 원본 이벤트와 undo 기록은 DB에 남는다."""
    rows = [{'id': e.request_id, 'revision': e.revision, 'kind': e.kind, 'payload': e.payload, 'at': e.created_at}
            for e in db.scalars(select(RootEvent).where(RootEvent.user_id == user_id,
                RootEvent.subject == subject, RootEvent.run_id == run_id).order_by(RootEvent.created_at, RootEvent.request_id))]
    undone = {e['payload'].get('undo') for e in rows if e['kind'] == 'undo'}
    return [e for e in rows if e['kind'] == 'undo' or e['id'] not in undone]


def tiers_for(db, doc, user_id):
    """This learner's 「내 중요도」 on the active revision (tier events only)."""
    from .state import personal_tiers
    rows = db.scalars(select(RootEvent).where(RootEvent.user_id == user_id, RootEvent.subject == doc.subject,
        RootEvent.run_id == doc.run_id, RootEvent.revision == doc.revision, RootEvent.kind == 'tier'))
    return personal_tiers(doc.document, [{'id': e.request_id, 'revision': e.revision, 'kind': e.kind,
                                          'payload': e.payload, 'at': e.created_at} for e in rows])


def original_tier(q):
    from .policy import canonical_tier
    return canonical_tier(q)


def with_tier(q, tiers):
    chosen = tiers.get(q['question_id'])
    if not chosen:
        return q
    return {**q, 'tier': chosen['tier'], 'personalTier': True, 'originalTier': chosen['originalTier']}


def task_tiers(doc, tiers):
    """Each task's tier as the learner sees it: 「내 중요도」, else the revision's tier, else Core."""
    questions = {q['question_id']: q for q in doc['bank_snapshot']['questions']}
    out = {}
    for task in doc['tasks']:
        qid = task['question_id']
        chosen = tiers.get(qid)
        out[task['task_id']] = chosen['tier'] if chosen else (original_tier(questions.get(qid, {})) or 'Core')
    return out


def focus_for(db, subject, user_id):
    """오늘 학습 중요도 필터(2026-11-12): this learner's last choice for the subject, else every tier."""
    from .policy import TIERS
    rows = focus_events(db, subject, user_id)
    # `seq` orders choices saved at the same instant (request IDs are random), as 「내 중요도」 does.
    row = max(rows, key=lambda e: (e.payload.get('seq', 0), e.created_at), default=None)
    chosen = set(row.payload.get('tiers', [])) if row else set(TIERS)
    return [t for t in TIERS if t in chosen] or list(TIERS)


def focus_events(db, subject, user_id):
    return db.scalars(select(RootEvent).where(RootEvent.user_id == user_id, RootEvent.subject == subject,
                                              RootEvent.kind == 'focus')).all()


def question(doc, task):
    return next(q for q in doc['bank_snapshot']['questions'] if q['question_id'] == task['question_id'])


def front(q):
    # Allowlist, never a blacklist of all possible authoring/answer metadata.
    from studyez_contracts.bank.cloze import normalize_cloze
    # 「내 중요도」(2026-11-09): personal tier, else the revision's tier, else Core.
    result={'question_id': q['question_id'], 'concept_id': '', 'tier': original_tier(q) or 'Core', 'importance': 0,
            'format': q.get('format', 'basic'), 'mcq_mode': q.get('mcq_mode', 'none'), 'retrieval_direction': '', 'question': normalize_cloze(q)['question'],
            'source_refs': [], 'conflict_id': '', 'options': [{'id': o['id'], 'text': o['text']} for o in q.get('options', [])],
            'matching_left': q.get('matching_left', []), 'matching_right': q.get('matching_right', []),
            'sequence_items': q.get('sequence_items', [])}
    if q.get('stimuli'):
        from studyez_contracts.roots.media import public_images
        result['stimuli']=public_images(q)
    if q.get('personalEdited'):
        result['personalEdited']=True
    if q.get('personalTier'):
        result.update(personalTier=True, originalTier=q['originalTier'] or 'Core')
    return result


def answer_units(q):
    """Units in blank order. A cloze stem's {blanks} are what front() shows, one unit each; the stored
    answer_units of a generated revision may merge rows or drop a repeated blank (2026-11-12: 92 of 696
    cloze), which shifted every later cell. An answer the learner rewrote has no units (bank_personal)."""
    units = q.get('answer_units', [])
    if q.get('format') == 'cloze' and units:
        from studyez_contracts.bank.cloze import normalize_cloze
        units = normalize_cloze(q).get('answer_units', units)
    return units


def answer(q):
    return {'answer': q['answer'], 'explanation': q.get('explanation', ''),
            'answerUnits': answer_units(q), 'correctOptionIds': q.get('correct_option_ids', []),
            'answerPairs': q.get('answer_pairs', []), 'correctOrder': q.get('correct_order', []),
            'slides': [], 'optionExplanations': q.get('option_explanations', []),
            'personalAnswer': bool(q.get('personalAnswer'))}

"""Main-Quiz 내 문제(추가·복사 후 수정)와 뒷면 메모(2026-11-15, docs/changes/2026-11-15-root-personal-questions).

둘 다 새 표 없이 append-only `root_event`에 남는다(내 중요도·Optional 제외와 같다).
- kind='mine': 내 문제 하나의 저장·삭제. 같은 mine_id의 마지막 기록이 현재 값이다.
- kind='memo': 문항 하나의 뒷면 메모. 문항마다 마지막 기록이 현재 값이고 빈 글은 지운 것이다.
둘 다 판(revision)별이다. 새 판으로 옮기지 않는다(ID만으로 승계하지 않는 규칙).

내 문제는 판 사본에 요청마다 덧붙인다(`overlay`). 캐시된 사본은 고치지 않는다. 덧붙인 사본은 계획·오늘 흐름·풀이에만
넘기고, 학습률·카드 수·목표 요약은 원래 사본으로 센다 — 그래서 내 문제는 복습 일정은 받고 학습률에는 안 들어간다.
"""
from __future__ import annotations

from dataclasses import replace

from studyez_contracts.bank.cloze import normalize_cloze
from studyez_contracts.roots.validate import question_fingerprint

from app import bank_personal
from . import content
from .light import LightDocument
from .policy import instant
from .state import per_task

PREFIX = 'mine-'
LIMIT = 300
TEXT_LIMIT = 4000
MEMO_LIMIT = 2000
DELETED = '내가 지운 문제입니다. 「이 문제 보류」로 넘어가세요.'
UNANCHORED = '이 내 문제의 기준 문항이 지금 준비되지 않았습니다.'


def is_mine(question_id: str | None) -> bool:
    return bool(question_id) and question_id.startswith(PREFIX)


def _ordered(events, kind, revision):
    rows = [e for e in events if e['kind'] == kind and e['revision'] == revision]
    # `seq` orders saves made at the same instant (request IDs are random), as 「내 중요도」 does.
    return sorted(rows, key=lambda e: (instant(e['at']), e['payload'].get('seq', 0), e['id']))


def current(events, revision):
    """(live, deleted): live는 mine_id -> 마지막 저장 payload(만든 순서), deleted는 지운 mine_id."""
    live, deleted, order = {}, set(), {}
    for event in _ordered(events, 'mine', revision):
        p = event['payload']
        order.setdefault(p['mine_id'], len(order))
        if p['action'] == 'delete':
            live.pop(p['mine_id'], None)
            deleted.add(p['mine_id'])
        else:
            live[p['mine_id']] = p
            deleted.discard(p['mine_id'])
    return dict(sorted(live.items(), key=lambda kv: order[kv[0]])), deleted


def memos(events, revision):
    """question_id -> 지금 메모(빈 글은 없음)."""
    out = {}
    for event in _ordered(events, 'memo', revision):
        p = event['payload']
        if p['text']:
            out[p['question_id']] = p['text']
        else:
            out.pop(p['question_id'], None)
    return out


def next_seq(events, kind):
    return 1 + sum(e['kind'] == kind for e in events)


def question_of(p):
    """내 문제의 문항 모양. 옛 Quiz Bank 「내가 추가한 문제」와 같은 계약(주관식, 구조 채점 없음)."""
    q = bank_personal.added_question(p['mine_id'], p['question'], p['answer'], p['tier'], p['explanation'])
    # personalAnswer는 붙이지 않는다: 그 표시는 「원래 해설이 바뀐 답과 안 맞는다」는 뜻이라 해설을 숨긴다. 내 문제의 해설은 내가 쓴 것이다.
    q.update(prerequisites=[], exam_rationale='내가 만든 문제')
    if p.get('stimuli'):
        q['stimuli'] = p['stimuli']
    if p.get('source_question_id'):
        q['sourceQuestionId'] = p['source_question_id']
    return q


def with_mine(row, live):
    """판 사본(LightRow)의 얕은 복사본에 내 문제를 덧붙인다. 기준 과제 바로 뒤, 같은 방향."""
    doc = row.document
    anchors = {t['task_id'] for t in doc['tasks']}
    attached = [p for p in live.values() if p['anchor_task_id'] in anchors]
    if not attached:
        return row
    by_anchor = {}
    for p in attached:
        by_anchor.setdefault(p['anchor_task_id'], []).append(p)
    tasks = []
    for task in doc['tasks']:
        tasks.append(task)
        tasks.extend({**task, 'task_id': p['mine_id'], 'question_id': p['mine_id']} for p in by_anchor.get(task['task_id'], []))
    questions = [question_of(p) for p in attached]
    bank = doc['bank_snapshot']
    out = LightDocument({**doc, 'tasks': tasks, 'bank_snapshot': {**bank, 'questions': [*bank['questions'], *questions]}})
    prints = getattr(doc, 'task_fingerprints', None)
    if prints is None:
        from studyez_contracts.roots import task_fingerprints
        prints = task_fingerprints(doc)
    out.task_fingerprints = {**prints, **{q['question_id']: question_fingerprint(q) for q in questions}}
    # 이전 판 기록 승계 표(2026-11-15 replace-carry-records)도 덧붙인 사본에 그대로 둔다.
    out.carried_questions = getattr(doc, 'carried_questions', None) or {}
    return replace(row, document=out)


def overlay(row, events, available, problems):
    """계획·풀이용 (덧붙인 사본, 준비된 과제, 준비 안 된 까닭). 집계용 값은 부르는 쪽이 원래 것을 그대로 쓴다.

    기준 과제가 준비된 내 문제만 준비된다. 목표 선행이 내 문제를 끌어올 수 있으므로 덧붙인 사본으로 선행을 다시 닫는다
    (준비 안 된 과제가 계획에 들어가면 order_plan이 500을 낸다)."""
    problems = dict(problems)
    if not per_task(row.document):
        return row, set(available), problems
    live, deleted = current(events, row.revision)
    for mine_id in deleted:
        problems[mine_id] = DELETED
    if not live:
        return row, set(available), problems
    mine_row = with_mine(row, live)
    extra = {m for m, p in live.items() if p['anchor_task_id'] in available}
    ready, problems = content.close_prerequisites(mine_row.document, set(available) | extra, problems)
    for mine_id in live:
        if mine_id not in ready:
            problems.setdefault(mine_id, UNANCHORED)
    return mine_row, ready, problems


def anchor_task(doc, live, question_id):
    """새 내 문제가 붙을 과제. 내 문제를 기준으로 하면 그 내 문제의 기준 과제를 따른다."""
    if is_mine(question_id):
        p = live.get(question_id)
        return p and next((t for t in doc['tasks'] if t['task_id'] == p['anchor_task_id']), None)
    return next((t for t in doc['tasks'] if t['question_id'] == question_id), None)


def draft_text(q):
    """복사에 쓸 글: 내게 보이는 발문(빈칸은 ____, 선지는 줄마다), 정답, 해설."""
    question = normalize_cloze(q)['question'].replace('{{c1}}', '____')
    options = [o['text'] for o in q.get('options', [])]
    if options:
        question += '\n' + '\n'.join(f'{i}) {text}' for i, text in enumerate(options, 1))
    return {'question': question, 'answer': q.get('answer', ''), 'explanation': q.get('explanation', '')}

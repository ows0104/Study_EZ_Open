"""Deterministic finite daily plans. No synthetic mastery or inferred prerequisites."""
from collections import defaultdict
from datetime import date, timedelta
from math import ceil
from statistics import median
from .policy import KST, instant, study_day
from .state import targets, direction_owners, replay


def plan(doc, events, available, now, policy):
    rows, states = replay(doc, events, now, policy)
    by_target = {r['id']: r for r in rows}
    owners = direction_owners(doc)
    target_list = targets(doc)
    order = {t['target_id']: i for i, t in enumerate(target_list)}
    authored = {t['target_id']: t for t in target_list}
    # One prepared task per direction. Optional directions do not replace required ones.
    candidates = {}
    for task in doc['tasks']:
        if task['task_id'] in available:
            candidates.setdefault(task['direction_id'], task)
    today = study_day(now, policy)
    day = now.astimezone(KST).date()
    deadline = date.fromisoformat(doc['exam_date']) - timedelta(days=policy['deadline_offset']) if doc['exam_date'] else None
    days = (deadline - day).days + 1 if deadline else None
    unseen = [t['target_id'] for t in target_list if not by_target[t['target_id']]['learned']
              and any(owners[d] == t['target_id'] for d in candidates)]
    quota = min(len(unseen), ceil(len(unseen) / days)) if days is not None and days > 0 else len(unseen)
    def priority(tid):
        return (not by_target[tid]['important'], order[tid])
    unseen.sort(key=priority)
    selected = []
    def add(did, reason):
        task = candidates.get(did)
        if task and not any(x['task_id'] == task['task_id'] for x in selected):
            selected.append({**task, 'reason': reason})
    for tid in unseen[:quota]:
        for direction in authored[tid]['directions']:
            add(direction['direction_id'], '새 목표')
    due = [d for d in candidates if states.get(d, {}).get('rating') is not None and
           states[d]['effectiveDue'] <= today.isoformat()]
    # A same-day failure never expands this session, or immediately creates forced repeats.
    due = [d for d in due if study_day(instant(states[d]['lastAt']), policy) != today]
    due.sort(key=lambda d: (*priority(owners[d]), states[d]['effectiveDue'], d))
    for did in due:
        add(did, '복습 확인')
    # Incomplete learned goals retain all unassessed directions, including optional detail.
    for did in candidates:
        if by_target[owners[did]]['learned'] and not states.get(did, {}).get('rating') and states.get(did, {}).get('lastDay') != today:
            add(did, '미평가 방향')
    history = defaultdict(set)
    for event in events:
        if event['kind'] == 'reveal' and event['payload'].get('attempted'):
            when = study_day(instant(event['at']), policy)
            if when < today:
                history[when].add((event['revision'], event['payload']['task_id']))
    habitual = int(median([len(history[d]) for d in sorted(history)[-7:]])) if history else None
    for tid in unseen[quota:]:
        if habitual is None or len(selected) >= habitual:
            break
        for direction in authored[tid]['directions']:
            add(direction['direction_id'], '새 범위 보완')
    # Explicit prerequisite relations reorder already-selected tasks and may bring a prepared
    # prerequisite forward. Failure on it never locks the following direction.
    chosen_targets = {owners[t['direction_id']] for t in selected}
    prereqs = defaultdict(set)
    for edge in doc['prerequisites']:
        prereqs[edge['after_target']].add(edge['before_target'])
    expanded = set()
    def prerequisites(tid, visiting):
        if tid in visiting or tid in expanded:
            return
        for parent in sorted(prereqs[tid], key=lambda p: order[p]):
            prerequisites(parent, visiting | {tid})
            if not by_target[parent]['learned']:
                for direction in authored[parent]['directions']:
                    add(direction['direction_id'], '명시적 선행 연결')
        expanded.add(tid)
    for tid in sorted(chosen_targets, key=lambda t: order[t]):
        prerequisites(tid, set())
    emitted, result = set(), []
    def emit(tid):
        if tid in emitted:
            return
        emitted.add(tid)
        for parent in sorted(prereqs[tid], key=lambda p: order[p]):
            emit(parent)
        result.extend(t for t in selected if owners[t['direction_id']] == tid)
    for task in selected:
        emit(owners[task['direction_id']])
    if doc.get('generation_policy')=='root-generation/2':
        from studyez_contracts.roots.generation_v2 import order_plan
        assessed={t['question_id']for t in doc['tasks']if states.get(t['direction_id'],{}).get('rating')is not None}
        result=order_plan(doc,result,available,assessed)
    return {'tasks': result, 'newGoalQuota': quota, 'days': days, 'habitualTasks': habitual,
            'deadline': deadline.isoformat() if deadline else None,
            'preparedUnseen': len(unseen), 'unpreparedGoals': sum(
                not any(owners[d] == t['target_id'] for d in candidates) for t in target_list),
            'scopeNote': '준비된 학습 범위 기준 · 앞으로 들어올 자료량 추정 없음'}

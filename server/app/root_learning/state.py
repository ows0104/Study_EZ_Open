"""Replay immutable events; revealing an answer never implies successful recall."""
from datetime import timedelta
from .policy import (instant, study_day, day_start, transition, effective_due, GRADE_RATING, LEGACY_MASTERY,
                     next_mastery, target_due, target_retention)


def targets(doc):
    return [t for t in doc['review']['targets'] if t['target_id'] in doc['adopted_target_ids']]


def direction_owners(doc):
    return {d['direction_id']: t['target_id'] for t in targets(doc) for d in t['directions']}


def personal_tiers(doc, events, now=None):
    """This revision's 「내 중요도」: the last tier event per question (tier null = 원래대로).

    Other revisions are never read: a question ID alone does not carry a learner's choice."""
    chosen = {}
    rows = [e for e in events if e['kind'] == 'tier' and e['revision'] == doc['revision']
            and (now is None or instant(e['at']) <= now)]
    # `seq` orders choices saved at the same instant (request IDs are random).
    for event in sorted(rows, key=lambda e: (instant(e['at']), e['payload'].get('seq', 0), e['id'])):
        p = event['payload']
        if p.get('tier') is None:
            chosen.pop(p['question_id'], None)
        else:
            chosen[p['question_id']] = {'tier': p['tier'], 'originalTier': p['originalTier']}
    return chosen


PER_TASK_POLICY = 'root-generation/4'
GRADE_ORDER = {'missed': 0, 'partial': 1, 'independent': 2}


def per_task(doc):
    """root-generation/4 documents keep learner state per task (spec R8 option B); older ones per direction."""
    return doc.get('generation_policy') == PER_TASK_POLICY


def _rate(value, event, p, when, task_questions, questions, plans, tiers):
    """One rating applied to one learner state (a direction's, or for /4 a task's). Mutates `value`."""
    # Mastery follows every rating (older ones too) so a target-scheduled rating starts from history.
    params = p.get('targetParameters')
    mastery = next_mastery(value, p.get('selfRating') or GRADE_RATING[p['grade']], when, params or LEGACY_MASTERY)
    updated = transition(value, p['grade'], p['helped'], when, p['policy'], p.get('exam_date'),
                         p.get('selfRating'), p.get('ratingParameters'))
    updated['mastery'] = mastery
    if params and p.get('selfRating') is not None:
        # Target retention: the question's tier, or the learner's current 「내 중요도」 for it.
        qid = task_questions.get(p.get('task_id'))
        q = questions.get(qid, {})
        chosen = tiers.get(qid)
        target = target_retention(q, plans.get(q.get('concept_id')), params, chosen and chosen['tier'])
        updated = target_due(updated, mastery, target, p['policy'], p.get('exam_date'))
    value.clear(); value.update(updated)


def replay(doc, events, now, policy):
    if per_task(doc):
        rows, directions, _ = replay_tasks(doc, events, now, policy)
        return rows, directions
    owners = direction_owners(doc)
    tiers = personal_tiers(doc, events, now)
    task_questions = {t['task_id']: t['question_id'] for t in doc['tasks']}
    questions = {q['question_id']: q for q in doc['bank_snapshot']['questions']}
    plans = {p['concept_id']: p for p in doc['bank_snapshot'].get('retrieval_plan', [])}
    aliases = {(e['revision'], e['from_direction']): e['to_direction'] for e in doc['equivalences']}
    events = sorted((e for e in events if instant(e['at']) <= now), key=lambda e: (instant(e['at']), e['id']))
    undone = {e['payload']['undo'] for e in events if e['kind'] == 'undo'}
    directions, first = {}, {}
    for event in events:
        p = event['payload']
        did = p.get('direction_id') if event['revision'] == doc['revision'] else aliases.get((event['revision'], p.get('direction_id')))
        if did not in owners:
            continue
        tid = owners[did]
        when = instant(event['at'])
        value = directions.setdefault(did, {'learned': False, 'rating': None, 'due': None, 'stage': -1, 'lastDay': None})
        if event['kind'] == 'reveal' and p.get('attempted'):
            value['learned'] = True
            first.setdefault(tid, when)
        elif event['kind'] == 'rate' and event['id'] not in undone:
            _rate(value, event, p, when, task_questions, questions, plans, tiers)
    for value in directions.values():
        value['effectiveDue'] = effective_due(value, now, policy, doc['exam_date'])
    today = study_day(now, policy)
    rows = []
    for target in targets(doc):
        required = [d['direction_id'] for d in target['directions'] if d['requirement'] == 'required']
        undecided = any(d['requirement'] == 'undecided' for d in target['directions'])
        values = [directions.get(d, {}) for d in required]
        recalled = bool(required) and not undecided and all(v.get('rating') == 'independent' and v['effectiveDue'] >= today.isoformat() for v in values)
        rows.append({'id': target['target_id'], 'learned': target['target_id'] in first,
                     'recalled': recalled, 'required': required, 'undecided': undecided,
                     'important': any(target['importance'][axis]['status'] == 'supported' for axis in ('exam', 'clinical')),
                     'firstAt': first.get(target['target_id'])})
    return rows, directions


def replay_tasks(doc, events, now, policy):
    """root-generation/4: rating, due date, stage and learned replayed per task_id (spec R8, option B).

    Events are unchanged facts; they already name task_id and direction_id. This revision's events count
    for their task_id. An earlier revision's event counts only through a reviewed equivalence of its
    direction, and only for the task of the linked direction whose question fingerprint equals the
    `question_sha256` the event recorded (/4 events record it): a changed question starts fresh and an
    ID alone never carries history.

    A direction's value is derived from its tasks:
    - learned: any of its tasks was attempted;
    - rating: None until any of its tasks is rated ("rated" = any rating exists), then the lowest latest
      rating among its rated tasks;
    - recalled: every task of the direction is independently recalled and not yet due;
    - due / effectiveDue: the earliest among its rated tasks; lastAt / lastDay: the latest.
    Target learned/recalled (and summary's ready) read these direction values as before.
    Returns (target rows, direction values, task values)."""
    from studyez_contracts.roots import task_fingerprints
    owners = direction_owners(doc)
    tiers = personal_tiers(doc, events, now)
    current = {t['task_id']: t for t in doc['tasks'] if t['direction_id'] in owners}
    task_questions = {t['task_id']: t['question_id'] for t in doc['tasks']}
    questions = {q['question_id']: q for q in doc['bank_snapshot']['questions']}
    plans = {p['concept_id']: p for p in doc['bank_snapshot'].get('retrieval_plan', [])}
    aliases = {(e['revision'], e['from_direction']): e['to_direction'] for e in doc['equivalences']}
    prints = task_fingerprints(doc)
    by_print = {(t['direction_id'], prints[tid]): tid for tid, t in current.items()}
    events = sorted((e for e in events if instant(e['at']) <= now), key=lambda e: (instant(e['at']), e['id']))
    undone = {e['payload']['undo'] for e in events if e['kind'] == 'undo'}
    tasks, first = {}, {}
    for event in events:
        p = event['payload']
        if event['revision'] == doc['revision']:
            task_id = p.get('task_id')
        else:
            did = aliases.get((event['revision'], p.get('direction_id')))
            task_id = by_print.get((did, p.get('question_sha256'))) if did and p.get('question_sha256') else None
        if task_id not in current:
            continue
        tid = owners[current[task_id]['direction_id']]
        when = instant(event['at'])
        value = tasks.setdefault(task_id, {'learned': False, 'rating': None, 'due': None, 'stage': -1, 'lastDay': None})
        if event['kind'] == 'reveal' and p.get('attempted'):
            value['learned'] = True
            first.setdefault(tid, when)
        elif event['kind'] == 'rate' and event['id'] not in undone:
            _rate(value, event, p, when, task_questions, questions, plans, tiers)
    for value in tasks.values():
        value['effectiveDue'] = effective_due(value, now, policy, doc['exam_date'])
    today = study_day(now, policy).isoformat()
    siblings = {}
    for task_id, task in current.items():
        siblings.setdefault(task['direction_id'], []).append(task_id)
    directions = {}
    for did, ids in siblings.items():
        if not any(i in tasks for i in ids):
            continue
        values = [tasks.get(i, {}) for i in ids]
        rated = [v for v in values if v.get('rating') is not None]
        directions[did] = {
            'taskIds': ids,
            'learned': any(v.get('learned') for v in values),
            'rating': min((v['rating'] for v in rated), key=lambda r: GRADE_ORDER.get(r, 0)) if rated else None,
            'recalled': all(v.get('rating') == 'independent' and v['effectiveDue'] >= today for v in values),
            'due': min((v['due'] for v in rated if v.get('due')), default=None),
            'effectiveDue': min((v['effectiveDue'] for v in rated if v.get('effectiveDue')), default=None),
            'lastAt': max((v['lastAt'] for v in rated if v.get('lastAt')), default=None),
            'lastDay': max((v['lastDay'] for v in values if v.get('lastDay')), default=None)}
    rows = []
    for target in targets(doc):
        required = [d['direction_id'] for d in target['directions'] if d['requirement'] == 'required']
        undecided = any(d['requirement'] == 'undecided' for d in target['directions'])
        recalled = bool(required) and not undecided and all(directions.get(d, {}).get('recalled') for d in required)
        rows.append({'id': target['target_id'], 'learned': target['target_id'] in first,
                     'recalled': recalled, 'required': required, 'undecided': undecided,
                     'important': any(target['importance'][axis]['status'] == 'supported' for axis in ('exam', 'clinical')),
                     'firstAt': first.get(target['target_id'])})
    return rows, directions, tasks


def summary(doc, events, available, now, policy):
    rows, directions = replay(doc, events, now, policy)
    ready_directions = {t['direction_id'] for t in doc['tasks'] if t['task_id'] in available}
    for row in rows:
        row['ready'] = bool(row['required']) and not row['undecided'] and set(row['required']) <= ready_directions
        if not row['ready']:
            row['recalled'] = False
        row['status'] = ('준비 전' if not row['ready'] else '회상 가능' if row['recalled'] else
                         '미학습' if not row['learned'] else '미평가' if not any(directions.get(d, {}).get('rating') for d in row['required']) else '보완 필요')
    before, _ = replay(doc, events, day_start(now, policy) - timedelta(microseconds=1), policy)
    carried, _ = replay(doc, [e for e in events if instant(e['at']) < day_start(now, policy)], now, policy)
    ready_ids = {r['id'] for r in rows if r['ready']}
    for row in [*before, *carried]:
        if row['id'] not in ready_ids:
            row['recalled'] = False
    return {'total': len(rows), 'learned': sum(r['learned'] for r in rows), 'recalled': sum(r['recalled'] for r in rows),
            'unseen': sum(not r['learned'] for r in rows), 'unready': sum(not r['ready'] for r in rows),
            'importantUnseen': sum(r['important'] and not r['learned'] for r in rows),
            'newToday': sum(r['firstAt'] is not None and r['firstAt'] >= day_start(now, policy) for r in rows),
            'recallChange': sum(r['recalled'] for r in rows) - sum(r['recalled'] for r in before),
            'recallLearningChange': sum(r['recalled'] for r in rows) - sum(r['recalled'] for r in carried),
            'recallTimeChange': sum(r['recalled'] for r in carried) - sum(r['recalled'] for r in before),
            'targets': [{k: v for k, v in r.items() if k not in ('firstAt', 'required')} for r in rows]}

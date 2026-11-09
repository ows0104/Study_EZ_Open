"""Replay immutable events; revealing an answer never implies successful recall."""
from datetime import timedelta
from .policy import instant, study_day, day_start, transition, effective_due, personal_due


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
    for event in sorted(rows, key=lambda e: (instant(e['at']), e['id'])):
        p = event['payload']
        if p.get('tier') is None:
            chosen.pop(p['question_id'], None)
        else:
            chosen[p['question_id']] = {'tier': p['tier'], 'originalTier': p['originalTier'], 'factor': p['factor']}
    return chosen


def replay(doc, events, now, policy):
    owners = direction_owners(doc)
    tiers = personal_tiers(doc, events, now)
    task_questions = {t['task_id']: t['question_id'] for t in doc['tasks']}
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
            updated = transition(value, p['grade'], p['helped'], when, p['policy'], p.get('exam_date'),
                                 p.get('selfRating'), p.get('ratingParameters'))
            # The learner's current tier re-times every four-rating result of that question.
            chosen = tiers.get(task_questions.get(p.get('task_id')))
            if chosen and p.get('selfRating') is not None:
                updated = personal_due(updated, chosen['factor'], p['policy'], p.get('exam_date'))
            value.clear(); value.update(updated)
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

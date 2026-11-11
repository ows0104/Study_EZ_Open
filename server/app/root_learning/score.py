"""Main-Quiz 학습률 — 사이트의 유일한 학습률 정의(2026-11-11 사용자 결정).

문항(학습 상태) 점수 = min(지금 숙련도 ÷ 목표치, 1). 지금 숙련도는 마지막 평가 뒤 망각 곡선으로 깎인다.
방향은 문항 평균, 지도 목표는 필수 방향 평균, 강의는 지도 목표들의 1 − RMS(1 − 점수)다.
중요도는 문항 목표치(등급·내 중요도)로 이미 들어가므로 따로 가중하지 않는다.
읽기 전용 파생값이다. 평가 저장 형식·복습일 계산은 건드리지 않는다.
"""
from math import sqrt

from .policy import instant, target_parameters, target_retention
from .state import personal_tiers, per_task, replay, replay_tasks, targets


def current_mastery(value, at):
    """평가 시점의 숙련도를 `at`까지 망각 곡선 M/(1+t/9S)로 깎는다. 평가가 없으면 0."""
    mastery = value.get('mastery') or 0
    if not mastery or not value.get('lastAt'):
        return 0.0
    elapsed = max(0.0, (instant(at) - instant(value['lastAt'])).total_seconds() / 86400)
    stability = max(0.25, value.get('ratingDays', value.get('baseDays', 1)) or 1)
    return mastery / (1 + elapsed / (9 * stability))


def coverage(scores):
    """약한 것을 더 크게: [1, 0] → 0.29, [0.5, 0.5] → 0.5."""
    return 1 - sqrt(sum((1 - s) ** 2 for s in scores) / len(scores)) if scores else 0.0


def _targets_for(doc, tiers, params):
    """학습 상태 단위(/4는 task, 이전은 direction)마다 다시 계산한 목표치. 저장된 목표치가 없을 때만 쓴다."""
    questions = {q['question_id']: q for q in doc['bank_snapshot']['questions']}
    plans = {p['concept_id']: p for p in doc['bank_snapshot'].get('retrieval_plan', [])}
    by_task, by_direction = {}, {}
    for task in doc['tasks']:
        q = questions.get(task['question_id'], {})
        chosen = tiers.get(task['question_id'])
        value = target_retention(q, plans.get(q.get('concept_id')), params, chosen and chosen['tier'])
        by_task[task['task_id']] = value
        by_direction[task['direction_id']] = max(by_direction.get(task['direction_id'], 0), value)
    return by_task, by_direction


def _unit_score(value, target, at):
    if not value or not target:
        return 0.0
    return min(current_mastery(value, at) / (value.get('target') or target), 1.0)


def lecture_score(doc, events, policy, at, *, until=None):
    """`until`까지의 평가로 `at` 시점의 학습률. 지도 목표가 없으면 score=None."""
    until = until or at
    tiers = personal_tiers(doc, events, until)
    params = target_parameters()
    task_targets, direction_targets = _targets_for(doc, tiers, params)
    if per_task(doc):
        _, _, tasks = replay_tasks(doc, events, until, policy)
        siblings = {}
        for task in doc['tasks']:
            siblings.setdefault(task['direction_id'], []).append(task['task_id'])

        def direction_score(did):
            ids = siblings.get(did) or []
            return sum(_unit_score(tasks.get(i), task_targets.get(i), at) for i in ids) / len(ids) if ids else 0.0
    else:
        _, directions = replay(doc, events, until, policy)

        def direction_score(did):
            return _unit_score(directions.get(did), direction_targets.get(did), at)

    scores, rated = [], 0
    for target in targets(doc):
        chosen = [d['direction_id'] for d in target['directions'] if d['requirement'] == 'required'] \
            or [d['direction_id'] for d in target['directions']]
        values = [direction_score(d) for d in chosen]
        scores.append(sum(values) / len(values) if values else 0.0)
        rated += any(v > 0 for v in values)
    if not scores:
        return {'score': None, 'status': 'not_started', 'targetCount': 0, 'fullTargets': 0, 'ratedTargets': 0}
    full = sum(s >= 1 for s in scores)
    status = 'mastered' if full == len(scores) else 'not_started' if not rated else 'needs_review'
    return {'score': 100 if status == 'mastered' else min(99, round(100 * coverage(scores))),
            'value': coverage(scores), 'status': status, 'targetCount': len(scores),
            'fullTargets': full, 'ratedTargets': rated}

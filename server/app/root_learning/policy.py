"""Versioned result/elapsed-time/exam scheduling, independent of legacy quizzes."""
from datetime import UTC, date, datetime, timedelta, timezone
from copy import deepcopy
import json
from math import ceil, floor, isfinite
import os

KST = timezone(timedelta(hours=9))
# /2 (2026-11-11 사용자 지시: 모든 날짜 경계는 새벽 4시): 시험까지 남은 날도 학습일(day_hour)로 센다.
# /1은 시험일만 한국 달력(자정)으로 셌다. 이미 저장된 /1 사건·회차는 /1 그대로 재생한다.
CONFIGURED_POLICY = {
    'id': 'roots-adaptive/2', 'mode': 'adaptive', 'day_hour': 4, 'deadline_offset': 2,
    'initial_days': 1, 'success_growth': 2.0, 'partial_factor': 0.5,
    'max_days': 30, 'exam_fraction': 0.25, 'exam_day': 'study',
}
EXAM_DAY_MODES = ('calendar', 'study')
# Frozen for new self-assessments; every event stores its own parameters.
FOUR_RATING_PARAMETERS = {
    'minDays': 0.25, 'maxDays': 365, 'legacyDays': 1,
    'initialDays': {'Again': 0.25, 'Hard': 0.5, 'Good': 1, 'Easy': 2},
    'growth': {'Hard': 1.1, 'Good': 2, 'Easy': 3},
    'lapseMultiplier': 0.5, 'lapseMaxDays': 1, 'minSpacingDays': 1 / 6,
}
# Quiz Bank target retention (2026-11-09, 사용자 「새 평가부터 적용」). A four-rating event saved
# with targetParameters is scheduled like Quiz Bank: mastery M is an EMA of ratings, the target
# comes from the question's tier (or the learner's 「내 중요도」), and the interval is the time for
# M/(1+t/9S) to fall to the target, t=9S(M/target-1). Earlier events keep their own schedule.
TARGET_RATING_POLICY = 'roots-four-rating/2'
TIER_POLICY = 'roots-personal-tier/1'
TIERS = ('Essential', 'Core', 'Important', 'Optional')
GRADE_RATING = {'missed': 'Again', 'partial': 'Hard', 'independent': 'Good'}
# Mastery history of events saved before targetParameters existed (Quiz Bank values on 2026-11-09).
LEGACY_MASTERY = {'alpha': 0.35, 'ratings': {'Again': 0, 'Hard': 0.45, 'Good': 0.95, 'Easy': 1}}


def target_parameters():
    """Quiz Bank's current mastery policy, frozen into each new rating event."""
    from app.study_engine.policy import DEFAULT
    return deepcopy({k: DEFAULT['mastery'][k] for k in ('alpha', 'ratings', 'maxTarget', 'targets', 'tierTargets')})


def canonical_tier(q):
    """The revision's own tier; the authored `Must-Know` spelling is `Essential`. None when absent."""
    tier = 'Essential' if q.get('tier') == 'Must-Know' else q.get('tier')
    return tier if tier in TIERS else None


def target_retention(q, plan, params, personal=None):
    """Quiz Bank target_for: a private tier or Must-Know uses its tier target, else the concept plan,
    else the importance level; never above maxTarget or the tier's own target."""
    tier = personal or canonical_tier(q) or 'Core'
    tiers = params['tierTargets']
    if personal or tier == 'Essential':
        requested = tiers[tier]
    elif plan and 'target_mastery' in plan:
        requested = plan['target_mastery']
    else:
        requested = params['targets'].get(str(q.get('importance')), tiers[tier])
    return min(requested, params['maxTarget'], tiers[tier])


def next_mastery(value, rating, when, params):
    """Quiz Bank mastery update: decay by the forgetting curve; recall restores the prior level."""
    previous = value.get('mastery', 0)
    decayed = previous
    if value.get('lastAt'):
        elapsed = max(0, (utc(when) - instant(value['lastAt'])).total_seconds() / 86400)
        stability = max(0.25, value.get('ratingDays', value.get('baseDays', 1)))
        decayed = previous / (1 + elapsed / (9 * stability))
    baseline = previous if rating in ('Good', 'Easy') else decayed
    return (1 - params['alpha']) * baseline + params['alpha'] * params['ratings'][rating]


def target_due(value, mastery, target, policy, exam_date):
    """Re-time a four-rating result to the target; stability, max_days and exam cap are unchanged."""
    days = max(0, 9 * value['ratingDays'] * (mastery / target - 1))
    maximum = policy.get('max_days', max(policy.get('intervals', [30])))
    base = min(maximum, max(1, ceil(days)))
    limit = exam_limit(exam_date, value['lastAt'], policy)
    interval = min(base, limit) if limit is not None else base
    return {**value, 'target': target, 'baseDays': base, 'scheduledDays': interval,
            'due': (value['lastDay'] + timedelta(days=interval)).isoformat()}


def validate_policy(policy):
    if (type(policy) is not dict or not isinstance(policy.get('id'), str) or not policy['id']
            or 'day_hour' not in policy or 'deadline_offset' not in policy
            or type(policy['day_hour']) is not int or not 0 <= policy['day_hour'] <= 23
            or type(policy['deadline_offset']) is not int or policy['deadline_offset'] < 0):
        raise ValueError('올바른 뿌리 학습 정책이 필요합니다.')
    if policy.get('mode') == 'adaptive':
        expected = {'id', 'mode', 'day_hour', 'deadline_offset', 'initial_days',
                    'success_growth', 'partial_factor', 'max_days', 'exam_fraction'}
        # exam_day가 없는 정책(/1)은 달력 날짜로 센다.
        if (set(policy) - {'exam_day'} != expected or policy.get('exam_day', 'calendar') not in EXAM_DAY_MODES or type(policy.get('initial_days')) is not int or policy['initial_days'] < 1
                or type(policy.get('max_days')) is not int or policy['max_days'] < policy['initial_days']
                or any(type(policy.get(k)) not in (int, float) or not isfinite(policy[k])
                       for k in ('success_growth', 'partial_factor', 'exam_fraction'))
                or policy['success_growth'] <= 1 or not 0 < policy['partial_factor'] < 1
                or not 0 < policy['exam_fraction'] <= 1):
            raise ValueError('적응형 복습 정책의 간격·시험일 설정을 확인하세요.')
    elif (set(policy) != {'id', 'intervals', 'day_hour', 'deadline_offset'}
          or type(policy['intervals']) is not list or not policy['intervals']
          or any(type(i) is not int or i < 1 for i in policy['intervals'])):
        raise ValueError('이전 간격표 정책의 형식을 확인하세요.')
    return deepcopy(policy)


def configured_policy():
    raw = os.getenv('STUDYEZ_ROOT_POLICY')
    value = json.loads(raw) if raw else CONFIGURED_POLICY
    return validate_policy(value) if value is not None else None


def utc(when):
    return when.replace(tzinfo=UTC) if when.tzinfo is None else when.astimezone(UTC)


def instant(value):
    return utc(datetime.fromisoformat(value)) if isinstance(value, str) else utc(value)


def study_day(when, policy):
    return (utc(when).astimezone(KST) - timedelta(hours=policy['day_hour'])).date()


def day_start(when, policy):
    day = study_day(when, policy)
    return datetime.combine(day, datetime.min.time(), KST).replace(hour=policy['day_hour']).astimezone(UTC)


def exam_limit(exam_date, when, policy):
    """시험까지 남은 날. `exam_day: study`(/2)는 학습일, 없으면(/1) 한국 달력 날짜로 센다."""
    if policy.get('mode') != 'adaptive' or not exam_date:
        return None
    today = study_day(when, policy) if policy.get('exam_day') == 'study' else utc(when).astimezone(KST).date()
    remaining = (date.fromisoformat(exam_date) - today).days
    return max(1, floor(remaining * policy['exam_fraction'])) if remaining >= 0 else None


def transition(value, grade, helped, when, policy, exam_date=None, self_rating=None, rating_parameters=None):
    """Return the next assessment state; never mutate an event or infer correctness."""
    when = utc(when)
    day = study_day(when, policy)
    grade = 'partial' if grade == 'independent' and helped else grade
    stage = value.get('stage', -1)
    if self_rating is not None:
        # New four-button events use the established Quiz Bank rating spacing.
        # Older immutable events continue through their original branches below.
        from app.study_engine.memory import next_stability
        last = instant(value['lastAt']) if value.get('lastAt') else None
        prior = {'reviews': 1, 'stability_days': value.get('ratingDays', value.get('baseDays', 1)),
                 'updated_at': int(last.timestamp() * 1000)} if last else {}
        rating_days = next_stability(prior, self_rating, int(when.timestamp() * 1000),
                                     {'forgetting': rating_parameters or FOUR_RATING_PARAMETERS})
        if last and study_day(last, policy) == day and self_rating != 'Again':
            rating_days = prior['stability_days']
        maximum = policy.get('max_days', max(policy.get('intervals', [30])))
        base = min(maximum, max(1, ceil(rating_days)))
        limit = exam_limit(exam_date, when, policy)
        interval = min(base, limit) if limit is not None else base
        return {**value, 'rating': grade, 'selfRating': self_rating, 'ratingDays': min(maximum, rating_days),
                'stage': -1, 'baseDays': base, 'scheduledDays': interval,
                'due': (day + timedelta(days=interval)).isoformat(), 'lastDay': day, 'lastAt': when}
    if policy.get('mode') == 'adaptive':
        initial = policy['initial_days']
        previous = max(initial, value.get('baseDays', initial))
        last = instant(value['lastAt']) if value.get('lastAt') else None
        elapsed = max(0, (when - last).total_seconds() / 86400) if last else initial
        if grade == 'independent':
            if last is None:
                base = initial
            elif study_day(last, policy) == day:
                base = previous  # Repetition in one activity day is not interval evidence.
            else:
                base = ceil(max(previous, elapsed * policy['success_growth']))
        elif grade == 'partial':
            base = ceil(min(previous, max(initial, elapsed)) * policy['partial_factor'])
        else:
            base = initial
        base = min(policy['max_days'], max(initial, base))
        limit = exam_limit(exam_date, when, policy)
        interval = min(base, limit) if limit is not None else base
        stage = -1
    else:
        # Previously stored interval-table sessions/events keep their original semantics.
        if grade == 'independent':
            if value.get('lastDay') != day:
                stage = min(stage + 1, len(policy['intervals']) - 1)
            base = interval = policy['intervals'][max(0, stage)]
        else:
            stage, base, interval = -1, 1, 1
    previous = {k: v for k, v in value.items() if k not in ('selfRating', 'ratingDays')}
    return {**previous, 'rating': grade, 'stage': stage, 'baseDays': base, 'scheduledDays': interval,
            'due': (day + timedelta(days=interval)).isoformat(), 'lastDay': day, 'lastAt': when}


def effective_due(value, when, policy, exam_date):
    """Anchor exam compression to the last assessment so due dates cannot drift away."""
    if not value.get('due'):
        return None
    due = date.fromisoformat(value['due'])
    limit = exam_limit(exam_date, when, policy)
    if limit is not None and value.get('lastAt'):
        due = min(due, study_day(instant(value['lastAt']), policy) + timedelta(days=limit))
    return due.isoformat()


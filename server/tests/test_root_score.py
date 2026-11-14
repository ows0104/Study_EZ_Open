"""Main-Quiz 학습률(docs/changes/2026-11-11-main-quiz-learning-rate spec R1)."""
import copy
import json
from datetime import timedelta
from pathlib import Path

from tests.root_support import POLICY, NOW
from app.root_learning.policy import target_parameters
from app.root_learning.score import DISPLAY_TARGET_SCALE, _unit_score, coverage, current_mastery, lecture_score

PARAMS = target_parameters()
FIXTURE = json.loads((Path(__file__).parent / 'fixtures/root_generation_v2_import.json').read_text(encoding='utf-8'))


def v4_document(revision='v4a'):
    """test_root_learning_v4와 같은 모양: D1에 문항 셋(Q1·Q3·Q4), D2에 Q2. 계산만 보므로 검증·해시는 생략."""
    doc = copy.deepcopy(FIXTURE['result']['document'])
    doc.update(generation_policy='root-generation/4', revision=revision)
    bank = doc['bank_snapshot']
    for i in (3, 4):
        q = copy.deepcopy(bank['questions'][0])
        q.update(question_id=f'Q{i}')
        bank['questions'].append(q)
    doc['tasks'] = [{'task_id': 'task-q1', 'question_id': 'Q1', 'direction_id': 'D1'},
                    {'task_id': 'task-q3', 'question_id': 'Q3', 'direction_id': 'D1'},
                    {'task_id': 'task-q4', 'question_id': 'Q4', 'direction_id': 'D1'},
                    {'task_id': 'task-q2', 'question_id': 'Q2', 'direction_id': 'D2'}]
    return doc


def rated(task_id, direction_id, at, grade='independent', revision='v4a', **extra):
    return [{'id': 'reveal-' + task_id + str(at), 'kind': 'reveal', 'revision': revision, 'at': at,
             'payload': {'task_id': task_id, 'direction_id': direction_id, 'attempted': True, 'policy': POLICY, **extra}},
            {'id': 'rate-' + task_id + str(at), 'kind': 'rate', 'revision': revision, 'at': at + timedelta(seconds=1),
             'payload': {'task_id': task_id, 'direction_id': direction_id, 'grade': grade, 'helped': False,
                         'policy': POLICY, 'exam_date': '2026-12-20', **extra}}]


def good(task_id, direction_id, at, rating='Good', revision='v4a', params=True):
    """사분 평가 한 번. params=False면 targetParameters가 없던 11-09 이전 평가."""
    extra = {'selfRating': rating}
    if params:
        extra.update(ratingPolicy='roots-four-rating/2', targetParameters=PARAMS)
    return rated(task_id, direction_id, at, 'independent', revision, **extra)


def split(doc):
    """지도 목표 둘: T1=D1, T2=D2. 계산은 문서 검증을 거치지 않으므로 그대로 고친다."""
    doc = copy.deepcopy(doc)
    t1 = doc['review']['targets'][0]
    t2 = copy.deepcopy(t1)
    t2['target_id'] = 'T2'
    t1['directions'] = [d for d in t1['directions'] if d['direction_id'] == 'D1']
    t2['directions'] = [d for d in t2['directions'] if d['direction_id'] == 'D2']
    doc['review']['targets'].append(t2)
    doc['adopted_target_ids'] = ['T1', 'T2']
    return doc


def many(events, at, rating='Good'):
    """같은 문항을 날마다 여러 번 Good — 숙련도가 목표치까지 오르게."""
    out = []
    for i in range(12):
        out += [dict(e, id=e['id'] + f'-{i}', at=e['at'] + timedelta(days=i)) for e in events]
    return out


# 1. 약한 것을 더 크게: [1, 0] → 29, [0.5, 0.5] → 50.
assert round(100 * coverage([1, 0])) == 29 and round(100 * coverage([0.5, 0.5])) == 50
assert coverage([]) == 0

doc = v4_document()
every_task = ['task-q1', 'task-q3', 'task-q4']

# 2. 평가가 없으면 0, 상태 not_started.
empty = lecture_score(doc, [], POLICY, NOW)
assert empty['score'] == 0 and empty['status'] == 'not_started' and empty['targetCount'] == 1

# 3. 문항 하나 Good 한 번은 부분 점수: 0보다 크고 100보다 작다.
once = good('task-q1', 'D1', NOW)
one = lecture_score(doc, once, POLICY, NOW + timedelta(minutes=1))
assert 0 < one['score'] < 100 and one['status'] == 'needs_review', one

# 4. 모든 문항을 목표치까지 올리면 그 직후 100(mastered).
full_events = []
for task, direction in [*[(t, 'D1') for t in every_task], ('task-q2', 'D2')]:
    full_events += good(task, direction, NOW + timedelta(seconds=len(full_events)))
full_events = many(full_events, NOW)
last = max(e['at'] for e in full_events)
top = lecture_score(doc, full_events, POLICY, last + timedelta(minutes=1))
assert top['score'] == 100 and top['status'] == 'mastered', top

# 5. 같은 기록으로 시간이 지나면 단조 감소, 오래 지나도 0으로 뚝 떨어지지 않는다.
values = [lecture_score(doc, full_events, POLICY, last + timedelta(days=d))['value'] for d in (0, 30, 90, 180, 365)]
assert all(a >= b for a, b in zip(values, values[1:])) and values[-1] < values[0], values
assert values[-1] > 0, values

# 6. 평가 시각(until)과 계산 시각(at)을 따로 준다: 지난 기록만으로 미래 시점을 본다.
past_only = lecture_score(doc, full_events, POLICY, last + timedelta(days=60), until=NOW + timedelta(minutes=1))
assert past_only['value'] < lecture_score(doc, full_events, POLICY, last + timedelta(days=60))['value']

# 7. 목표치가 저장되지 않은 옛 평가(11-09 이전)도 지금 정책의 목표치로 점수가 나온다.
legacy = lecture_score(doc, good('task-q1', 'D1', NOW, params=False), POLICY, NOW + timedelta(minutes=1))
assert 0 < legacy['score'] < 100, legacy

# 8. 지도 목표 단위로 묶는다: 문항 셋이 붙은 T1이 문항 하나인 T2보다 무겁지 않다.
two = split(doc)
d2_full = many(good('task-q2', 'D2', NOW), NOW)
d1_full = many(sum((good(t, 'D1', NOW + timedelta(seconds=i)) for i, t in enumerate(every_task)), []), NOW)
end = NOW + timedelta(days=12)
only_t2 = lecture_score(two, d2_full, POLICY, end)
only_t1 = lecture_score(two, d1_full, POLICY, end)
assert only_t2['score'] == only_t1['score'] == 29, (only_t1, only_t2)     # [1, 0]
assert only_t1['fullTargets'] == only_t2['fullTargets'] == 1

# 9. 옛 문서(방향 단위 상태)도 계산된다.
old = FIXTURE['result']['document']
d1 = old['tasks'][0]['task_id']
old_events = many(rated(d1, 'D1', NOW, 'independent', old['revision'], selfRating='Good',
                        ratingPolicy='roots-four-rating/2', targetParameters=PARAMS), NOW)
old_score = lecture_score(old, old_events, POLICY, end)
assert old_score['targetCount'] == 1 and 0 < old_score['score'] < 100, old_score   # D2는 0

# 10. 지금 숙련도: 평가 없으면 0, 시간이 지나면 줄어든다.
assert current_mastery({}, NOW) == 0
state = {'mastery': 0.9, 'lastAt': NOW, 'ratingDays': 2}
assert current_mastery(state, NOW) == 0.9 > current_mastery(state, NOW + timedelta(days=5)) > 0
# 11. 보이는 값만 목표치의 절반 기준(2026-11-14): 절반이면 100%, 4분의 1이면 50%. 계획 기준(기본 1)은 그대로.
assert DISPLAY_TARGET_SCALE == 0.5
half = {'mastery': 0.4, 'lastAt': NOW, 'ratingDays': 2, 'target': 0.8}
assert _unit_score(half, 0.8, NOW, DISPLAY_TARGET_SCALE) == 1.0
assert abs(_unit_score(dict(half, mastery=0.2), 0.8, NOW, DISPLAY_TARGET_SCALE) - 0.5) < 1e-9
assert _unit_score(dict(half, mastery=0.9), 0.8, NOW, DISPLAY_TARGET_SCALE) == 1.0   # 1에서 자른다
assert abs(_unit_score(half, 0.8, NOW) - 0.5) < 1e-9                                 # 계획 기준
plan_view = lecture_score(doc, once, POLICY, NOW + timedelta(minutes=1))
shown = lecture_score(doc, once, POLICY, NOW + timedelta(minutes=1), target_scale=DISPLAY_TARGET_SCALE)
assert plan_view == one and shown['value'] > plan_view['value'], (plan_view, shown)
print('test_root_score ok')

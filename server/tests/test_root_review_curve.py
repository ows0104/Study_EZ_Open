"""복습 간격(docs/changes/2026-11-18-review-curve R1·R2, 2026-11-18-review-curve-2 R1~R6)."""
from datetime import timedelta
from tests.root_support import NOW, POLICY
from app.root_learning import policy
from app.root_learning.policy import (FOUR_RATING_PARAMETERS, ROOT_MASTERY, curve_parameters, curve_schedule,
                                      effective_due, next_mastery, transition)

V3 = policy.target_parameters()
V2 = {k: v for k, v in V3.items() if k not in ROOT_MASTERY}
CURVE = curve_parameters()
TARGETS = {'Essential': 0.9, 'Core': 0.85, 'Important': 0.78, 'Optional': 0.55}
GRADE = {'Again': 'missed', 'Hard': 'partial', 'Good': 'independent', 'Easy': 'independent'}


def days(ratings, tier, horizon=45, late_at=None, exam=None):
    """Study-day offsets of each review when it is taken on its due day (state._rate's order).
    `late_at`: the review after this index is taken twice as late as planned."""
    value, when, out = {'stage': -1, 'lastDay': None, 'rating': None}, NOW, []
    for i, rating in enumerate(ratings):
        offset = (when - NOW).days
        if offset >= horizon:
            break
        out.append(offset)
        mastery = next_mastery(value, rating, when, V3)
        updated = transition(value, GRADE[rating], False, when, POLICY, exam, rating, FOUR_RATING_PARAMETERS)
        updated['mastery'] = mastery
        value = curve_schedule(value, updated, rating, when, TARGETS[tier], tier, POLICY, exam, CURVE)
        when = when + timedelta(days=value['scheduledDays'] * (2 if late_at == i else 1))
    return out


assert policy.TARGET_RATING_POLICY == 'roots-four-rating/4' and CURVE['policy'] == 'roots-curve/1'

# R1·R2·R3: the spec table (first 45 days). Again/Hard follow the tier; repeated Hard and Again still spread out.
expected = {
    'Again': {'Essential': list(range(20))[:20], 'Core': [0, 1, 2, 3, 4, 5, 6, 8, 10, 12, 14, 16, 18, 20],
              'Optional': [0, 2, 5, 8, 12, 16, 21, 27, 34, 42]},
    'Hard': {'Essential': [0, 1, 2, 3, 5, 7, 9, 12, 16, 21, 27, 34, 43], 'Core': [0, 1, 3, 5, 7, 10, 13, 17, 22, 29, 38],
             'Important': [0, 2, 4, 7, 10, 14, 19, 26, 34], 'Optional': [0, 4, 9, 16, 25, 36]},
    'Good': {'Essential': [0, 1, 3, 7, 15, 31], 'Core': [0, 2, 6, 13, 26], 'Important': [0, 3, 9, 20, 41],
             'Optional': [0, 8, 23]},
    'Easy': {'Essential': [0, 2, 9, 34], 'Core': [0, 4, 15], 'Important': [0, 6, 24], 'Optional': [0, 15]},
}
for rating, tiers in expected.items():
    for tier, want in tiers.items():
        got = days([rating] * 20, tier)
        assert got[:len(want)] == want, (rating, tier, got)
# R4 difficulty: a question first missed grows slower afterwards than one first known.
assert days(['Again'] + ['Good'] * 10, 'Core') == [0, 1, 2, 4, 7, 11, 19, 34]
assert days(['Hard'] + ['Good'] * 10, 'Core') == [0, 1, 3, 6, 12, 23, 43]
# R5 late bonus: a correct recall twice as late as planned grows S more than an on-time one.
assert days(['Good'] * 10, 'Core', late_at=1) == [0, 2, 10, 20, 40]
# Same study day: a second Good moves neither S nor D; a second Again still holds S at one day.
first = curve_schedule({}, {'lastDay': NOW.date(), 'lastAt': NOW}, 'Good', NOW, 0.85, 'Core', POLICY, None, CURVE)
again = curve_schedule({**first, 'rating': 'independent'}, {}, 'Good', NOW + timedelta(hours=1), 0.85, 'Core', POLICY, None, CURVE)
assert (again['curveDays'], again['difficulty']) == (first['curveDays'], first['difficulty']) == (1, 0.5)

# R6 exam: Essential/Core keep the exam compression, Important/Optional follow their curve.
exam = (NOW + timedelta(days=12)).date().isoformat()
core = curve_schedule({}, {}, 'Easy', NOW, 0.85, 'Core', POLICY, exam, CURVE)
optional = curve_schedule({}, {}, 'Easy', NOW, 0.55, 'Optional', POLICY, exam, CURVE)
assert core['examPressure'] and core['scheduledDays'] == 3 < core['baseDays'] == 4, core
assert not optional['examPressure'] and optional['scheduledDays'] == optional['baseDays'] == 15, optional
later = NOW + timedelta(days=9)
assert effective_due({**optional, 'lastAt': NOW}, later, POLICY, exam) == optional['due']
assert effective_due({**core, 'lastAt': NOW}, later, POLICY, exam) < core['due']

# Older first parts still hold: /2 events are read with /3's mastery; a four-button rating keeps its grade after help.
assert policy.replay_parameters({'ratingPolicy': 'roots-four-rating/2', 'targetParameters': V2}) == V3
assert policy.replay_parameters({'selfRating': 'Good'}) is None
assert next_mastery({}, 'Hard', NOW, V3) == 0.45 and next_mastery({}, 'Hard', NOW, V2) == 0.35 * 0.45
empty = {'stage': -1, 'lastDay': None, 'rating': None}
assert transition(empty, 'independent', True, NOW, POLICY, None, 'Easy')['rating'] == 'independent'
assert transition(empty, 'independent', True, NOW, POLICY)['rating'] == 'partial'
print('PASS: /4 curve by tier for all four ratings, difficulty, late bonus, same-day hold, exam tiers, /3 mastery, kept self-rating')

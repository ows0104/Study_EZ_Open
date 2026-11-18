"""쉬운 문항이 곡선대로 빠진다(docs/changes/2026-11-18-review-curve spec R1·R2)."""
from datetime import timedelta
from tests.root_support import NOW, POLICY
from app.root_learning import policy
from app.root_learning.policy import FOUR_RATING_PARAMETERS, ROOT_MASTERY, next_mastery, target_due, transition

V3 = policy.target_parameters()
V2 = {k: v for k, v in V3.items() if k not in ROOT_MASTERY}
TARGETS = {'Essential': 0.9, 'Core': 0.85, 'Important': 0.78, 'Optional': 0.55}


def days(ratings, target, params, horizon=30):
    """Study-day offsets of each review when every review is taken on its due day (state._rate's order)."""
    value, when, out = {'stage': -1, 'lastDay': None, 'rating': None}, NOW, []
    for rating in ratings:
        offset = (when - NOW).days
        if offset >= horizon:
            break
        out.append(offset)
        mastery = next_mastery(value, rating, when, params)
        value = transition(value, 'missed' if rating == 'Again' else 'independent', False, when, POLICY, None, rating,
                           FOUR_RATING_PARAMETERS)
        value['mastery'] = mastery
        value = target_due(value, mastery, target, POLICY, None)
        when = when + timedelta(days=value['scheduledDays'])
    return out


assert V3['ratingAlpha'] == {'Good': 0.5, 'Easy': 0.7} and V3['firstFromRating'] is True
assert policy.TARGET_RATING_POLICY == 'roots-four-rating/3'

# R1: the spec table, first 30 days.
expected = {
    ('Easy', 'Essential'): [0, 3, 10, 29], ('Easy', 'Core'): [0, 4, 14], ('Easy', 'Important'): [0, 6, 22],
    ('Easy', 'Optional'): [0, 15],
    ('Good', 'Essential'): [0, 1, 3, 6, 10, 16, 25], ('Good', 'Core'): [0, 2, 5, 10, 19],
    ('Good', 'Important'): [0, 2, 6, 14], ('Good', 'Optional'): [0, 7, 21]}
for (rating, tier), want in expected.items():
    got = days([rating] * 20, TARGETS[tier], V3)
    assert got == want, (rating, tier, got)

# /2's own parameters brought Easy Core back four days in a row.
assert days(['Easy'] * 20, 0.85, V2) == [0, 1, 2, 3, 4, 8, 23]
# R3: stored /2 events are replayed with /3's mastery; events without targetParameters are left alone.
assert policy.replay_parameters({'ratingPolicy': 'roots-four-rating/2', 'targetParameters': V2}) == V3
assert policy.replay_parameters({'ratingPolicy': 'roots-four-rating/3', 'targetParameters': V3}) == V3
assert policy.replay_parameters({'selfRating': 'Good'}) is None
# A hard question stays: Again then Good comes back daily four times (was six).
assert days(['Again'] + ['Good'] * 20, 0.85, V3)[:7] == [0, 1, 2, 3, 4, 6, 10]
assert days(['Again'] + ['Good'] * 20, 0.85, V2)[:7] == [0, 1, 2, 3, 4, 5, 6]
# First rating is the level itself only once; a stored mastery keeps the EMA.
assert next_mastery({}, 'Hard', NOW, V3) == 0.45 and next_mastery({}, 'Hard', NOW, V2) == 0.35 * 0.45
assert abs(next_mastery({'mastery': 0.5}, 'Easy', NOW, V3) - (0.3 * 0.5 + 0.7)) < 1e-12

# R2: a four-button rating keeps the learner's grade after help; three-grade events keep the downgrade.
empty = {'stage': -1, 'lastDay': None, 'rating': None}
assert transition(empty, 'independent', True, NOW, POLICY, None, 'Easy')['rating'] == 'independent'
assert transition(empty, 'independent', True, NOW, POLICY)['rating'] == 'partial'
print('PASS: /3 first rating and faster recall gains, spec schedule, /2 retimed on replay, self-rating kept after help')

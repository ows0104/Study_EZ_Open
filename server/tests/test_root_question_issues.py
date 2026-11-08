"""Main-Quiz 답의 검토 기록은 이 문항을 가리키는 것만 싣는다(2026-11-08 사용자 지시).

감염병리1 판은 회차 전체 메모 다섯 줄이 98문항 모든 답에 똑같이 붙었다. 메모 원본은 생성 기록에 그대로 남는다.
"""
from tests.root_support import setup
setup()
from app.routes.root_learning import question_issues

run_wide = [
    'This is a deliberately narrower study bank, not full-source coverage.',
    'Neutral priority removes only unproven importance claims: all axes for Q085,Q051,Q055 must lack evidence.',
    'Q0851 is a different, longer id.',
    'Historical examination evidence is limited (Q05 only).',
    {'question_id': 'Q051', 'message': 'dict-shaped validation warning'},
]
assert question_issues(run_wide, 'Q085') == [run_wide[1]]
assert question_issues(run_wide, 'Q051') == [run_wide[1], run_wide[4]]
assert question_issues(run_wide, 'Q05') == [run_wide[3]]
assert question_issues(run_wide, 'Q011') == []
assert question_issues([], 'Q011') == []
print('PASS: review issues are kept only when they name this question (token match, dicts included)')

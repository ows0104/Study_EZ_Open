"""관리자 「생성·검수 결과」: review-relations/2 판은 지도에 못 붙은 문항을 개수만이 아니라 목록으로 보인다
(docs/changes/2026-11-14-map-relation-guard, D 「멈추지 말고 보고」)."""
from tests.root_support import setup
setup()
from app.routes.root_generation import build_report


def result(extra):
    meta = {'pipelineVersion': 'root-generation/4', 'addRounds': 1, 'fixes': [], 'notReady': [], 'mergedDuplicates': [],
            'unplacedQuestions': [{'question_id': 'Q2', 'reason': 'no-relation: 문항 검토가 이 문항이 묻는 지도 관계를 적지 않았다'}],
            'importanceNotes': [], **extra}
    return {'manifest': meta, 'brief': {'targets': [{'target_id': 'T1'}]},
            'document': {'tasks': [{'task_id': 't1'}], 'bank_snapshot': {'questions': [{'question_id': 'Q2', 'question': 'A의 원인은?'}]}},
            'validation': {'errors': [], 'warnings': []}, 'medical': {'reviews': []},
            'sourceAudit': {'question_checks': {'reviews': []}, 'review': {'coverage': []}}}


report = build_report(result({'coverageFallback': [{'question_id': 'Q1', 'direction_id': 'D1'}]}))
assert report['coverageFallback'] == 1 and report['unplacedQuestions'] == 1
assert report['unplacedList'] == [{'question_id': 'Q2', 'reason': 'no-relation: 문항 검토가 이 문항이 묻는 지도 관계를 적지 않았다',
                                   'question': 'A의 원인은?'}]
print('PASS review-relations/2 report lists the questions left off the map with reason and text')

old = build_report(result({}))
assert 'coverageFallback' not in old and 'unplacedList' not in old and old['unplacedQuestions'] == 1
print('PASS a review-relations/1 report keeps its old fields')

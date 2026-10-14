import copy

import pytest

from quizbank import review, web_audit
from server.app.bank_validation import pool_checks
from server.app.bank_validation.choices import pool_review_identity


def sample_bank():
    return {'source_conflicts': [], 'questions': [{'question_id': 'Q1', 'format': 'mcq',
        'question': '옳은 것은?', 'correct_option_ids': ['A'], 'mcq_mode': 'comparison',
        'option_pools': [{'pool_id': 'P1', 'correct_when': 'true', 'select_count': 2,
            'candidates': [{'candidate_id': f'C{i}', 'true_text': f'참 {i}', 'false_text': f'거짓 {i}',
                           'true_explanation': '참 근거', 'false_explanation': '정정 근거',
                           'source_refs': [{'source_id': 'S1', 'locator': 'p1'}]} for i in range(3)]}]}]}


def checks(bank):
    return [{**{k: c[k] for k in ('question_id', 'pool_id', 'candidate_id', 'content_hash')},
             'true_verdict': 'ok', 'false_verdict': 'ok', 'criterion_verdict': 'ok',
             'note': '두 명제와 같은 선택 조건을 확인한 테스트 응답'} for c in pool_checks.candidates(bank)]


def report(bank, rows):
    return {'summary': '모두 검수했다', 'reviews': [{'question_id': 'Q1', 'verdict': 'ok',
             'note': '', 'suggested_answer': ''}], 'pool_checks': rows}


@pytest.mark.parametrize('problem', ['missing', 'duplicate', 'unknown', 'extra_unknown', 'stale', 'blank_note', 'malformed', 'invalid_id'])
def test_unchecked_candidates_never_receive_a_pool_approval(problem):
    bank = sample_bank()
    rows = checks(bank)
    if problem == 'missing': rows.pop()
    elif problem == 'duplicate': rows.append(copy.deepcopy(rows[0]))
    elif problem == 'unknown': rows[0]['candidate_id'] = 'UNKNOWN'
    elif problem == 'extra_unknown': rows.append({**rows[0], 'candidate_id': 'UNKNOWN'})
    elif problem == 'stale': rows[0]['content_hash'] = 'old'
    elif problem == 'blank_note': rows[0]['note'] = ''
    elif problem == 'invalid_id': rows[0]['candidate_id'] = []
    else: rows[0] = None
    shaped = review.shape(report(bank, rows), bank)
    assert shaped['poolCoverage']['status'] == 'incomplete'
    assert shaped['requiresRevision']
    assert 'option_pool_hash' not in shaped['reviews'][0]


def test_content_and_condition_changes_invalidate_candidate_attestation():
    bank = sample_bank()
    shaped = review.shape(report(bank, checks(bank)), bank)
    q = bank['questions'][0]
    assert pool_checks.reviewed_ok(q, shaped['reviews'][0])
    for edit in ('true_text', 'false_explanation', 'question', 'correct_when'):
        changed = copy.deepcopy(q)
        if edit == 'question': changed['question'] = '옳지 않은 것은?'
        elif edit == 'correct_when': changed['option_pools'][0]['correct_when'] = 'false'
        else: changed['option_pools'][0]['candidates'][0][edit] = 'changed'
        assert not pool_checks.reviewed_ok(changed, shaped['reviews'][0])
    assert not pool_checks.reviewed_ok(q, {'verdict': 'ok', 'option_pool_hash': pool_review_identity(q)})


def test_candidate_verdicts_override_a_conflicting_parent_ok():
    bank = sample_bank()
    rows = checks(bank)
    rows[1]['false_verdict'] = 'wrong'
    shaped = review.shape(report(bank, rows), bank)
    assert shaped['counts']['wrong'] == 1
    assert 'P1/C1' in shaped['reviews'][0]['note']
    assert not pool_checks.reviewed_ok(bank['questions'][0], shaped['reviews'][0])


def test_source_review_is_bound_to_actual_candidates_even_when_summary_says_no_pool():
    bank = sample_bank()
    raw = {'summary': '보기 풀이 없다', 'pages': [{'page': 1, 'status': 'checked', 'note': ''}],
           'checks': [{'point_id': 'P', 'status': 'covered', 'question_ids': ['Q1'], 'note': '목표 확인'}],
           'question_issues': [], 'plan_issues': [], 'duplicates': [],
           'classifications': [{'question_id': 'Q1', 'recommended_mode': 'comparison', 'reason': '비교'}],
           'pool_checks': []}
    points = [{'point_id': 'P', 'point': '목표', 'source_refs': 'S1 p.1'}]
    missing = web_audit.shape_report(raw, bank, points, 1)
    assert missing['requiresRevision'] and missing['poolCoverage']['expectedCount'] == 3
    raw['pool_checks'] = checks(bank)
    raw['pool_checks'][0]['true_verdict'] = 'doubt'
    checked = web_audit.shape_report(raw, bank, points, 1)
    assert checked['poolCoverage']['checkedCount'] == 3
    assert checked['webAudit']['question_issues'][0]['severity'] == 'doubt'
    rebuilt = web_audit.shape_report(checked['webAudit'], bank, points, 1)
    assert len(rebuilt['webAudit']['question_issues']) == 1

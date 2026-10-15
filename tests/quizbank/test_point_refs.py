import copy
import json

import pytest

from quizbank.point_refs import checked_plan
from quizbank.session import SessionError
from tests.quizbank.test_question_first import plan


def test_reference_repair_uses_one_cli_call_and_preserves_the_original(tmp_path):
    raw = plan()
    raw['objectives'][0]['retrieval_targets'][0]['slides'] = [2]
    raw['rejected_candidates'] = [{'slides': [1], 'reason': 'Cover'}]
    fixed = copy.deepcopy(raw)
    fixed['objectives'][0]['slides'] = [2]
    work = tmp_path / 'source-only'
    work.mkdir()
    calls = []
    def call(prompt, schema, cwd, model, label):
        calls.append(label)
        assert cwd == work and not (cwd / 'bank.json').exists()
        assert json.loads((cwd / 'reference-plan.json').read_text(encoding='utf-8')) == raw
        return fixed, {'seconds': 1}
    result, usage = checked_plan(raw, 2, work, tmp_path, None, call)
    assert len(calls) == len(usage) == 1 and result['unreadable_pages'] == []
    assert raw['objectives'][0]['slides'] == [1]
    assert (tmp_path / 'independent-plan.reference-repair.raw.json').is_file()


@pytest.mark.parametrize('invalid', ['content', 'still_invalid', 'id', 'excluded'])
def test_reference_repair_never_changes_content_or_retries_a_failed_repair(tmp_path, invalid):
    raw = plan()
    raw['objectives'][0]['retrieval_targets'][0]['slides'] = [2]
    fixed = copy.deepcopy(raw)
    fixed['objectives'][0]['slides'] = [1, 2]
    if invalid == 'content':
        fixed['objectives'][0]['retrieval_targets'][0]['target'] = 'Changed medical target'
    elif invalid == 'id':
        fixed['objectives'][0]['retrieval_targets'][0]['point_id'] = 'New-ID'
    elif invalid == 'excluded':
        fixed['rejected_candidates'].append({'slides': [1], 'reason': 'New exclusion'})
    else:
        fixed['objectives'][0]['slides'] = [1]
    calls = []
    def call(*args):
        calls.append(args)
        return fixed, {}
    with pytest.raises(SessionError):
        checked_plan(raw, 2, tmp_path, tmp_path, None, call)
    assert len(calls) == 1


def test_valid_plans_and_other_failures_do_not_trigger_reference_repair(tmp_path):
    def no_call(*args):
        pytest.fail('Unexpected CLI repair')
    assert checked_plan(plan(), 1, tmp_path, tmp_path, None, no_call)[1] == []
    broken = plan()
    broken['objectives'][0]['objective_id'] = ''
    with pytest.raises(SessionError, match='ID'):
        checked_plan(broken, 1, tmp_path, tmp_path, None, no_call)

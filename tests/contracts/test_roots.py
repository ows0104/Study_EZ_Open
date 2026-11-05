import copy
import importlib.util
from pathlib import Path
import pytest
from studyez_contracts.roots import validate_document, direction_hash

spec = importlib.util.spec_from_file_location('root_fixture', Path(__file__).with_name('root_fixture.py'))
fixture = importlib.util.module_from_spec(spec); spec.loader.exec_module(fixture)


def test_shared_review_consumed_without_mutation_and_unknown_required_direction_retained():
    doc = fixture.document(); before = copy.deepcopy(doc)
    assert validate_document(doc) == doc and doc == before
    assert len(doc['adopted_target_ids']) == 3
    assert 'D4' not in {t['direction_id'] for t in doc['tasks']}


@pytest.mark.parametrize('change', [
    lambda d: d['adopted_target_ids'].append('T1'),
    lambda d: d['tasks'][0].update(direction_id='absent'),
    lambda d: d['tasks'][0].update(question_id='absent'),
    lambda d: d['review']['mappings'][0].update(tested_relation_ids=[],provided_relation_ids=['R1']),
    lambda d: d['review']['coverage'][2].update(status='covered',confirmed_direction_ids=['D4'],unknown_direction_ids=[]),
    lambda d: d['bank_snapshot']['questions'][0].update(answer='changed'),
    lambda d: d.update(extra_mastery=1),
])
def test_invalid_or_unconfirmed_task_cannot_become_a_ready_direction(change):
    doc=fixture.document();change(doc)
    with pytest.raises((ValueError, KeyError)):
        validate_document(doc)


def test_identity_includes_answer_scope_question_and_source_but_not_layout_or_revision():
    doc=fixture.document(); modified=copy.deepcopy(doc)
    modified.update(revision='v2',title='Layout only')
    assert direction_hash(doc,'D1') == direction_hash(modified,'D1')
    modified['review']['targets'][0]['directions'][0]['answer_scope']='changed'
    assert direction_hash(doc,'D1') != direction_hash(modified,'D1')

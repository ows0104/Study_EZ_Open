import copy

from tests.quizbank.test_repair import bank
from server.app.bank_validation.publication import stamp, usable, warning
from server.app.bank_validation.validate import validate_bank


def leaked_bank(bank):
    candidate = copy.deepcopy(bank)
    candidate['build_meta']['schema_version'] = '3.1'
    question = next(q for q in candidate['questions'] if q['format'] == 'basic')
    question['question'] = ' '.join(question['answer_units'])
    return candidate


def test_publication_retains_failed_content_checks_and_original_questions(bank):
    candidate = leaked_bank(bank)
    checked = validate_bank(candidate, ['S1', 'S2'])
    assert not checked['pass']
    original = copy.deepcopy(candidate)
    marked = stamp(candidate, checked, ['S1', 'S2'], allow_unresolved=True)
    assert not marked['pass'] and marked['errors'] == checked['errors']
    assert usable(candidate, marked) and warning(candidate, marked)
    assert candidate == original
    candidate['questions'][0]['question'] += ' changed'
    assert not usable(candidate, marked)


def test_broken_ids_cannot_be_published_even_with_claimed_pass(bank):
    candidate = copy.deepcopy(bank)
    candidate['questions'][0]['question_id'] = candidate['questions'][1]['question_id']
    marked = stamp(candidate, {'pass': True}, ['S1', 'S2'], allow_unresolved=True)
    assert not marked['publication']['allowed'] and not usable(candidate, marked)


def test_unrequested_or_forged_publication_stamp_is_removed(bank):
    marked = stamp(bank, {'pass': False, 'publication': {'allowed': True}}, ['S1', 'S2'], allow_unresolved=False)
    assert 'publication' not in marked and not usable(bank, marked)
    assert usable(bank, {'pass': True})


def test_duplicate_wording_is_preserved_and_can_be_published(bank):
    candidate = copy.deepcopy(bank)
    first = next(q for q in candidate['questions'] if q['format'] == 'basic')
    duplicate = copy.deepcopy(first)
    duplicate['question_id'] = 'DUPLICATE'
    duplicate['prerequisites'] = []
    candidate['questions'].append(duplicate)
    checked = validate_bank(candidate, ['S1', 'S2'])
    assert any('중복 발문' in e for e in checked['errors'])
    marked = stamp(candidate, checked, ['S1', 'S2'], allow_unresolved=True)
    assert not marked['pass'] and usable(candidate, marked)
    assert len(candidate['questions']) == len(bank['questions']) + 1

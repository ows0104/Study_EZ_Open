"""Intake keeps going when a resolved source conflict's linked questions miss one of its sources
(docs/changes/2026-11-11-intake-conflict-warning). 261111_02 picornavirus: CF02 cited S1 and S2, P062 cited S1."""
import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'contracts'))
import generation_v2_fixture as f
from quizbank.connection_generate_v3 import intake_rejections
from studyez_contracts.bank.validate import validate_bank


def _gap_bank():
    bank = copy.deepcopy(f.old.bank())
    q = bank['questions'][0]
    bank['source_conflicts'] = [{'conflict_id': 'CF02', 'description': 'S2 25쪽 선지는 각막염, S1 24쪽은 결막염. 결막염 채택.',
                                 'source_refs': [{'source_id': 'S1', 'locator': '물리 24쪽'},
                                                 {'source_id': 'S2', 'locator': '물리 25쪽'}],
                                 'unresolved': False}]
    q['conflict_id'] = 'CF02'
    q['source_refs'] = [r for r in q['source_refs'] if r['source_id'] == 'S1'] or [{'source_id': 'S1', 'locator': '물리 24쪽'}]
    if 'conflict_ids' in bank.get('build_meta', {}):
        bank['build_meta']['conflict_ids'] = ['CF02']
    return bank


def test_a_conflict_citation_gap_is_printed_and_does_not_stop(capsys):
    errors = validate_bank(_gap_bank(), ['S1', 'S2'])['errors']
    assert 'CF02: S2 기준 문항 누락' in errors
    assert intake_rejections(errors) == []
    assert 'CF02: S2 기준 문항 누락' in capsys.readouterr().out


def test_other_bank_level_errors_still_stop():
    with pytest.raises(Exception, match='특정 문항에 속하지 않습니다'):
        intake_rejections(['CF02: S2 기준 문항 누락', 'retrieval_plan: ID/값 중복'])


def test_question_errors_still_leave_only_that_question_out():
    assert intake_rejections(['CF02: S2 기준 문항 누락', 'Q7: OX 정답은 O 또는 X']) == [
        {'question_id': 'Q7', 'error': 'Q7: OX 정답은 O 또는 X'}]


def test_prefixed_question_id_is_a_question_error():
    assert intake_rejections(['ST-Q061: integration의 기초 문항 필요']) == [
        {'question_id': 'ST-Q061', 'error': 'ST-Q061: integration의 기초 문항 필요'}]
    with pytest.raises(Exception):
        intake_rejections(['retrieval_plan: ID/값 중복'])

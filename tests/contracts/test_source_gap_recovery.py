"""A required_gap that also names optional directions: deterministic split and its recovery proof.

2026-11-08 261104_02 source-0 listed D044–D048 (only D046 required) in one required_gap; the whole
review was rejected. The split keeps the reviewer's text and questions, moves only the optional ids.
"""
import copy
import pytest
import generation_v2_fixture as f
from studyez_contracts.roots import generation_v2 as c, document_hash
from studyez_contracts.roots.source_assessment import envelope


def case():
    b = f.brief(); b['targets'][0]['directions'][1]['requirement'] = 'optional'
    bank = f.old.bank(); a = f.assessment(b, bank)
    a['issues'] = [{'issue_id': 'I1', 'kind': 'required_gap', 'text': 'Synthetic missing recall',
                    'question_ids': [bank['questions'][0]['question_id']], 'direction_ids': ['D1', 'D2']}]
    return b, bank, envelope(b, bank, a)


def issues(raw):
    return raw['assessment']['issues']


def test_mixed_required_gap_is_rejected_then_split_into_gap_and_extension():
    b, bank, raw = case()
    with pytest.raises(ValueError, match='required gaps must reference required directions'):
        c.compile_assessment(b, bank, raw)
    fixed, splits = c.split_required_gaps(b, raw)
    assert splits == [{'issue_id': 'I1', 'required': ['D1'], 'optional': ['D2']}]
    assert [(i['issue_id'], i['kind'], i['direction_ids']) for i in issues(fixed)] == [
        ('I1', 'required_gap', ['D1']), ('I1-optional', 'optional_extension', ['D2'])]
    assert all(i['text'] == 'Synthetic missing recall' for i in issues(fixed))
    c.compile_assessment(b, bank, fixed)
    assert issues(raw)[0]['direction_ids'] == ['D1', 'D2']  # the model's raw review is not touched


def test_only_optional_becomes_extension_and_valid_or_unmapped_gaps_stay():
    b, bank, raw = case()
    issues(raw)[0]['direction_ids'] = ['D2']
    fixed, splits = c.split_required_gaps(b, raw)
    assert [(i['issue_id'], i['kind']) for i in issues(fixed)] == [('I1', 'optional_extension')] and splits
    for ids in (['D1'], [], ['D9']):
        b, bank, raw = case(); issues(raw)[0]['direction_ids'] = ids
        fixed, splits = c.split_required_gaps(b, raw)
        assert fixed == raw and splits == []


def proof_case():
    b, bank, raw = case()
    stages = {'normalize': {'status': 'completed', 'inputHash': 'a' * 64, 'outputHash': 'b' * 64, 'rawOutputHash': 'c' * 64},
              'generate': {'status': 'completed', 'inputHash': 'd' * 64, 'outputHash': 'e' * 64, 'rawOutputHash': 'f' * 64,
                           'usageHash': '0' * 64, 'briefHash': document_hash(b)},
              'source-0': {'status': 'failed', 'inputHash': '7' * 64, 'rawOutputHash': document_hash(raw), 'usageHash': '8' * 64,
                           'clinicalContextHash': '9' * 64}}
    old = {'identity': '1' * 64, 'pipelineVersion': c.POLICY, 'repairRounds': 1, 'stages': stages}
    _fixed, splits = c.split_required_gaps(b, raw)
    proof = {'priorLedger': old, 'priorLedgerHash': document_hash(old), 'packetHash': '2' * 64, 'currentRuntimeHash': '3' * 64,
             'reason': 'mixed required_gap', 'stage': 'source-0',
             'rejection': 'assessment2: required gaps must reference required directions; unmapped goals need map_fix',
             'brief': b, 'originalRaw': raw, 'splits': splits, 'toolSha256': '4' * 64, 'modelReplay': False}
    now = copy.deepcopy(stages)
    now['source-0'].update(status='completed', outputHash='5' * 64)
    meta = {'sourceGapRecoveries': [{'proof': proof, 'proofHash': document_hash(proof)}], 'inputHash': '2' * 64,
            'runtimeHash': '3' * 64, 'repairRounds': 1}
    return meta, {k: {'name': k, **v} for k, v in now.items()}


def test_recovery_proof_is_accepted_and_tampering_is_rejected():
    meta, stages = proof_case()
    assert c.validate_source_gap_recoveries(meta, stages)
    assert c.accepted_source_raw_hash(meta, 'source-0') != stages['source-0']['rawOutputHash']
    assert c.accepted_source_raw_hash(meta, 'source-1') is None

    def broken(edit):
        m, s = proof_case(); edit(m, s)
        p = m['sourceGapRecoveries'][0]['proof']; m['sourceGapRecoveries'][0]['proofHash'] = document_hash(p)
        with pytest.raises(ValueError):
            c.validate_source_gap_recoveries(m, s)

    broken(lambda m, s: m['sourceGapRecoveries'][0]['proof'].update(splits=[]))           # not the deterministic split
    broken(lambda m, s: m['sourceGapRecoveries'][0]['proof'].update(modelReplay=True))
    broken(lambda m, s: m.update(repairRounds=0))                                        # budget reset
    broken(lambda m, s: s['source-0'].update(rawOutputHash='6' * 64))                    # model output replaced
    broken(lambda m, s: s['generate'].update(briefHash='6' * 64))                        # another brief
    broken(lambda m, s: m['sourceGapRecoveries'][0]['proof'].update(rejection='other failure'))

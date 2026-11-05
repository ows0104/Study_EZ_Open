"""Validate the public preview provenance contract independently of its producer."""
from copy import deepcopy
import pytest
from studyez_contracts.preview_sources import fingerprint, professor_names, professor_text, validate


def example():
    value = dict(version=1, year=2026, currentProfessors=['김범준'], currentSource='notes',
                 date='2026-11-05', startTime='09:00', baselineYear=2025,
                 baselineProfessors=['방예지'], baselineFilename='[251101_01] 포도알균.pdf',
                 changed=True, newProfessor=False, status='ok', reason='동일 교수 최신 보유 필기',
                 coverage=dict(available=[2025, 2023, 2022, 2021], missing=[2024], incomplete=[], failed=[]),
                 selected=dict(year=2023, filename='[231101_01] 포도알균.pdf', professors=['김범준'],
                               sha256='a'*64, sizeBytes=100, match='same'))
    value['fingerprint'] = fingerprint(value)
    return value


def test_public_roundtrip_has_no_paths_or_mutable_aliases():
    source = example()
    public = validate(source)
    public['coverage']['available'].clear()
    assert source['coverage']['available']
    assert professor_names(['김 범준', '김범준']) == ['김범준']
    assert professor_text('김범준, 방예지') == ['김범준', '방예지']


@pytest.mark.parametrize('mutate', [
    lambda v: v.update(path='C:/private/notes.pdf'),
    lambda v: v['selected'].update(filename='C:/private/notes.pdf'),
    lambda v: v['selected'].update(year=2020),
    lambda v: v['selected'].update(sha256='unverified'),
    lambda v: v['coverage']['available'].append(2020),
    lambda v: v['coverage']['missing'].clear(),
    lambda v: v.update(newProfessor='true'),
    lambda v: v.update(currentSource='guessed'),
])
def test_rejects_malformed_or_private_provenance(mutate):
    value = deepcopy(example())
    mutate(value)
    with pytest.raises(ValueError):
        validate(value)

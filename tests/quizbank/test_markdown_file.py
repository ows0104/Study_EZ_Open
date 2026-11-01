import hashlib
import json
from pathlib import Path
import pytest
from server.app.bank_validation.markdown_file import validate

FIXTURES = Path(__file__).resolve().parents[1] / 'fixtures'
RAW = (FIXTURES / 'bank-file-valid.md').read_text(encoding='utf-8')
CASES = json.loads((FIXTURES / 'bank-file-cases.json').read_text(encoding='utf-8'))
NAME = 'study-ez-261006_02-bank.md'


def test_all_formats_and_byte_fingerprint():
    for raw in (RAW, '\ufeff' + RAW.replace('\n', '\r\n')):
        info = validate(raw, NAME, '약리학', '261006_02')
        assert info['questionCount'] == 8
        assert info['sha256'] == hashlib.sha256(raw.encode()).hexdigest()
        assert info['byteLength'] == len(raw.encode())
        assert validate(raw, NAME, '약리학', '261006_02', info) == info
        with pytest.raises(ValueError, match='SHA-256'):
            validate(raw, NAME, '약리학', '261006_02', {**info, 'sha256': '0' * 64})


@pytest.mark.parametrize('case', CASES, ids=lambda c: c['name'])
def test_same_invalid_file_cases_as_browser(case):
    changed = RAW.replace(case['old'], case['new'], 1)
    assert changed != RAW
    with pytest.raises(ValueError):
        validate(changed, NAME, '약리학', '261006_02')


def test_file_identity_and_real_file_structure_are_required():
    for raw, name, subject, run_id in [(RAW, 'other.md', '약리학', '261006_02'),
                                      (RAW, NAME, 'Other', '261006_02'),
                                      ('```md\n' + RAW + '\n```', NAME, '약리학', '261006_02')]:
        with pytest.raises(ValueError):
            validate(raw, name, subject, run_id)

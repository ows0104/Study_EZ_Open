"""Bind explicit candidate checks to the actual stem, rule and truth pairs."""
from collections import Counter

from .choices import pool_review_identity
from .content import fingerprint

VERDICTS = ('ok', 'doubt', 'wrong')
CHECK_SCHEMA = {
    'type': 'array', 'items': {
        'type': 'object', 'additionalProperties': False,
        'properties': {
            **{k: {'type': 'string'} for k in ('question_id', 'pool_id', 'candidate_id', 'content_hash', 'note')},
            **{k: {'type': 'string', 'enum': list(VERDICTS)}
               for k in ('true_verdict', 'false_verdict', 'criterion_verdict')},
        },
        'required': ['question_id', 'pool_id', 'candidate_id', 'content_hash',
                     'true_verdict', 'false_verdict', 'criterion_verdict', 'note'],
    },
}


def candidates(bank: dict) -> list[dict]:
    rows = []
    for q in bank['questions']:
        for pool in q.get('option_pools', []):
            for candidate in pool['candidates']:
                rows.append({
                    'question_id': q['question_id'], 'pool_id': pool['pool_id'],
                    **candidate,
                    'content_hash': fingerprint([pool_review_identity(q), pool['pool_id'], candidate['candidate_id']]),
                    'question': q['question'], 'format': q['format'],
                    'correct_when': pool['correct_when'], 'select_count': pool['select_count'],
                    'correct_count': len(q['correct_option_ids']),
                })
    return rows


def key(row: dict) -> tuple:
    return tuple(row.get(k) for k in ('question_id', 'pool_id', 'candidate_id'))


def verdict(row: dict) -> str:
    return max((row[k] for k in ('true_verdict', 'false_verdict', 'criterion_verdict')), key=VERDICTS.index)


def assess(bank: dict, checks: list[dict]) -> tuple[dict, list[dict]]:
    """Completeness comes from candidate identities, never the prose summary."""
    manifest = candidates(bank)
    expected = {key(row): row for row in manifest}
    candidate_duplicates = [k for k, n in Counter(key(row) for row in manifest).items() if n > 1]
    invalid_records = 0
    if not isinstance(checks, list):
        checks, invalid_records = [], 1
    records = [row for row in checks if isinstance(row, dict)
               and all(isinstance(row.get(k), str) for k in ('question_id', 'pool_id', 'candidate_id'))]
    invalid_records += len(checks) - len(records)
    checks = records
    occurrences = Counter(key(row) for row in checks)
    valid, invalid, stale = [], [], []
    for row in checks:
        identity = key(row)
        if identity not in expected or occurrences[identity] != 1:
            continue
        if row.get('content_hash') != expected[identity]['content_hash']:
            stale.append(identity)
        elif not all(row.get(k) in VERDICTS for k in ('true_verdict', 'false_verdict', 'criterion_verdict')) \
                or not isinstance(row.get('note'), str) or not row['note'].strip():
            invalid.append(identity)
        else:
            valid.append(row)
    seen = {key(row) for row in valid}
    missing = sorted(expected.keys() - seen)
    unexpected = [identity for identity in occurrences if identity not in expected]
    duplicates = [identity for identity, count in occurrences.items() if count > 1]
    incomplete = bool(missing or unexpected or duplicates or stale or invalid or invalid_records or candidate_duplicates)
    counts = Counter(verdict(row) for row in valid)
    return {
        'status': 'incomplete' if incomplete else 'verified',
        'expectedCount': len(expected), 'checkedCount': len(valid),
        'missing': missing, 'unexpected': unexpected, 'duplicates': duplicates,
        'stale': stale, 'invalid': invalid,
        'invalidRecords': invalid_records, 'candidateDuplicates': candidate_duplicates,
        'counts': {v: counts[v] for v in VERDICTS},
    }, valid


def notes(checks: list[dict]) -> list[dict]:
    return [{'question_id': row['question_id'], 'verdict': verdict(row),
             'note': f"{row['pool_id']}/{row['candidate_id']}: {row['note']}"}
            for row in checks if verdict(row) != 'ok']


def reviewed_ok(question: dict, review: dict) -> bool:
    """Unattested legacy reviews use fixed choices until explicitly rechecked."""
    if review.get('verdict') != 'ok' or review.get('option_pool_hash') != pool_review_identity(question):
        return False
    coverage, _ = assess({'questions': [question]}, review.get('pool_checks', []))
    return coverage['status'] == 'verified' and not coverage['counts']['wrong'] and not coverage['counts']['doubt']

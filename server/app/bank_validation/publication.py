"""Publication permission is separate from authoring and medical review verdicts."""
from .coverage import bank_hash
from .validate import validate_bank

WARNING = '미해결 검수 항목이 있는 문제은행입니다. 정답의 검토 표시와 수정·제보를 확인하세요.'


def stamp(bank: dict, validation: dict, source_ids: list[str], *, allow_unresolved: bool) -> dict:
    result = {k: v for k, v in validation.items() if k != 'publication'}
    if allow_unresolved:
        structural = validate_bank(bank, source_ids, check_quality=False)
        result['publication'] = {'allowed': structural['pass'], 'bankHash': bank_hash(bank),
            'structuralValidation': structural,
            'hasUnresolved': bool(not validation.get('pass') or validation.get('revision'))}
    return result


def usable(bank: dict | None, validation: dict | None) -> bool:
    if not bank:
        return False
    validation = validation or {}
    publication = validation.get('publication')
    if publication is None:
        return bool(validation.get('pass'))
    return bool(publication.get('allowed') and publication.get('bankHash') == bank_hash(bank)
                and (publication.get('structuralValidation') or {}).get('pass'))


def warning(bank: dict | None, validation: dict | None) -> str:
    publication = (validation or {}).get('publication') or {}
    return WARNING if usable(bank, validation) and publication.get('hasUnresolved') else ''

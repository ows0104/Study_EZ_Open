"""Read verified exam evidence and source issues without changing question/review judgments."""
from .slide_focus import question_hash

CATEGORIES = {'exam_only', 'partial_support', 'source_conflict', 'unsupported', 'uncertain'}

def current(report: dict | None, original: dict, presented: dict | None = None) -> dict | None:
    if not isinstance(report, dict) or report.get('version') != 1:
        return None
    if presented and (presented.get('personalEdited') or presented.get('personalAnswer') or (presented.get('choice_variant') or {}).get('poolId')):
        return None
    record = report.get('questions', {}).get(original.get('question_id')) or {}
    if record.get('questionHash') != question_hash(original):
        return None
    base = record.get('base') or {}
    return base if base.get('category') in CATEGORIES and base.get('reason', '').strip() else None

def primary_references(report: dict | None, original: dict, presented: dict | None = None) -> list[dict]:
    base = current(report, original, presented)
    if not base or base['category'] != 'exam_only':
        return []
    core = base.get('examCore') or {}
    pages = core.get('pages') or []
    mode = core.get('mode')
    if mode not in ('single', 'linked') or mode == 'single' and len(pages) != 1 or mode == 'linked' and len(pages) < 2:
        return []
    if any(not p.get('filename') or not p.get('pdfFilename') or type(p.get('page')) is not int or p['page'] < 1
           or not p.get('evidence', '').strip() for p in pages):
        return []
    return pages

def status(report: dict | None, original: dict, presented: dict | None = None, *, focus: dict | None = None) -> dict | None:
    base = current(report, original, presented)
    if not base:
        # New selector reports can show an issue before an exam image has been connected.
        if presented and (presented.get('personalEdited') or presented.get('personalAnswer') or (presented.get('choice_variant') or {}).get('poolId')):
            return None
        record = (focus or {}).get('questions', {}).get(original.get('question_id')) or {}
        selection = record.get('base') or {}
        if record.get('questionHash') != question_hash(original) or selection.get('mode') != 'unresolved':
            return None
        category = selection.get('unresolved_cause')
        if category not in CATEGORIES or not selection.get('reason', '').strip():
            return None
        base = {'category': category, 'reason': selection['reason']}
    return {'category': base['category'], 'reason': base['reason'], 'missingClaim': base.get('missingClaim', '')}

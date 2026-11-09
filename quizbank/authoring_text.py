"""Internal IDs in student-facing question text.

Students read the question, answer, explanation and options. Point, question, concept, target,
direction and relation IDs belong to authoring (exam_rationale, point_ids, source_refs). Repair
rounds of 26110901 (사슬알균) wrote explanations such as 「P018의 화농성 질환 분류 범위 보완.」 and
「… Q015에서 통합 회상한다.」: the authoring history instead of the medicine.

Only IDs that exist in this bank or brief are counted, and only those with both a letter and a
digit, so medical notation (P450, C5a, 「A군」) is not mistaken for an ID.
"""
import re

_STUDENT_TEXT = ('question', 'answer', 'explanation')
_STUDENT_LISTS = ('options', 'option_explanations', 'matching_left', 'matching_right', 'sequence_items')


def _texts(q):
    for key in _STUDENT_TEXT:
        if isinstance(q.get(key), str):
            yield key, q[key]
    for i, unit in enumerate(q.get('answer_units') or []):
        if isinstance(unit, str):
            yield 'answer_units', unit
    for key in _STUDENT_LISTS:
        for row in q.get(key) or []:
            if isinstance(row, str):
                yield key, row
            elif isinstance(row, dict):
                for field, value in row.items():
                    if isinstance(value, str) and not field.endswith('_id'):
                        yield key + '.' + field, value


def _known_ids(bank, brief):
    ids = set()
    for q in bank.get('questions', []):
        ids.add(q.get('question_id'))
        ids.update(q.get('point_ids') or [])
    brief = brief or {}
    for key, field in (('concepts', 'concept_id'), ('relations', 'relation_id'), ('targets', 'target_id'),
                       ('points', 'point_id')):
        ids.update(row.get(field) for row in brief.get(key, []) if isinstance(row, dict))
    for target in brief.get('targets', []):
        ids.update(d.get('direction_id') for d in target.get('directions', []) if isinstance(d, dict))
    return {i for i in ids if isinstance(i, str) and re.search(r'[A-Za-z]', i) and re.search(r'\d', i)}


def internal_id_mentions(bank, brief):
    """[{question_id, field, id, text}] for every internal ID found in student-facing text."""
    known = _known_ids(bank, brief)
    if not known:
        return []
    pattern = re.compile(r'(?<![A-Za-z0-9])(' + '|'.join(map(re.escape, sorted(known, key=len, reverse=True)))
                         + r')(?![A-Za-z0-9])')
    found = []
    for q in bank.get('questions', []):
        for field, text in _texts(q):
            for match in dict.fromkeys(pattern.findall(text)):
                found.append({'question_id': q.get('question_id'), 'field': field, 'id': match, 'text': text})
    return found

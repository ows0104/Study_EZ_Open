"""Source-reviewed priority metadata without regenerating or editing quiz content."""
from __future__ import annotations
import copy
import hashlib
import json
from collections import Counter
from pathlib import Path
import jsonschema
from . import priority
from .points import _object, _array, STR, INT
from .session import SessionError

TIERS = {'type': 'string', 'enum': [*priority.IMPORTANCE, 'Advanced']}
STATUS = {'type': 'string', 'enum': ['verified', 'uncertain']}
EVIDENCE = {'status': STATUS, 'recommended_tier': TIERS,
            'recommended_importance': {'type': 'integer', 'minimum': 1, 'maximum': 5},
            'source_refs': _array(STR), 'evidence': STR, 'reason': STR}
REPORT = _object({'summary': STR, 'pages_checked': _array(INT),
    'questions': _array(_object({'question_id': STR, **EVIDENCE,
        'tested_target': STR, 'basis': {'type': 'string', 'enum': list(priority.BASIS)}})),
    'concepts': _array(_object({'concept_id': STR, **EVIDENCE})), 'limitations': _array(STR)})
Q_FIELDS = {'tier', 'importance'}
C_FIELDS = {'tier', 'importance', 'importance_rationale'}


def digest(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def content(bank):
    value = copy.deepcopy(bank)
    for question in value['questions']:
        for key in Q_FIELDS:
            question.pop(key, None)
    for concept in value['concepts']:
        for key in C_FIELDS:
            concept.pop(key, None)
    return value


def review_targets(bank):
    """Exact source-review targets, independent of order and priority labels.

    A new publication may reuse CLI decisions only when every question and
    concept is identical. Source and policy fingerprints are checked by the
    caller; learning plans and publication timestamps are never copied.
    """
    stripped = content(bank)
    return {name: {item[key]: item for item in stripped[name]}
            for name, key in [('questions', 'question_id'), ('concepts', 'concept_id')]}


def criteria_text():
    source = (Path(__file__).parents[1] / 'content/prompts/bank/bankPrompt.md').read_text(encoding='utf-8')
    return source.split('### 3.3 중요도와 독립된 심화 표시', 1)[1].split('## 4.', 1)[0].strip()


def apply(bank, report, page_count):
    jsonschema.validate(report, REPORT)
    if Counter(report['pages_checked']) != Counter(range(1, page_count + 1)):
        raise SessionError('중요도 검수: 원본 전체 쪽의 확인 기록이 필요합니다.')
    for name, key in [('questions', 'question_id'), ('concepts', 'concept_id')]:
        if Counter(row[key] for row in report[name]) != Counter(item[key] for item in bank[name]):
            raise SessionError('중요도 검수: 모든 기존 ID를 중복 없이 확인해야 합니다.')
        for row in report[name]:
            if not row['reason'].strip() or not row['evidence'].strip():
                raise SessionError('중요도 검수: 근거와 판단 이유가 필요합니다.')
            if row['status'] == 'verified' and (not row['source_refs'] or not all(ref.strip() for ref in row['source_refs'])):
                raise SessionError('중요도 검수: 확인된 분류에는 실제 출처가 필요합니다.')
            if row['status'] == 'verified' and row['recommended_importance'] != priority.IMPORTANCE.get(row['recommended_tier']):
                raise SessionError('중요도 검수: 등급·중요도 수치가 일치해야 합니다.')
    questions = {q['question_id']: q for q in bank['questions']}
    checks = []
    for row in report['questions']:
        if row['status'] != 'verified':
            continue
        original = questions[row['question_id']]
        checks.append({**row, 'recommended_advanced': original.get('advanced', False),
                       'advanced_reason': '기존 심화 표시는 중요도 전용 검수에서 변경하지 않음', 'essential_target': ''})
    if checks:
        priority.assess({'questions': [questions[row['question_id']] for row in checks]}, checks)
    result = copy.deepcopy(bank)
    qrows = {row['question_id']: row for row in report['questions']}
    crows = {row['concept_id']: row for row in report['concepts']}
    changes = []
    for item in result['questions']:
        row = qrows[item['question_id']]
        if row['status'] == 'verified':
            if (item['tier'], item['importance']) != (row['recommended_tier'], row['recommended_importance']):
                changes.append({'question_id': item['question_id'], 'before': item['tier'], 'after': row['recommended_tier']})
            item.update(tier=row['recommended_tier'], importance=row['recommended_importance'])
    for item in result['concepts']:
        row = crows[item['concept_id']]
        if row['status'] == 'verified':
            item.update(tier=row['recommended_tier'], importance=row['recommended_importance'],
                        importance_rationale=f"{row['evidence']} {row['reason']}")
    if content(result) != content(bank):
        raise SessionError('중요도 검수: 중요도 외 데이터가 바뀌었습니다.')
    return result, {'changedQuestions': len(changes), 'changes': changes,
        'uncertainQuestions': [row['question_id'] for row in report['questions'] if row['status'] == 'uncertain'],
        'uncertainConcepts': [row['concept_id'] for row in report['concepts'] if row['status'] == 'uncertain'],
        'before': dict(Counter(q['tier'] for q in bank['questions'])),
        'after': dict(Counter(q['tier'] for q in result['questions']))}

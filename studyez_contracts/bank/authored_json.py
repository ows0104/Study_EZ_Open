"""Pure authored-file v2 contract and lossless, deterministic BANK conversion."""
from __future__ import annotations

import copy
import hashlib
import json
import re

from .cloze import INLINE, normalize_cloze
from .schema import DIRECTIONS, QUESTION, SCHEMA_VERSION

MAX_BYTES = 8_000_000
MAX_CHARS = 2_000_000
FORMATS = ('basic', 'list', 'cloze', 'ox', 'mcq', 'multi_select')
IMPORTANCE = {'Must-Know': 5, 'Core': 5, 'Important': 4, 'Optional': 2}


def require(value, message):
    if not value:
        raise ValueError(message)


def json_version(version):
    match = re.fullmatch(r'(\d+)\.(\d+)', version or '')
    return bool(match and tuple(map(int, match.groups())) >= (1, 80))


def _object(value, required, optional=()):
    require(type(value) is dict and set(required) <= value.keys()
            and value.keys() <= set(required) | set(optional), 'JSON 객체의 필수·허용 필드를 확인하세요.')


def _text(value):
    require(type(value) is str and bool(value.strip()), '비어 있지 않은 문자열이 필요합니다.')


def _strings(value):
    require(type(value) is list, '문자열 배열이 필요합니다.')
    for item in value:
        _text(item)


def _refs(value):
    require(type(value) is list and bool(value), '출처가 필요합니다.')
    for ref in value:
        _object(ref, ('source_id', 'locator'))
        require(type(ref['source_id']) is str and re.fullmatch(r'S[1-9]\d*', ref['source_id']), '출처 ID가 올바르지 않습니다.')
        _text(ref['locator'])


def _evidence(value):
    _object(value, ('mode', 'slides', 'reference_pages', 'reason', 'jokbo'))
    mode, slides = value['mode'], value['slides']
    require(mode in ('single', 'linked', 'unresolved') and type(slides) is list, '근거 mode·slides를 확인하세요.')
    require((mode == 'single' and len(slides) == 1) or (mode == 'linked' and len(slides) >= 2)
            or (mode == 'unresolved' and not slides), '근거 mode와 핵심 지면 수가 다릅니다.')
    _text(value['reason'])
    pages = []
    for slide in slides:
        _object(slide, ('page', 'evidence'))
        require(type(slide['page']) is int and 0 < slide['page'] <= 9007199254740991, '실제 PDF 쪽 번호가 필요합니다.')
        _text(slide['evidence'])
        pages.append(slide['page'])
    refs = value['reference_pages']
    require(type(refs) is list and all(type(p) is int and 0 < p <= 9007199254740991 for p in refs), '참고 쪽 번호를 확인하세요.')
    require(len(set(pages)) == len(pages) and len(set(refs)) == len(refs) and not set(pages) & set(refs), '근거 쪽 번호가 중복됐습니다.')
    require(type(value['jokbo']) is list, '족보 근거 배열이 필요합니다.')
    for item in value['jokbo']:
        _object(item, ('year', 'number'))
        _text(item['year']); _text(item['number'])


def validate_document(doc):
    _object(doc, ('schema_version', 'subject', 'run_id', 'prompt_version', 'complete',
                  'question_count', 'question_ids', 'conflict_ids', 'questions', 'source_conflicts'), ('generation_id',))
    require(type(doc['schema_version']) is int and doc['schema_version'] == 2 and doc['complete'] is True,
            'JSON 파일의 schema_version=2·complete=true가 필요합니다.')
    _text(doc['subject']); _text(doc['run_id'])
    require(json_version(doc['prompt_version']), '순수 JSON은 프롬프트 1.80 이상을 사용하세요.')
    if 'generation_id' in doc:
        require(type(doc['generation_id']) is str and re.fullmatch(r'[a-f0-9]{32}', doc['generation_id']), 'generation_id를 확인하세요.')
    require(type(doc['questions']) is list and bool(doc['questions']), '전체 문항 배열이 필요합니다.')
    _strings(doc['question_ids']); _strings(doc['conflict_ids'])
    require(type(doc['source_conflicts']) is list, '출처 충돌 배열이 필요합니다.')
    ids, conflicts, used = [], [], set()
    for conflict in doc['source_conflicts']:
        _object(conflict, ('conflict_id', 'description', 'source_refs', 'unresolved'))
        require(type(conflict['conflict_id']) is str and re.fullmatch(r'CF\d{3,}', conflict['conflict_id']), '충돌 ID를 확인하세요.')
        _text(conflict['description']); _refs(conflict['source_refs'])
        require(type(conflict['unresolved']) is bool, '충돌 unresolved는 boolean이어야 합니다.')
        conflicts.append(conflict['conflict_id'])
    require(doc['conflict_ids'] == conflicts and len(set(conflicts)) == len(conflicts), '출처 충돌 ID 목록이 다르거나 중복됐습니다.')
    for q in doc['questions']:
        _object(q, ('question_id', 'format', 'tier', 'importance', 'advanced', 'item_difficulty',
                    'retrieval_direction', 'question', 'source_refs', 'exam_rationale', 'evidence'),
                ('answers', 'options', 'mcq_mode', 'explanation', 'conflict_id'))
        _text(q['question_id']); ids.append(q['question_id'])
        require(type(q['format']) is str and q['format'] in FORMATS, '이번 출제에서 허용되지 않은 문항 형식입니다.')
        require(type(q['tier']) is str and q['tier'] in IMPORTANCE and type(q['importance']) is int
                and q['importance'] == IMPORTANCE[q['tier']], 'tier·importance가 일치하지 않습니다.')
        require(type(q['advanced']) is bool and type(q['item_difficulty']) is int and 1 <= q['item_difficulty'] <= 5,
                '심화·난이도를 확인하세요.')
        require(type(q['retrieval_direction']) is str and q['retrieval_direction'] in DIRECTIONS, '회상 방향이 올바르지 않습니다.')
        _text(q['question']); _text(q['exam_rationale']); _refs(q['source_refs']); _evidence(q['evidence'])
        if 'explanation' in q:
            _text(q['explanation'])
        if 'conflict_id' in q:
            require(type(q['conflict_id']) is str and q['conflict_id'] in conflicts, '정의되지 않은 충돌 ID입니다.')
            used.add(q['conflict_id'])
        fmt = q['format']
        if fmt == 'cloze':
            blanks = list(INLINE.finditer(q['question']))
            remainder = INLINE.sub('', q['question'])
            require('answers' not in q and bool(blanks) and all(m[1].strip() for m in blanks)
                    and '{' not in remainder and '}' not in remainder, 'cloze 빈칸·중괄호·별도 정답을 확인하세요.')
        else:
            answers = q.get('answers')
            _strings(answers); require(bool(answers), '정답 배열이 비었습니다.')
            require(fmt != 'basic' or len(answers) == 1, 'basic은 정답 단위 하나가 필요합니다.')
            if fmt == 'ox':
                require(answers in (['O'], ['X']) and bool(q.get('explanation')), 'OX 정답·필수 해설을 확인하세요.')
        if fmt in ('mcq', 'multi_select'):
            require(q.get('mcq_mode') in ('recall_first', 'comparison'), '객관식 mcq_mode가 필요합니다.')
            options = q.get('options')
            require(type(options) is list and len(options) >= 2, '객관식 보기가 필요합니다.')
            option_ids = []
            for option in options:
                _object(option, ('id', 'text')); _text(option['text'])
                require(type(option['id']) is str and re.fullmatch(r'[A-Z]+', option['id']), '보기 ID를 확인하세요.')
                option_ids.append(option['id'])
            require(len(set(option_ids)) == len(option_ids) and len(set(answers)) == len(answers)
                    and set(answers) <= set(option_ids) and (fmt != 'mcq' or len(answers) == 1), '정답과 실제 보기 ID가 일치하지 않습니다.')
        else:
            require('options' not in q and 'mcq_mode' not in q, '해당하지 않는 객관식 필드가 있습니다.')
    require(type(doc['question_count']) is int and doc['question_count'] == len(ids)
            and doc['question_ids'] == ids and ids == [f'Q{i:03}' for i in range(1, len(ids) + 1)],
            '전체 문항 수·ID 순서·누락·중복을 확인하세요.')
    require(used == set(conflicts), '문항에서 사용하지 않은 출처 충돌이 있습니다.')
    return doc


def loads(raw):
    require(type(raw) is str and 200 <= len(raw) <= MAX_CHARS, 'JSON 파일의 길이가 올바르지 않습니다.')
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'JSON 객체에 중복 키가 있습니다: ' + key)
            result[key] = value
        return result
    def constant(value):
        raise ValueError('JSON에 비유한 숫자를 사용할 수 없습니다: ' + value)
    try:
        value = json.loads(raw.removeprefix('\ufeff'), object_pairs_hook=pairs, parse_constant=constant)
        return validate_document(value)
    except (TypeError, RecursionError) as error:
        raise ValueError('JSON 파일의 구조가 올바르지 않습니다.') from error


def validate(raw, filename, subject, run_id, metadata=None):
    require(type(filename) is str and filename.endswith('.json') and run_id in filename
            and not re.search(r'[\\/\x00-\x1f]', filename), '선택한 강의 ID가 포함된 .json 파일을 사용하세요.')
    doc = loads(raw)
    require(doc['subject'] == subject and doc['run_id'] == run_id, '파일의 강의 ID·과목이 선택한 강의와 다릅니다.')
    data = raw.encode('utf-8')
    require(len(data) <= MAX_BYTES, '문제은행 파일이 너무 큽니다.')
    info = {'filename': filename, 'sha256': hashlib.sha256(data).hexdigest(), 'byteLength': len(data),
            'subject': subject, 'runId': run_id, 'promptVersion': doc['prompt_version'],
            'questionCount': doc['question_count'], 'questionIds': doc['question_ids'],
            'conflictIds': doc['conflict_ids'], 'validated': True}
    if metadata is not None:
        require(metadata.get('sha256') == info['sha256'] and metadata.get('byteLength') == len(data),
                '파일의 SHA-256·바이트 수가 실제 내용과 다릅니다.')
    return info


def to_bank(raw, title):
    doc = loads(raw)
    bank = {'build_meta': {'schema_version': SCHEMA_VERSION, 'lecture_title': title},
            'source_summary': [], 'source_conflicts': copy.deepcopy(doc['source_conflicts']),
            'concepts': [], 'retrieval_plan': [], 'questions': [],
            'audit_summary': {'summary': '저장된 JSON의 결정적 변환. 내용 검수는 별도 수행.', 'rejected_candidate_count': 0, 'changes': []},
            'warnings': []}
    evidence = {}
    from .slide_focus import authored_hash
    for item in doc['questions']:
        q = {key: '' if schema['type'] == 'string' else [] for key, schema in QUESTION['properties'].items()
             if key in QUESTION['required']}
        q.update({key: copy.deepcopy(value) for key, value in item.items() if key not in ('answers', 'evidence')})
        q.update(tier='Essential' if item['tier'] == 'Must-Know' else item['tier'],
                 mcq_mode=item.get('mcq_mode', 'none'), answer_units=item.get('answers', []).copy())
        if item['format'] == 'cloze':
            q = normalize_cloze(q)
        elif item['format'] in ('mcq', 'multi_select'):
            options = {option['id']: option['text'] for option in item['options']}
            q['correct_option_ids'] = item['answers'].copy()
            q['answer_units'] = [options[key] for key in item['answers']]
            q['answer'] = '\n'.join(f'{key}. {options[key]}' for key in item['answers'])
        else:
            q['answer'] = '\n'.join(item['answers'])
        bank['questions'].append(q)
        evidence[q['question_id']] = {'authoredHash': authored_hash(q), 'evidence': copy.deepcopy(item['evidence'])}
    return bank, evidence


def preserve_authored(bank, raw, title):
    """Keep model-authored learning links, but restore deterministic source content."""
    original, _ = to_bank(raw, title)
    require([q['question_id'] for q in bank['questions']] == [q['question_id'] for q in original['questions']],
            '웹 JSON 원문의 문항 ID·순서를 보존해야 합니다.')
    result = copy.deepcopy(bank)
    questions = []
    for authored, linked in zip(original['questions'], bank['questions']):
        questions.append({**authored, **{key: copy.deepcopy(linked[key]) for key in
            ('concept_id', 'prerequisites', 'learning_page', 'stimuli') if key in linked}})
    result['questions'] = questions
    result['source_conflicts'] = original['source_conflicts']
    return result

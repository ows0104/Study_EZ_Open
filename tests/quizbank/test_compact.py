import copy
import hashlib
import json

import pytest

from quizbank import compact, file_organize, generate, organize
from quizbank.schema import BANK, QUESTION
from quizbank.session import SessionError
from quizbank.validate import validate_bank


RAW = '''### Q001 | basic | Core | 5 | 2 | direct
문제: 첫 기호는?
정답: ["α"]
출처: S1 p.1
출제근거: 직접 회상

### Q002 | cloze | Core | 5 | 2 | mechanism
문제: 앞은 {{c1}}, 중간은 {{c1}}, 끝은 {{c1}}이다.
정답: ["α", "β", "α"]
출처: S1 p.1
출제근거: 빈칸별 회상

### Q003 | list | Advanced | 4 | 2 | reverse
문제: 두 묶음의 이름은?
정답: ["a, b; c", "d"]
출처: S1 p.1
출제근거: 목록 회상

### Q004 | ox | Core | 4 | 2 | trap
문제: 첫 기호는 β이다.
정답: ["X"]
출처: S1 p.1
출제근거: 오개념 판별

### Q005 | mcq | Core | 4 | 2 | discrimination | comparison
문제: 첫 기호를 고르시오.
보기:
A. α
B. β
C. γ
D. δ
E. ε
정답: ["A"]
출처: S1 p.1; S2 2023 Q11; EXT 확인 근거
출제근거: 기호 구별
충돌: CF001

### Q006 | multi_select | Optional | 3 | 3 | discrimination | comparison
문제: 해당하는 기호를 모두 고르시오.
보기:
A. α
B. β
C. γ
D. δ
E. ε
정답: ["A", "C"]
출처: S1 p.1
출제근거: 복수 항목 구별

### Q007 | matching | Core | 4 | 2 | discrimination
문제: 숫자와 기호를 연결하시오.
왼쪽:
1. 하나
2. 둘
3. 셋
오른쪽:
A. α
B. β
정답: ["1-B", "2-A", "3-B"]
출처: S1 p.1
출제근거: 짝 연결

### Q008 | sequence | Core | 4 | 2 | sequence
문제: 기호 순서를 정렬하시오.
항목:
A. α
B. β
C. γ
정답: ["C", "A", "B"]
출처: S1 p.1
출제근거: 순서 회상

### CF001
설명: S1과 S2의 기호 표기가 달라 EXT로 확인했다.
출처: S1 p.1; S2 2023 Q11; EXT 확인 근거
미해결: false
STUDYEZ_BANK_COMPLETE
'''


def draft():
    """The organizer's non-medical fixture with deliberately omitted derived answers."""
    questions = []
    for i, block in enumerate(compact.read_blocks(RAW)):
        q = {key: [] if spec['type'] == 'array' else 0 if spec['type'] == 'integer' else ''
             for key, spec in QUESTION['properties'].items()}
        q.update({k: v for k, v in block.items() if k != 'units'})
        q.update(question=["첫 기호는?", "앞은 {{c1}}, 중간은 {{c1}}, 끝은 {{c1}}이다.",
                           "두 묶음의 이름은?", "첫 기호는 β이다.", "첫 기호를 고르시오.",
                           "해당하는 기호를 모두 고르시오.", "숫자와 기호를 연결하시오.",
                           "기호 순서를 정렬하시오."][i],
                 source_refs=[{'source_id': 'S1', 'locator': 'p.1'}], exam_rationale='기호 회상')
        if q['format'] in ('mcq', 'multi_select'):
            q['options'] = [{'id': chr(65 + j), 'text': s} for j, s in enumerate(['α', 'β', 'γ', 'δ', 'ε'])]
        if q['format'] == 'matching':
            q['matching_left'], q['matching_right'] = ['1. 하나', '2. 둘', '3. 셋'], ['A. α', 'B. β']
        if q['format'] == 'sequence':
            q['sequence_items'] = ['A. α', 'B. β', 'C. γ']
        questions.append(q)
    questions[4]['conflict_id'] = 'CF001'
    questions[4]['source_refs'] += [{'source_id': 'S2', 'locator': '2023 Q11'}, {'source_id': 'EXT', 'locator': '확인 근거'}]
    return {'build_meta': {'schema_version': '3.1', 'lecture_title': '기호'}, 'source_summary': [],
            'source_conflicts': [{'conflict_id': 'CF001', 'description': 'S1과 S2의 표기 충돌 확인',
                                 'source_refs': copy.deepcopy(questions[4]['source_refs']), 'unresolved': False}],
            'concepts': [], 'retrieval_plan': [], 'questions': questions,
            'audit_summary': {'summary': '', 'rejected_candidate_count': 0, 'changes': []}, 'warnings': []}


@pytest.mark.parametrize('file_mode', [False, True])
def test_all_formats_reconstruct_and_pass_app_draft_validation(tmp_path, monkeypatch, file_mode):
    before = draft()
    def provider(prompt, **kwargs):
        assert 'v1.49의 간결 블록' in prompt
        target = kwargs['cwd'] / 'bank.json'
        target.write_text(json.dumps(before, ensure_ascii=False), encoding='utf-8')
        return {'text': '{"written":true}', 'duration_ms': 1, 'cost_usd': None,
                'usage': {'input_tokens': 1, 'cache_read_input_tokens': 0, 'output_tokens': 1}, 'models': {}, 'session_id': 'test'}
    monkeypatch.setattr(file_organize.codex, 'run', provider)
    monkeypatch.setattr(organize.session, 'run_structured', lambda *a, **kw: (copy.deepcopy(before), {}))
    bank, _ = organize.organize(RAW, {'title': '기호', 'sources': [], 'prompt_version': '1.49'},
                               out=tmp_path if file_mode else None)
    assert [q['question_id'] for q in bank['questions']] == [q['question_id'] for q in before['questions']]
    assert bank['source_conflicts'] == before['source_conflicts']
    assert [q['source_refs'] for q in bank['questions']] == [q['source_refs'] for q in before['questions']]
    q = bank['questions']
    assert q[0]['answer'] == 'α' and q[0]['answer_units'] == ['α']
    assert q[1]['answer'] == '앞은 α, 중간은 β, 끝은 α이다.' and q[1]['answer_units'] == ['α', 'β', 'α']
    assert q[2]['answer_units'] == ['a, b; c', 'd']
    assert q[3]['answer'] == 'X' and q[3]['answer_units'] == ['X']
    assert q[4]['correct_option_ids'] == ['A'] and q[4]['answer_units'] == ['α']
    assert q[5]['correct_option_ids'] == ['A', 'C'] and q[5]['answer_units'] == ['α', 'γ']
    assert q[6]['answer_pairs'] == [{'left': '하나', 'right': 'β'}, {'left': '둘', 'right': 'α'}, {'left': '셋', 'right': 'β'}]
    assert q[7]['correct_order'] == ['γ', 'α', 'β']
    check = validate_bank(bank, ['S1', 'S2'], learning_structure=False)
    assert check['pass'], check['errors']


@pytest.mark.parametrize('change', ['missing', 'extra', 'duplicate'])
def test_compact_structured_path_cannot_lose_add_or_duplicate_questions(monkeypatch, change):
    bank = draft()
    if change == 'missing':
        bank['questions'].pop()
    else:
        q = copy.deepcopy(bank['questions'][0])
        if change == 'extra':
            q['question_id'] = 'Q_EXTRA'
        bank['questions'].append(q)
    monkeypatch.setattr(organize.session, 'run_structured', lambda *a, **kw: (bank, {}))
    with pytest.raises(SessionError, match='문항 ID'):
        organize.organize(RAW, {'title': '기호', 'sources': [], 'prompt_version': '1.49'})


@pytest.mark.parametrize('replace', [('### Q002', '### Q001'), ('| cloze |', '| unknown |'),
                                   ('["α", "β", "α"]', '["α",]'), ('["α", "β", "α"]', '[]')])
def test_invalid_block_contract_fails_before_llm(replace):
    with pytest.raises(SessionError):
        compact.read_blocks(RAW.replace(*replace))


@pytest.mark.parametrize('index,units', [(1, ['α']), (4, ['Z']), (6, ['1-B', '2-A']), (7, ['A', 'A', 'B'])])
def test_answer_position_and_ids_are_checked(index, units):
    blocks = compact.read_blocks(RAW)
    blocks[index]['units'] = units
    with pytest.raises(SessionError):
        compact.restore(draft(), blocks)


def test_question_ids_keep_old_tables_and_ignore_conflicts_and_references():
    assert file_organize.question_ids(RAW) == {f'Q{i:03}' for i in range(1, 9)}
    assert compact.read_blocks('### Q001\nquestion: old block\nanswer: old answer') == []
    with pytest.raises(SessionError):
        compact.read_blocks(RAW + '\n### Q009\n문제: 미완성\n')


def test_output_group_headings_do_not_split_create_or_drop_questions():
    grouped = '## 묶음 1: Q001–Q004\n\n' + RAW.replace(
        '### Q005 | mcq', '## 묶음 2: Q005–Q008\n\n### Q005 | mcq')
    assert compact.read_blocks(grouped) == compact.read_blocks(RAW)
    assert file_organize.question_ids(grouped) == file_organize.question_ids(RAW)
    bank = draft()
    compact.restore(bank, compact.read_blocks(grouped))
    check = validate_bank(bank, ['S1', 'S2'], learning_structure=False)
    assert check['pass'], check['errors']


def test_browser_copy_can_join_labeled_fields_into_one_paragraph():
    joined = RAW.replace('\n정답:', ' 정답:').replace('\n출처:', ' 출처:').replace('\n출제근거:', ' 출제근거:')
    assert compact.read_blocks(joined) == compact.read_blocks(RAW)


def test_answer_decoder_preserves_quoted_field_names_inside_answers():
    units = ['문구 정답: ["가짜"] 자체', '따옴표 " 와 역슬래시 \\']
    raw = RAW.replace('["α", "β", "α"]', json.dumps(units + ['α'], ensure_ascii=False))
    assert compact.read_blocks(raw)[1]['units'] == units + ['α']


def test_shared_quality_guidance_matches_the_reviewed_153_rules():
    # v1.53 clarifies the user's language and explanation-only preferences.
    quality = generate.item_quality_guidance().removeprefix('문항 품질 원칙\n\n')
    assert hashlib.sha256(quality.encode()).hexdigest() == 'd526a69dc9b4be733398489b2a21298edd47bb69e814ad6dc8d86ad626e309a6'


def test_optional_explanation_is_restored_without_becoming_answers(monkeypatch):
    explanation = 'apical/luminal membrane의 표기를 유지한다. 문구 해설: "가짜"도 문자열이다.'
    extra = ' 해설: ' + json.dumps(explanation, ensure_ascii=False)
    raw = RAW.replace('정답: ["α"]', '정답: ["α"]' + extra, 1)
    bank = draft()
    bank['questions'][0].update(explanation='정리기가 바꾼 값')
    monkeypatch.setattr(organize.session, 'run_structured', lambda *a, **kw: (bank, {}))
    result, _ = organize.organize(raw, {'title': '기호', 'sources': [], 'prompt_version': '1.53'})
    q = result['questions'][0]
    assert q['explanation'] == explanation and 'hint' not in q
    assert q['answer_units'] == ['α'] and q['question'] == '첫 기호는?'
    assert all('hint' not in q and not q['explanation'] for q in result['questions'][1:])


@pytest.mark.parametrize('extra', ['해설: []', '해설: null', '해설: "하나" 해설: "둘"', '해설: 이스케이프되지 않은 글'])
def test_invalid_optional_fields_fail_before_organizing(extra):
    with pytest.raises(SessionError):
        compact.read_blocks(RAW.replace('정답: ["α"]', '정답: ["α"] ' + extra, 1))


def test_legacy_banks_receive_empty_display_fields_without_mutation():
    from quizbank.schema import without_retired
    bank = draft()
    for q in bank['questions']:
        q.pop('explanation')
        q['hint'] = '이전 실험 힌트'
    before = copy.deepcopy(bank)
    normalized = without_retired(bank)
    assert bank == before
    assert all('hint' not in q and q['explanation'] == '' for q in normalized['questions'])


def test_previous_experiment_hint_is_consumed_without_becoming_question_data():
    raw = RAW.replace('정답: ["α"]', '정답: ["α"] 힌트: "이전 단서" 해설: "원문 해설"', 1)
    blocks = compact.read_blocks(raw)
    assert blocks[0]['units'] == ['α'] and blocks[0]['explanation'] == '원문 해설'
    assert all('hint' not in q for q in blocks)

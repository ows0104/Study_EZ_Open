"""Synthetic A/B/C/D relationships only; not lecture content or medical validation."""
import hashlib
from studyez_contracts.learning_links import question_hash
from studyez_contracts.roots import document_hash

POLICY = {'id': 'roots-test/1', 'intervals': [1, 3, 7, 14], 'day_hour': 9, 'deadline_offset': 2}


def document():
    ref = {'source_id': 'S1', 'locator': 'synthetic paragraph', 'pages': []}
    bank = {'lecture_id': 'test/demo', 'questions': [
        {'question_id': f'Q{i}', 'format': 'basic', 'question': f'Synthetic question {i}?',
         'answer': f'Secret answer {i}', 'explanation': f'Synthetic explanation {i}', 'options': [], 'answer_units': []}
        for i in range(1, 4)]}
    relations = [{'relation_id': f'R{i}', 'from_id': a, 'to_id': b, 'kind': 'association', 'condition': 'synthetic',
                  'evidence': [ref], 'review_status': 'reviewed' if i < 4 else 'unreviewed', 'reason': 'synthetic'}
                 for i, (a, b) in enumerate([('A', 'B'), ('B', 'A'), ('C', 'D'), ('D', 'A')], 1)]
    relations.append({'relation_id': 'P1', 'from_id': 'A', 'to_id': 'C', 'kind': 'prerequisite',
                      'condition': 'explicit synthetic prerequisite', 'evidence': [ref], 'review_status': 'reviewed', 'reason': 'synthetic'})
    targets = []
    for i, ids in [(1, [1, 2]), (2, [3]), (3, [4])]:
        importance = {a: {'status': 'insufficient', 'reason': 'unverified', 'evidence': []} for a in ['structural', 'exam', 'clinical']}
        if i == 1:
            importance['structural'] = {'status': 'supported', 'reason': 'synthetic root',
                'evidence': [{'kind': 'structural_rationale', 'reason': 'synthetic', 'refs': [ref]}]}
        if i == 2:
            importance['exam'] = {'status': 'supported', 'reason': 'synthetic exam',
                'evidence': [{'kind': 'observed_exam', 'reason': 'synthetic', 'refs': [ref]}]}
        targets.append({'target_id': f'T{i}', 'title': f'Synthetic target {i}', 'concept_ids': ['A', 'B'] if i == 1 else ['C' if i == 2 else 'D'],
            'relation_ids': [f'R{n}' for n in ids], 'role': 'root' if i == 1 else 'leaf', 'reason': 'synthetic',
            'evidence': [ref], 'importance': importance,
            'directions': [{'direction_id': f'D{n}', 'cue': f'Cue {n}', 'answer_scope': f'Secret direction {n}',
                            'requirement': 'required', 'relation_ids': [f'R{n}']} for n in ids]})
    review = {'schema_version': 'learning-links/1', 'lecture_id': 'test/demo', 'bank_sha256': document_hash(bank),
        'hash_policy': 'learning-links-question/1', 'scope': {'label': 'Synthetic root scope', 'included': ['A/B/C/D'],
            'excluded': [], 'reviewed': ['synthetic'], 'limitations': ['Not medical content'], 'outside_list_review': 'synthetic only'},
        'provenance': {'status': 'reviewed', 'method': 'synthetic fixture', 'reviewer': 'test', 'independent_points': 'confirmed', 'notes': 'synthetic'},
        'sources': [{'source_id': 'S1', 'label': 'synthetic', 'sha256': hashlib.sha256(b'synthetic').hexdigest(),
                     'kind': 'other', 'professor': None, 'year': None, 'page_count': None}],
        'concepts': [{'concept_id': c, 'label': c, 'parent_ids': [] if c == 'A' else ['A']} for c in 'ABCD'],
        'relations': relations, 'targets': targets,
        'points': [{'point_id': f'P{i}', 'text': 'Synthetic point', 'evidence': [ref], 'target_ids': [f'T{i}'],
                    'scope_status': 'included', 'reason': 'synthetic'} for i in [1, 2, 3]],
        'mappings': [{'question_id': f'Q{i}', 'question_sha256': question_hash(q, bank), 'target_id': 'T1' if i < 3 else 'T2',
                     'direction_id': f'D{i}', 'tested_relation_ids': [f'R{i}'], 'provided_relation_ids': [],
                     'explanation_relation_ids': [], 'reason': 'synthetic'} for i, q in enumerate(bank['questions'], 1)],
        'coverage': [{'point_id': f'P{i}', 'status': 'covered' if i < 3 else 'unknown',
                      'confirmed_direction_ids': ['D1', 'D2'] if i == 1 else ['D3'] if i == 2 else [],
                      'partial_direction_ids': [], 'missing_direction_ids': [], 'unknown_direction_ids': ['D4'] if i == 3 else [],
                      'reason': 'synthetic', 'exclusion_basis': None} for i in [1, 2, 3]]}
    return {'schema_version': 'roots/1', 'revision': 'v1', 'title': 'Synthetic root lecture', 'review': review,
            'bank_snapshot': bank, 'bank_source': 'standalone', 'bank_build_id': None, 'adopted_target_ids': ['T1', 'T2', 'T3'],
            'tasks': [{'task_id': f'task{i}', 'question_id': f'Q{i}', 'direction_id': f'D{i}'} for i in [1, 2, 3]],
            'exam_date': '2026-11-07', 'equivalences': [],
            'prerequisites': [{'before_target':'T1','after_target':'T2','relation_id':'P1'}]}

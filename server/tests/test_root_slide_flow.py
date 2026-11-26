"""오늘 학습 순서는 슬라이드 흐름이다(docs/changes/2026-11-26-slide-flow-order, 사용자 2026-11-26 「슬라이드 흐름으로」).

피부근염 261124_02의 모양: 6쪽 「IIM의 세 가지 범주」(근거는 구조뿐)가 중요한 목표 57개 뒤로 밀렸고, 오늘 목록에 없는
Optional 7쪽 문항의 전제 때문에 26쪽 「진단 후 평가할 동반질환」이 맨 앞에 왔다. 중요도는 오늘 범위를 고르는 데만 쓰고
순서는 쪽 순이다. 명시적 선행만 순서를 바꾼다."""
from collections import defaultdict

from app.root_learning.planning import REVIEW_REASON, PULLED_REASON, slide_flow, task_pages


def doc_of(rows):
    """rows: (task_id, question_id, direction_id, page or None) in document order."""
    return {'tasks': [{'task_id': t, 'question_id': q, 'direction_id': d} for t, q, d, _ in rows],
            'bank_snapshot': {'questions': [{'question_id': q, **({'learning_page': p} if p is not None else {})}
                                            for _, q, _, p in rows]}}


def pick(doc, reasons=None):
    reasons = reasons or {}
    return [{**t, 'reason': reasons.get(t['task_id'], '새 목표')} for t in doc['tasks']]


def owner_by(targets):
    return lambda task: targets[task['direction_id']]


def ids(result):
    return [t['task_id'] for t in result]


NONE = defaultdict(set)

# ---------------------------------------------------------------- pages
d = doc_of([('a', 'A', 'D1', 20), ('b', 'B', 'D2', 6), ('m', 'm', 'D2', None), ('c', 'C', 'D3', 9)])
assert task_pages(d) == {'a': 20, 'b': 6, 'm': 6, 'c': 9}            # 쪽 없는 과제는 바로 앞 과제의 쪽
assert task_pages(doc_of([('x', 'X', 'D1', None)])) == {'x': 0}

# ---------------------------------------------------------------- slide order, reviews after new learning
d = doc_of([('t20', 'Q20', 'D1', 20), ('t6', 'Q6', 'D2', 6), ('t9', 'Q9', 'D3', 9), ('r7', 'R7', 'D4', 7)])
owner = owner_by({'D1': 'T1', 'D2': 'T2', 'D3': 'T3', 'D4': 'T4'})
got = slide_flow(d, pick(d, {'r7': REVIEW_REASON}), NONE, set(), {}, owner)
assert ids(got) == ['t6', 't9', 't20', 'r7']                          # 문서 순서도 중요도도 아닌 쪽 순, 복습은 뒤
# 같은 쪽은 문서 순서
d2 = doc_of([('x', 'X', 'D1', 8), ('y', 'Y', 'D2', 8)])
assert ids(slide_flow(d2, pick(d2), NONE, set(), {}, owner_by({'D1': 'T1', 'D2': 'T2'}))) == ['x', 'y']

# ---------------------------------------------------------------- existence question by question (links)
d = doc_of([('def', 'DEF', 'D1', 6), ('epi', 'EPI', 'D2', 7), ('ild', 'ILD', 'D3', 13), ('lung', 'LUNG', 'D3', 14),
            ('comorb', 'COMORB', 'D4', 26)])
owner = owner_by({'D1': 'T1', 'D2': 'T2', 'D3': 'T3', 'D4': 'TQ'})
edges = defaultdict(set, {'T2': {'TQ'}, 'T3': {'TQ'}})
existence = {('TQ', 'T2'), ('TQ', 'T3')}
links = {'EPI_OPTIONAL': ['COMORB'], 'ILD': ['COMORB']}               # 7쪽 Optional 문항은 오늘 목록에 없다
got = slide_flow(d, pick(d), edges, existence, links, owner)
assert ids(got) == ['def', 'epi', 'comorb', 'ild', 'lung']            # 26쪽 존재 문항은 그것을 전제하는 13쪽 바로 앞
# links가 없는 판(예전 반입)은 목표 단위로 지금처럼
got = slide_flow(d, pick(d), edges, existence, None, owner)
assert ids(got) == ['def', 'comorb', 'epi', 'ild', 'lung']
# 앞당겨 끌어온 선행 문항도 그것을 필요로 하는 문항 자리로
got = slide_flow(d, pick(d, {'comorb': PULLED_REASON}), edges, existence, links, owner)
assert ids(got) == ['def', 'epi', 'comorb', 'ild', 'lung']

# ---------------------------------------------------------------- other target edges (reverse goal after forward goal)
d = doc_of([('rev', 'REV', 'D2', 5), ('fwd', 'FWD', 'D1', 9), ('far', 'FAR', 'D3', 7)])
owner = owner_by({'D1': 'T1', 'D2': 'TQ_REV', 'D3': 'T3'})
got = slide_flow(d, pick(d), defaultdict(set, {'TQ_REV': {'T1'}}), set(), {}, owner)
assert ids(got) == ['fwd', 'rev', 'far']                              # 정방향이 역방향 자리(5쪽)로 당겨진다

# ---------------------------------------------------------------- one direction on one page, personal question
d = doc_of([('a1', 'A1', 'DA', 8), ('a2', 'A2', 'DA', 8), ('b1', 'B1', 'DB', 8), ('c1', 'C1', 'DC', 9)])
owner = owner_by({'DA': 'T1', 'DB': 'T2', 'DC': 'T3'})
assert ids(slide_flow(d, pick(d), NONE, set(), {}, owner)) == ['a1', 'b1', 'a2', 'c1']   # 같은 쪽 안에서만 떼어 놓는다
d = doc_of([('a1', 'A1', 'DA', 8), ('mine-1', 'mine-1', 'DA', None), ('b1', 'B1', 'DB', 8)])
assert ids(slide_flow(d, pick(d), NONE, set(), {}, owner)) == ['a1', 'mine-1', 'b1']    # 내 문제는 기준 과제 바로 뒤
d = doc_of([('a1', 'A1', 'DA', 8), ('a2', 'A2', 'DA', 8), ('c1', 'C1', 'DC', 9)])
assert ids(slide_flow(d, pick(d), NONE, set(), {}, owner)) == ['a1', 'a2', 'c1']        # 다른 쪽 과제를 끌어오지 않는다

# ---------------------------------------------------------------- a cycle never fails the plan
d = doc_of([('x', 'X', 'D1', 3), ('y', 'Y', 'D2', 4)])
got = slide_flow(d, pick(d), defaultdict(set, {'T1': {'T2'}, 'T2': {'T1'}}), set(), {}, owner_by({'D1': 'T1', 'D2': 'T2'}))
assert sorted(ids(got)) == ['x', 'y']
assert slide_flow(d, [], NONE, set(), {}, owner_by({'D1': 'T1', 'D2': 'T2'})) == []

print('PASS: slide order by page, reviews after new learning, existence by question, target edges, '
      'same-page direction spacing, personal question beside its anchor, cycle-safe')

"""presuppose/1 (docs/changes/2026-11-15-tree-edge-goals): what a question's stem gives as already known.

A question that hands the learner 「A has B」 and asks about B's detail C does not show that A→B is known
(사이트 intent I3). The `v4-presuppose` stage lists, per question, the upper links its visible stem presupposes
and which questions recall each link as their answer. A link no question recalls becomes an exam point of origin
`presupposition`, normalized into an existence goal by `v4-supplement-normalize-presuppose`, which may add the
content relation that goal recalls (a parent→child membership is not a map relation, so the supplement could not
bind it otherwise). At assembly every presupposition whose existence goal and presupposing question both became
tasks gives a target prerequisite (existence goal → the question's goal); its relation is this stage's judgment of
study order, not a source fact. Pure functions only: no model, DB or server.
"""
import copy
import re

from studyez_contracts.learning_links.schema import obj, arr, TEXT
from studyez_contracts.learning_links.validate import require, validate_shape
from .validate import document_hash
from . import generation_v2 as v2
from . import generation_v3 as v3

PRESUPPOSE = 'presuppose/1'
CHUNK = 40            # questions judged per stage call; every question of the bank is the reference
ORIGIN = 'presupposition'

_POINT = copy.deepcopy(v3.POINT)
_POINT['properties'].pop('importance_basis')
_POINT['required'].remove('importance_basis')
LINK = obj(a=TEXT, b=TEXT, link=TEXT, recalled_by=arr(TEXT), point={'anyOf': [_POINT, {'type': 'null'}]}, reason=TEXT)
OUTPUT = obj(rows=arr(obj(question_id=TEXT, presupposes=arr(LINK))))
# The model-facing schema has anyOf (point or null); this pure module checks `point` by hand, as v3 does its supplement.
_CHECKED = obj(rows=arr(obj(question_id=TEXT, presupposes=arr(obj(a=TEXT, b=TEXT, link=TEXT, recalled_by=arr(TEXT), reason=TEXT)))))

_RELATION = copy.deepcopy(v2.BRIEF['properties']['relations']['items'])
NORMALIZE_OUTPUT = copy.deepcopy(v3.SUPPLEMENT_NORMALIZE_OUTPUT)
NORMALIZE_OUTPUT['properties']['relations'] = arr(_RELATION)
NORMALIZE_OUTPUT['required'].append('relations')


# ---------------------------------------------------------------- judgment
def _reference(q):
    front = v3._front(q)
    return {k: front[k] for k in ('question_id', 'question', 'answer', 'answer_units') if k in front}


def stage_input(bank, question_ids, page_counts):
    """The questions to judge (what the learner sees, the scored answer, cited sources) and every question of the bank
    as the reference for `recalled_by`."""
    wanted = set(question_ids)
    judged = [q for q in bank['questions'] if q['question_id'] in wanted]
    require(len(judged) == len(wanted), 'presuppose: unknown question')
    return {'questions': [{**v3._front(q), 'source_refs': copy.deepcopy(q.get('source_refs', []))} for q in judged],
            'all_questions': [_reference(q) for q in bank['questions']],
            'page_counts': dict(page_counts),
            'pages': v3.cited_pages([r for q in judged for r in q.get('source_refs', [])])}


def check(value, ctx):
    """One presuppose output: every judged question exactly once; a link either names the questions that recall it as
    their answer or, when none does, the exam point an existence goal is made from."""
    require(type(value) is dict and type(value.get('rows')) is list, 'presuppose output: rows required')
    for row in value['rows']:
        require(type(row) is dict and type(row.get('presupposes')) is list, 'presuppose output: presupposes required')
        for link in row['presupposes']:
            require(type(link) is dict and 'point' in link and (link['point'] is None or type(link['point']) is dict),
                    'presuppose output: point is an object or null')
    validate_shape({'rows': [{**r, 'presupposes': [{k: v for k, v in l.items() if k != 'point'} for l in r['presupposes']]}
                             for r in value['rows']]}, _CHECKED, 'presuppose output')
    judged = [q['question_id'] for q in ctx['questions']]
    rows = [r['question_id'] for r in value['rows']]
    require(sorted(rows) == sorted(judged) and len(rows) == len(set(rows)), 'presuppose: rows must name every judged question once')
    known = {q['question_id'] for q in ctx['all_questions']}
    for row in value['rows']:
        for link in row['presupposes']:
            by = link['recalled_by']
            require(len(by) == len(set(by)) and set(by) <= known, f"presuppose {row['question_id']}: recalled_by names unknown questions")
            require(row['question_id'] not in by, f"presuppose {row['question_id']}: a question cannot recall what its own stem gives")
            if by:
                require(link['point'] is None, f"presuppose {row['question_id']}: a recalled link carries no point")
            else:
                require(link['point'] is not None, f"presuppose {row['question_id']}: a link nobody recalls needs its point")
                v3._check_point({**link['point'], 'importance_basis': []})
                for ref in link['point']['source_refs']:
                    # A source without pages (text) has page count None: it is cited by locator only.
                    require(ref['source_id'] in ctx['page_counts'], f"presuppose {row['question_id']}: point pages outside the sources")
                    count = ctx['page_counts'][ref['source_id']]
                    require(all(count is not None and 1 <= p <= count for p in ref['pages']),
                            f"presuppose {row['question_id']}: point pages outside the sources")
    return value


def _norm(text):
    return re.sub(r'\s+', ' ', text).strip().casefold()


def _key(link):
    return _norm(link['a']), _norm(link['b'])


def records(outputs, bank, points_doc, reserved=()):
    """Every judged link in question order, and the new exam points of the links nobody recalls. One point per (A, B),
    however many questions presuppose it, and one per point text: links the judgment gave the same point (two members
    of one category, e.g. two accessory factors of one organism) are one existence goal, not two identical ones
    (2026-11-15 콜레라 실측: 44 points, 7 repeated another's text). Questions that left the bank since the judgment
    are dropped, as are their names in `recalled_by`.

    Returns (points_doc, records, new_points)."""
    present = [q['question_id'] for q in bank['questions']]
    rows = {r['question_id']: r for value in outputs for r in value['rows']}
    numbers = [int(m.group(1)) for pid in [*(p['point_id'] for p in points_doc['points']), *reserved]
               for m in [re.fullmatch(r'P(\d+)', pid)] if m]
    nxt = max(numbers, default=0) + 1
    value = copy.deepcopy(points_doc)
    made, by_text, out, new = {}, {}, [], []
    for qid in present:
        for link in rows.get(qid, {'presupposes': []})['presupposes']:
            by = [x for x in link['recalled_by'] if x in set(present)]
            pid = None
            if not link['recalled_by']:
                key, text = _key(link), _norm(link['point']['point'])
                pid = made.get(key) or by_text.get(text)
                if pid is None:
                    pid = f'P{nxt:03d}'
                    nxt += 1
                    point = {'point_id': pid, **copy.deepcopy(link['point']), 'origin': ORIGIN, 'origin_question_id': qid}
                    value['points'].append(point)
                    new.append(point)
                made.setdefault(key, pid)
                by_text.setdefault(text, pid)
            out.append({'question_id': qid, 'a': link['a'], 'b': link['b'], 'link': link['link'],
                        'recalled_by': by, 'point_id': pid})
    return value, out, new


# ---------------------------------------------------------------- existence goals
# 원본이 한 연결의 원소를 이름 붙은 묶음(표의 열·칸, 약물 계열)으로 나눴으면 정규화가 묶음마다 존재 목표를 만든다
# (docs/changes/2026-11-25-long-list-answers). 그 몫으로 포인트마다 목표 ID를 여유 있게 준다. 안 쓴 번호는 다음 보충이 잇는다.
GOALS_PER_POINT = 3


def new_goal_ids(brief, points):
    return v3.supplement_ids(brief, GOALS_PER_POINT * len(points))


def relation_ids(brief, count, prefix='RQP'):
    """The IDs new content relations may take. `prefix` keeps each policy's relations apart (discriminate/1 uses
    RQD), so one does not reuse a number the other already gave."""
    used = [int(m.group(1)) for r in brief['relations']
            for m in [re.fullmatch(re.escape(prefix) + r'(\d+)', r['relation_id'])] if m]
    start = max(used, default=0) + 1
    return [f'{prefix}{n:03d}' for n in range(start, start + count)]


def normalize_input(brief, new_points, allowed):
    """v3 supplement-normalize input with the IDs the new content relations may take (at most one per point)."""
    return {**v3.supplement_normalize_input(brief, new_points, allowed),
            'allowed_relation_ids': relation_ids(brief, len(new_points))}


def _relations(value, ctx):
    concepts = {c['concept_id'] for c in ctx['concepts']}
    allowed = set(ctx['allowed_relation_ids'])
    ids = [r['relation_id'] for r in value['relations']]
    require(len(ids) == len(set(ids)) and set(ids) <= allowed, 'presuppose normalize: relation IDs outside the allowed range')
    for r in value['relations']:
        require(r['from_id'] in concepts and r['to_id'] in concepts and r['from_id'] != r['to_id'],
                f"presuppose normalize: {r['relation_id']} joins existing concepts")
        require(r['kind'] == 'association' and r['review_status'] == 'unreviewed',
                f"presuppose normalize: {r['relation_id']} is an unreviewed content relation (association)")


def extend(brief, value, new_point_ids):
    """Add the new content relations, then the new targets and points (v3.extend_brief: nothing existing changes)."""
    with_relations = copy.deepcopy(brief)
    with_relations['relations'] += copy.deepcopy(value['relations'])
    addition = v3.supplement_addition(with_relations, {'targets': value['targets'], 'points': value['points']}, True)
    return v3.extend_brief(with_relations, addition, new_point_ids)


def check_normalize(value, ctx, state=None):
    validate_shape(value, NORMALIZE_OUTPUT, 'presuppose normalize output')
    _relations(value, ctx)
    known = {**ctx, 'relations': [*ctx['relations'], *({'relation_id': r['relation_id']} for r in value['relations'])]}
    v3.check_supplement_normalize({'targets': value['targets'], 'points': value['points']}, known)
    if state is not None:
        extend(state['brief'], value, [p['point_id'] for p in ctx['points']])
    return value


# ---------------------------------------------------------------- study order at assembly
def _reaches(graph, start, goal):
    seen, todo = set(), [start]
    while todo:
        node = todo.pop()
        if node == goal:
            return True
        if node not in seen:
            seen.add(node)
            todo.extend(graph.get(node, ()))
    return False


def closes_task_cycle(placed, question_deps, target_graph, before, after):
    """True when the target edge before → after would make a task wait for itself.

    A target edge makes every task of `after` wait for every task of `before`. Questions also wait for each other
    (`questions[].prerequisites`), and the study plan combines both (generation_v2.order_plan). So the edge closes a
    cycle when a task of `before` already waits — through question prerequisites and the target edges so far — for a
    task of `after`. The target graph alone does not show it: 2026-11-17 job 670 / 261112_03, published Q071 (T064)
    has the question prerequisite Q068 (T062), and the existence edge T064 → T062 stopped the lecture with
    「prerequisites: combined target/question cycle」.

    `placed`: question → its target; `question_deps`: question → its prerequisite questions. A document that is valid
    without this guard has no such cycle, so the guard leaves every edge of it in place."""
    if not question_deps:
        return False
    by_target, incoming = {}, {}
    for q, t in placed.items():
        by_target.setdefault(t, []).append(q)
    for b, afters in target_graph.items():
        for a in afters:
            incoming.setdefault(a, set()).add(b)
    goal = set(by_target.get(after, []))
    seen, opened, stack = set(), set(), list(by_target.get(before, []))
    while stack:
        q = stack.pop()
        if q in goal:
            return True
        if q in seen:
            continue
        seen.add(q)
        stack.extend(d for d in question_deps.get(q, []) if d in placed)
        if placed[q] not in opened:
            opened.add(placed[q])
            for b in incoming.get(placed[q], ()):
                stack.extend(by_target.get(b, []))
    return False


def existence_relation_id(before, after):
    return 'PRE-' + document_hash([before, after])[:12]


def is_existence_edge(edge):
    """A target prerequisite order_edges made: an existence goal before the goal that presupposes it. The study plan
    brings these forward even outside today's chosen tiers; other target prerequisites (map relations) only within
    them (docs/changes/2026-11-16-prereq-question-only). A pair that already had a map edge keeps that edge."""
    return re.fullmatch(r'PRE-[0-9a-f]{12}', edge.get('relation_id') or '') is not None


def order_edges(brief, tasks, presuppositions, relations, edges, question_deps=None):
    """Target prerequisites from the presupposition records: the existence goal (the goal of a question that recalls
    the link, or the goal made from its point) before the goal of the question that presupposes it.

    Only goals with tasks take part; an edge that would close a cycle (targets, the concepts of prerequisite
    relations, or — with `question_deps`, question → its prerequisite questions — the tasks themselves) is left out,
    so is one whose relation would join a concept to itself (both goals name one concept).
    Returns (relations, edges) to add."""
    targets = {t['target_id']: t for t in brief['targets']}
    owners = {d['direction_id']: t['target_id'] for t in brief['targets'] for d in t['directions']}
    placed = {t['question_id']: owners[t['direction_id']] for t in tasks}
    from_points = {p['point_id']: list(p['target_ids']) for p in brief['points']}
    target_graph, concept_graph = {}, {}
    for e in edges:
        target_graph.setdefault(e['before_target'], set()).add(e['after_target'])
    for r in relations:
        if r['kind'] == 'prerequisite':
            concept_graph.setdefault(r['from_id'], set()).add(r['to_id'])
    pairs = {(e['before_target'], e['after_target']) for e in edges}
    new_relations, new_edges = [], []
    for rec in presuppositions:
        after = placed.get(rec['question_id'])
        if after is None:
            continue
        befores = {placed[q] for q in rec['recalled_by'] if q in placed}
        if rec['point_id']:
            befores |= {t for t in from_points.get(rec['point_id'], []) if t in set(placed.values())}
        for before in sorted(befores - {after}):
            if (before, after) in pairs or _reaches(target_graph, after, before):
                continue
            if closes_task_cycle(placed, question_deps, target_graph, before, after):
                continue
            a_ids, b_ids = targets[before]['concept_ids'], targets[after]['concept_ids']
            # An existence goal often names only concepts its detail goal also has (A and B; the detail goal adds C):
            # the edge still stands, from A (2026-11-16 job 635: 콜레라독소 소단위 → its A1·B pentamer details had none).
            source = next((c for c in a_ids if c not in b_ids), a_ids[0] if a_ids else None)
            # The two goals may even name the same concepts (normalize copied the detail goal's; 2차 시범 TQ017 = T109):
            # the relation then joins two of them; it records study order, not a map fact.
            sink = next((c for c in b_ids if c not in a_ids), next((c for c in b_ids if c != source), None))
            evidence = copy.deepcopy(targets[before].get('evidence') or [])
            if source is None or sink is None or not evidence or _reaches(concept_graph, sink, source):
                continue
            rid = existence_relation_id(before, after)
            new_relations.append({'relation_id': rid, 'from_id': source, 'to_id': sink, 'kind': 'prerequisite',
                                  'condition': f"{rec['a']} → {rec['b']}: 먼저 회상한다", 'evidence': evidence,
                                  'review_status': 'reviewed',
                                  'reason': f"{PRESUPPOSE}: {rec['question_id']}의 발문이 이 연결을 전제로 준다"})
            new_edges.append({'before_target': before, 'after_target': after, 'relation_id': rid})
            pairs.add((before, after))
            target_graph.setdefault(before, set()).add(after)
            concept_graph.setdefault(source, set()).add(sink)
    return new_relations, new_edges


def report(presuppositions, doc):
    """R5 counts of one result: links judged, recalled by a task, given an existence goal with tasks, still open."""
    placed = {t['question_id'] for t in doc['tasks']}
    edges = doc['prerequisites']
    owners = {d['direction_id']: t['target_id'] for t in doc['review']['targets'] for d in t['directions']}
    task_targets = {owners[t['direction_id']] for t in doc['tasks']}
    points = {p['point_id']: p['target_ids'] for p in doc['review']['points']}
    rows = [r for r in presuppositions if r['question_id'] in placed]
    recalled = [r for r in rows if any(q in placed for q in r['recalled_by'])]
    goal = [r for r in rows if r not in recalled and r['point_id'] and set(points.get(r['point_id'], [])) & task_targets]
    open_ = [r for r in rows if r not in recalled and r not in goal]
    return {'presupposed': len(rows), 'recalledByTask': len(recalled), 'existenceGoal': len(goal), 'open': open_,
            'prerequisites': len(edges)}


def mark_existence(ctx, brief, presuppositions, bank):
    """Add input: a goal made from a presupposition point carries `existence` (the stems that presuppose its link), so
    the author writes the question that recalls A→B instead of another detail (2026-11-15 콜레라 실측: 26 such goals,
    12 questions, several asking a function the bank already asked). Changes `ctx` in place and returns it."""
    stems = {q['question_id']: v3._front(q).get('question', '') for q in bank['questions']}
    by_point = {}
    for r in presuppositions or []:
        if r['point_id']:
            by_point.setdefault(r['point_id'], []).append(r['question_id'])
    owners = {d['direction_id']: t['target_id'] for t in brief['targets'] for d in t['directions']}
    targets = {}
    for p in brief['points']:
        for tid in p['target_ids']:
            targets.setdefault(tid, []).extend(by_point.get(p['point_id'], []))
    for goal in ctx['goals']:
        qids = sorted(set(targets.get(owners.get(goal['direction_id']), [])))
        if qids:
            goal['existence'] = {'presupposed_by': [{'question_id': q, 'question': stems.get(q, '')} for q in qids]}
    return ctx


def mark_review(ctx, brief, presuppositions, bank, exclude=()):
    """Item review and fix input: `existence`, one row per question of the batch written for an existence goal (a
    presupposition point in its point_ids) with the goal's cue, members and relation, and the stems that presuppose
    the link. Without it the review judged existence questions like detail ones (「too easy, ask by a condition」)
    and the fix put the next layer into the stem; the review also named only older relations, so a question went to
    an older goal and its existence goal stayed without a task (2026-11-16 job 635: Q231·Q241·Q243,
    docs/changes/2026-11-16-existence-question-shape). Changes `ctx` in place and returns it; no key when none.

    Only a question this run wrote may carry the label, by two rules
    (docs/changes/2026-11-17-existence-review-label):

    `exclude`: the questions already in the bank before this run wrote any, as `written_for` takes them. Point ids are
    not evidence of authorship — `_join_points` gives a goal's points to every question the coverage judgment lists as
    its evidence, and evidence includes a question that merely **provides** the link.

    A question whose own stem presupposed a goal's link is never that goal's existence question: a stem that hands
    A→B over and answers C cannot be the question that answers B. Without these the review read such a question as an
    existence item and told the fix to ask the members instead, so the detail it asked was overwritten and nothing
    asked it again — 41 of 43 labelled questions on 2026-11-16 (261116_02 Q057: 「Vero cell의 항바이러스 반응」 →
    「일본뇌염 백신의 제조 기질은?」, and no question left answering the IFN deficiency)."""
    pids = {r['point_id'] for r in presuppositions or [] if r['point_id']}
    if not pids:
        return ctx
    stems = {q['question_id']: v3._front(q).get('question', '') for q in bank['questions']}
    by_point = {}
    for r in presuppositions:
        if r['point_id']:
            by_point.setdefault(r['point_id'], set()).add(r['question_id'])
    points = {p['point_id']: p for p in brief['points']}
    targets = {t['target_id']: t for t in brief['targets']}
    skip = set(exclude)
    rows = []
    for q in ctx['questions']:
        if q['question_id'] in skip:
            continue
        mine = [p for p in q.get('point_ids', []) if p in pids and p in points
                and q['question_id'] not in by_point.get(p, ())]
        if not mine:
            continue
        goals = [d for p in mine for tid in points[p]['target_ids'] if tid in targets for d in targets[tid]['directions']]
        seen = []
        for d in goals:
            if d not in seen:
                seen.append(d)
        by = sorted({x for p in mine for x in by_point.get(p, ())} - {q['question_id']})
        rows.append({'question_id': q['question_id'],
                     'goals': [{'cue': d['cue'], 'components': [c['text'] for c in d['components']],
                                'relation_ids': list(d['relation_ids'])} for d in seen],
                     'presupposed_by': [{'question_id': x, 'question': stems.get(x, '')} for x in by]})
    if rows:
        ctx['existence'] = rows
    return ctx


def existence_directions(brief, presuppositions):
    """The goals made from presupposition points (existence goals), in map order."""
    pids = {r['point_id'] for r in presuppositions or [] if r['point_id']}
    tids = {t for p in brief['points'] if p['point_id'] in pids for t in p['target_ids']}
    return [d['direction_id'] for t in brief['targets'] if t['target_id'] in tids for d in t['directions']]


def _whole(row, goal):
    comps = {c['component_id'] for c in goal['components']}
    return {e['question_id'] for e in row['evidence']
            if comps and comps <= {p['component_id'] for p in e['components'] if p['location'] == 'answer'}}


def whole_answers(coverage_rows, brief, presuppositions):
    """(question, existence goal) pairs where one question answers every member of the goal. Placement puts such a
    question on its existence goal first (2026-11-15 2차 실측: the review named an older relation and the question for
    「C. jejuni가 일으키는 질환」 went to an older goal)."""
    goals = {d['direction_id']: d for t in brief['targets'] for d in t['directions']}
    rows = {r['direction_id']: r for r in coverage_rows}
    return {(q, did) for did in existence_directions(brief, presuppositions) if did in rows for q in _whole(rows[did], goals[did])}


def written_for(bank, brief, presuppositions, exclude=()):
    """Existence goals a question was already written for (a presupposition point in its point_ids). Each such goal
    gets one question: a later add round does not ask it again. On the 2026-11-16 trial the first question asked the
    members in one layer, coverage still missed the goal's other members, and the second round wrote the same question
    again (Q244 = Q253, both tasks; docs/changes/2026-11-16-existence-question-shape R7).

    `exclude`: the questions that were already in the bank before this run wrote any. They never count as written for
    an existence goal, however the goal's points reached them — `_join_points` gives a goal's points to every question
    the coverage judgment lists as its evidence, and evidence includes a question that merely **provides** the link.
    Without this the goal was read as already asked and no question was ever written for it: 261116_06 left
    「Cryptococcus의 주요 임상상은?」 unasked while 11 of its questions presupposed it (2026-11-16)."""
    pids = {r['point_id'] for r in presuppositions or [] if r['point_id']}
    skip = set(exclude)
    asked = {p for q in bank['questions'] if q['question_id'] not in skip
             for p in q.get('point_ids', []) if p in pids}
    tids = {t for p in brief['points'] if p['point_id'] in asked for t in p['target_ids']}
    return {d['direction_id'] for t in brief['targets'] if t['target_id'] in tids for d in t['directions']}


def existence_gaps(rows, brief, presuppositions):
    """Existence goals no single question asks whole, with all their members: the add stage writes one question that
    asks the whole category, not 「…를 제외한」 the members another question happens to ask (2차 실측)."""
    goals = {d['direction_id']: d for t in brief['targets'] for d in t['directions']}
    return {did: [c['component_id'] for c in goals[did]['components']]
            for did in existence_directions(brief, presuppositions) if did in rows and not _whole(rows[did], goals[did])}

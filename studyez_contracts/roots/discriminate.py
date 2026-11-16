"""discriminate/1 (docs/changes/2026-11-16-reverse-discriminating): the links a stem never makes the learner pick.

A named element of one category (an organism's factor, say) is **discriminable** when other owners in the lecture
have a category of the same kind: told only the cue (its action, target or finding), the learner has to pick which
owner's element it is. 「A의 B는?」 hands over A, so it never asks that. The `v4-discriminate` stage judges, per
category, which of its named elements are discriminable, which questions already ask one without naming its owner
(`asked_by`) and which ask it with the owner in the stem (`forward_by`). An element nobody asks the first way
becomes an exam point of origin `discrimination`, normalized into a reverse goal exactly as a presupposition
becomes an existence goal.

What the goal requires is the element name; whether the answer also names the owner is the author's call
(사용자 2026-11-16 「답에 소속은 꼭 강제 안해도 될듯? 그냥 예시였어」). The one hard rule is that the stem does not
name the owner, and that lives in the add prompt and the item review, not here: a forward question already answers
the element name, so coverage would call such a goal covered at once. `gaps` therefore keeps a reverse goal open
until a question carries its point, and `report` counts the stems that named the owner anyway.

At assembly a forward question's goal is ordered before the reverse goal (R7): recall 「A의 B」 once, then pick B
from the cue alone. Pure functions only: no model, DB or server.
"""
import copy
import re

from studyez_contracts.learning_links.schema import obj, arr, TEXT
from studyez_contracts.learning_links.validate import require, validate_shape
from .validate import document_hash
from . import generation_v3 as v3
from . import presuppose as pre

DISCRIMINATE = 'discriminate/1'
CHUNK = 40            # categories judged per stage call; every category of the map is the reference
ORIGIN = 'discrimination'
RELATION_PREFIX = 'RQD'

_POINT = copy.deepcopy(v3.POINT)
_POINT['properties'].pop('importance_basis')
_POINT['required'].remove('importance_basis')
ELEMENT = obj(element=TEXT, cue=TEXT, siblings=arr(TEXT), asked_by=arr(TEXT), forward_by=arr(TEXT),
              point={'anyOf': [_POINT, {'type': 'null'}]}, reason=TEXT)
OUTPUT = obj(rows=arr(obj(concept_id=TEXT, peer_concept_ids=arr(TEXT), elements=arr(ELEMENT), reason=TEXT)))
# The model-facing schema has anyOf (point or null); this pure module checks `point` by hand, as presuppose does.
_CHECKED = obj(rows=arr(obj(concept_id=TEXT, peer_concept_ids=arr(TEXT), reason=TEXT,
                            elements=arr(obj(element=TEXT, cue=TEXT, siblings=arr(TEXT), asked_by=arr(TEXT),
                                             forward_by=arr(TEXT), reason=TEXT)))))

NORMALIZE_OUTPUT = copy.deepcopy(pre.NORMALIZE_OUTPUT)

# A name of its own: letters, digits and ASCII hyphens (piperacillin-tazobactam). An en dash or em dash
# separates a name from its gloss in these labels (「LasB–zinc metalloprotease」), so it is not part of one.
_NAME = re.compile(r'[A-Za-z][A-Za-z0-9\-]{2,}')


# ---------------------------------------------------------------- the map side
def _children(brief):
    kids = {}
    for c in brief['concepts']:
        for p in c.get('parent_ids') or []:
            kids.setdefault(p, []).append(c['concept_id'])
    return kids


def owners(brief):
    """concept_id → the top-level concept it hangs under (its owner: the organism, drug group or other subject the
    lecture puts the category beneath). A root is its own owner; a concept reached from several roots takes the
    first in map order, as the map's own ordering decides."""
    kids = _children(brief)
    roots = [c['concept_id'] for c in brief['concepts'] if not (c.get('parent_ids') or [])]
    found = {}
    for root in roots:
        for top in kids.get(root, ()):
            seen, todo = set(), [top]
            while todo:
                node = todo.pop()
                if node in seen:
                    continue
                seen.add(node)
                found.setdefault(node, top)
                todo.extend(kids.get(node, ()))
    for root in roots:
        found.setdefault(root, root)
    return found


def named(label):
    """The named elements of a concept label: 「이름 있는 인자만」 (사용자 2026-11-16). A label with no name of its
    own (a Korean description of a mechanism step, say) has none, so code never sends it as an element."""
    return [m.group(0) for m in _NAME.finditer(label or '')]


def categories(brief):
    """The category concepts worth judging, in map order: a concept whose children carry named elements. The kind of
    a category is not read from its label — labels differ per owner (2026-11-16 실측: 64 categories, no label shared
    across owners) — so the stage names the peers and this only limits the volume."""
    kids, who = _children(brief), owners(brief)
    labels = {c['concept_id']: c['label'] for c in brief['concepts']}
    out = []
    for c in brief['concepts']:
        cid = c['concept_id']
        if not kids.get(cid) or who.get(cid) == cid:
            continue
        elements = sorted({n for k in kids[cid] for n in named(labels.get(k, ''))})
        if elements:
            out.append(cid)
    return out


def _row(brief, cid, kids, labels, who):
    return {'concept_id': cid, 'category': labels.get(cid, ''), 'owner': labels.get(who.get(cid), ''),
            'owner_id': who.get(cid, ''),
            'elements': sorted({n for k in kids.get(cid, ()) for n in named(labels.get(k, ''))}),
            'members': [labels.get(k, '') for k in kids.get(cid, ())]}


def stage_input(brief, bank, concept_ids, page_counts):
    """The categories to judge, every category of the map as the reference for peers, the bank's fronts for
    `asked_by`/`forward_by`, and the pages the questions of each judged category cite (where a point may point)."""
    kids = _children(brief)
    labels, owner_of = {c['concept_id']: c['label'] for c in brief['concepts']}, owners(brief)
    wanted = list(concept_ids)
    known = {c['concept_id'] for c in brief['concepts']}
    require(set(wanted) <= known, 'discriminate: unknown concept')
    subtree = set()
    for cid in wanted:
        todo = [cid]
        while todo:
            node = todo.pop()
            if node in subtree:
                continue
            subtree.add(node)
            todo.extend(kids.get(node, ()))
    refs = [r for q in bank['questions'] if q.get('concept_id') in subtree for r in q.get('source_refs', [])]
    return {'categories': [_row(brief, cid, kids, labels, owner_of) for cid in wanted],
            'all_categories': [_row(brief, cid, kids, labels, owner_of) for cid in categories(brief)],
            'all_questions': [pre._reference(q) for q in bank['questions']],
            'page_counts': dict(page_counts),
            'pages': v3.cited_pages(refs)}


# ---------------------------------------------------------------- judgment
def check(value, ctx):
    """One discriminate output: every judged category exactly once; an element either names the questions that ask it
    without its owner or, when none does, the exam point a reverse goal is made from."""
    require(type(value) is dict and type(value.get('rows')) is list, 'discriminate output: rows required')
    for row in value['rows']:
        require(type(row) is dict and type(row.get('elements')) is list, 'discriminate output: elements required')
        for el in row['elements']:
            require(type(el) is dict and 'point' in el and (el['point'] is None or type(el['point']) is dict),
                    'discriminate output: point is an object or null')
    validate_shape({'rows': [{**r, 'elements': [{k: v for k, v in e.items() if k != 'point'} for e in r['elements']]}
                             for r in value['rows']]}, _CHECKED, 'discriminate output')
    judged = [c['concept_id'] for c in ctx['categories']]
    rows = [r['concept_id'] for r in value['rows']]
    require(sorted(rows) == sorted(judged) and len(rows) == len(set(rows)),
            'discriminate: rows must name every judged category once')
    allowed = {c['concept_id']: c for c in ctx['all_categories']}
    known_q = {q['question_id'] for q in ctx['all_questions']}
    for row in value['rows']:
        mine = allowed.get(row['concept_id']) or next(c for c in ctx['categories'] if c['concept_id'] == row['concept_id'])
        peers = row['peer_concept_ids']
        require(len(peers) == len(set(peers)) and set(peers) <= set(allowed) and row['concept_id'] not in peers,
                f"discriminate {row['concept_id']}: peers are other categories of this map")
        require(all(allowed[p]['owner_id'] != mine['owner_id'] for p in peers),
                f"discriminate {row['concept_id']}: a peer belongs to another owner")
        if not peers:
            require(not row['elements'],
                    f"discriminate {row['concept_id']}: without a peer category nothing is discriminable")
        names = [e['element'] for e in row['elements']]
        require(len(names) == len(set(names)), f"discriminate {row['concept_id']}: one row per element")
        for el in row['elements']:
            require(el['element'] in mine['elements'],
                    f"discriminate {row['concept_id']}: {el['element']} is not a named element of this category")
            for key in ('asked_by', 'forward_by'):
                ids = el[key]
                require(len(ids) == len(set(ids)) and set(ids) <= known_q,
                        f"discriminate {row['concept_id']}/{el['element']}: {key} names unknown questions")
            if el['asked_by']:
                require(el['point'] is None,
                        f"discriminate {row['concept_id']}/{el['element']}: an element already asked carries no point")
            else:
                require(el['point'] is not None,
                        f"discriminate {row['concept_id']}/{el['element']}: an element nobody asks needs its point")
                v3._check_point({**el['point'], 'importance_basis': []})
                for ref in el['point']['source_refs']:
                    # A source without pages (text) has page count None: it is cited by locator only.
                    require(ref['source_id'] in ctx['page_counts'],
                            f"discriminate {row['concept_id']}/{el['element']}: point pages outside the sources")
                    count = ctx['page_counts'][ref['source_id']]
                    require(all(count is not None and 1 <= p <= count for p in ref['pages']),
                            f"discriminate {row['concept_id']}/{el['element']}: point pages outside the sources")
    return value


def _norm(text):
    return re.sub(r'\s+', ' ', text or '').strip().casefold()


def records(outputs, bank, points_doc, brief, reserved=()):
    """Every judged element in map order, and the new exam points of the elements nobody asks by the cue alone. One
    point per (owner, element) and one per point text, as presuppose does for its links. Questions that left the bank
    since the judgment are dropped from `asked_by`/`forward_by`. The owner is read from the map, never from the
    judgment: it decides what a stem may not say, so it is not the model's to restate.

    Returns (points_doc, records, new_points)."""
    present = {q['question_id'] for q in bank['questions']}
    labels = {c['concept_id']: c['label'] for c in brief['concepts']}
    owner_of = owners(brief)

    def owner(cid):
        return labels.get(owner_of.get(cid), '')
    numbers = [int(m.group(1)) for pid in [*(p['point_id'] for p in points_doc['points']), *reserved]
               for m in [re.fullmatch(r'P(\d+)', pid)] if m]
    nxt = max(numbers, default=0) + 1
    value = copy.deepcopy(points_doc)
    made, by_text, out, new = {}, {}, [], []
    for got in outputs:
        for row in got['rows']:
            for el in row['elements']:
                asked = [q for q in el['asked_by'] if q in present]
                forward = [q for q in el['forward_by'] if q in present]
                pid = None
                if not el['asked_by']:
                    key, text = (_norm(owner(row['concept_id'])), _norm(el['element'])), _norm(el['point']['point'])
                    pid = made.get(key) or by_text.get(text)
                    if pid is None:
                        pid = f'P{nxt:03d}'
                        nxt += 1
                        point = {'point_id': pid, **copy.deepcopy(el['point']), 'origin': ORIGIN,
                                 'origin_concept_id': row['concept_id']}
                        value['points'].append(point)
                        new.append(point)
                    made.setdefault(key, pid)
                    by_text.setdefault(text, pid)
                out.append({'concept_id': row['concept_id'], 'owner': owner(row['concept_id']), 'element': el['element'],
                            'cue': el['cue'], 'siblings': list(el['siblings']), 'asked_by': asked,
                            'forward_by': forward, 'point_id': pid})
    return value, out, new


# ---------------------------------------------------------------- reverse goals
def normalize_input(brief, new_points, allowed):
    """v3 supplement-normalize input with the IDs the new content relations may take (at most one per point)."""
    return {**v3.supplement_normalize_input(brief, new_points, allowed),
            'allowed_relation_ids': pre.relation_ids(brief, len(new_points), prefix=RELATION_PREFIX)}


def extend(brief, value, new_point_ids):
    return pre.extend(brief, value, new_point_ids)


def check_normalize(value, ctx, state=None):
    validate_shape(value, NORMALIZE_OUTPUT, 'discriminate normalize output')
    concepts = {c['concept_id'] for c in ctx['concepts']}
    allowed = set(ctx['allowed_relation_ids'])
    ids = [r['relation_id'] for r in value['relations']]
    require(len(ids) == len(set(ids)) and set(ids) <= allowed,
            'discriminate normalize: relation IDs outside the allowed range')
    for r in value['relations']:
        require(r['from_id'] in concepts and r['to_id'] in concepts and r['from_id'] != r['to_id'],
                f"discriminate normalize: {r['relation_id']} joins existing concepts")
        require(r['kind'] == 'association' and r['review_status'] == 'unreviewed',
                f"discriminate normalize: {r['relation_id']} is an unreviewed content relation (association)")
    known = {**ctx, 'relations': [*ctx['relations'], *({'relation_id': r['relation_id']} for r in value['relations'])]}
    v3.check_supplement_normalize({'targets': value['targets'], 'points': value['points']}, known)
    if state is not None:
        extend(state['brief'], value, [p['point_id'] for p in ctx['points']])
    return value


def blank_rows(direction_ids):
    """The coverage rows of brand-new reverse goals. No judgment is asked for them: a published forward question
    answers the element name, so a judgment would call the goal covered and `_join_points` would hand that question
    the goal's point — after which `written_for` reads the goal as already written and no reverse question is ever
    written (caught by the pipeline test, 2026-11-16). The add round's own coverage call judges them once the
    question exists."""
    return {did: {'direction_id': did, 'status': 'missing', 'evidence': [], 'duplicates': [],
                  'reason': f'{DISCRIMINATE}: 역방향 목표는 문항을 쓴 뒤에 범위를 본다'} for did in direction_ids}


def reverse_directions(brief, records):
    """The goals made from discrimination points (reverse goals), in map order."""
    pids = {r['point_id'] for r in records or [] if r['point_id']}
    tids = {t for p in brief['points'] if p['point_id'] in pids for t in p['target_ids']}
    return [d['direction_id'] for t in brief['targets'] if t['target_id'] in tids for d in t['directions']]


def written_for(bank, brief, records):
    """Reverse goals a question was already written for (a discrimination point in its point_ids). Each such goal
    gets one question; a later add round does not ask it again (presuppose/1 R7's lesson)."""
    pids = {r['point_id'] for r in records or [] if r['point_id']}
    asked = {p for q in bank['questions'] for p in q.get('point_ids', []) if p in pids}
    tids = {t for p in brief['points'] if p['point_id'] in asked for t in p['target_ids']}
    return {d['direction_id'] for t in brief['targets'] if t['target_id'] in tids for d in t['directions']}


def gaps(brief, records, bank):
    """Reverse goals still open, with all their members. Not a coverage verdict: the element name is what a forward
    question already answers, so coverage calls such a goal covered as soon as it looks (that is the whole point of
    the goal — the same content from the other end). A reverse goal is open until a question carries its point."""
    goals = {d['direction_id']: d for t in brief['targets'] for d in t['directions']}
    done = written_for(bank, brief, records)
    return {did: [c['component_id'] for c in goals[did]['components']]
            for did in reverse_directions(brief, records) if did not in done and did in goals}


# ---------------------------------------------------------------- what the author and the reviewer are told
def _by_point(records):
    by = {}
    for r in records or []:
        if r['point_id']:
            by.setdefault(r['point_id'], []).append(r)
    return by


def _goal_points(brief):
    owner = {}
    for p in brief['points']:
        for tid in p['target_ids']:
            owner.setdefault(tid, []).append(p['point_id'])
    return owner


def mark_add(ctx, brief, records, bank):
    """Add input: a goal made from a discrimination point carries `discrimination` — the cue, the element, the
    siblings the cue has to beat and the forward questions' stems (not to copy). Changes `ctx` in place."""
    stems = {q['question_id']: v3._front(q).get('question', '') for q in bank['questions']}
    by_point, by_target = _by_point(records), _goal_points(brief)
    owners_of = {d['direction_id']: t['target_id'] for t in brief['targets'] for d in t['directions']}
    for goal in ctx['goals']:
        mine = [r for pid in by_target.get(owners_of.get(goal['direction_id']), []) for r in by_point.get(pid, [])]
        if not mine:
            continue
        goal['discrimination'] = [
            {'owner': r['owner'], 'element': r['element'], 'cue': r['cue'], 'siblings': list(r['siblings']),
             'forward_by': [{'question_id': q, 'question': stems.get(q, '')} for q in r['forward_by']]}
            for r in mine]
    return ctx


def mark_review(ctx, brief, records, bank):
    """Item review and fix input: `discrimination`, one row per question of the batch written for a reverse goal, with
    the cue it asks by and the stems of the forward questions. Without it the review reads a cue-only stem as an
    incomplete question and the fix names the owner in it — which is the one thing this goal forbids (presuppose/1
    hit exactly this: 「too easy, ask by a condition」, docs/changes/2026-11-16-existence-question-shape).
    Changes `ctx` in place and returns it; no key when none."""
    pids = {r['point_id'] for r in records or [] if r['point_id']}
    if not pids:
        return ctx
    stems = {q['question_id']: v3._front(q).get('question', '') for q in bank['questions']}
    by_point = _by_point(records)
    points = {p['point_id']: p for p in brief['points']}
    targets = {t['target_id']: t for t in brief['targets']}
    rows = []
    for q in ctx['questions']:
        mine = [p for p in q.get('point_ids', []) if p in pids and p in points]
        if not mine:
            continue
        got, seen = [], []
        for p in mine:
            for r in by_point.get(p, []):
                if (r['owner'], r['element']) not in seen:
                    seen.append((r['owner'], r['element']))
                    got.append(r)
        goals = [d for p in mine for tid in points[p]['target_ids'] if tid in targets
                 for d in targets[tid]['directions']]
        cues = []
        for d in goals:
            if d not in cues:
                cues.append(d)
        rows.append({'question_id': q['question_id'],
                     'goals': [{'cue': d['cue'], 'components': [c['text'] for c in d['components']],
                                'relation_ids': list(d['relation_ids'])} for d in cues],
                     'elements': [{'owner': r['owner'], 'element': r['element'], 'cue': r['cue'],
                                   'siblings': list(r['siblings']),
                                   'forward_by': [{'question_id': x, 'question': stems.get(x, '')}
                                                  for x in r['forward_by']]} for r in got]})
    if rows:
        ctx['discrimination'] = rows
    return ctx


# ---------------------------------------------------------------- study order at assembly
def reverse_relation_id(before, after):
    return 'REV-' + document_hash([before, after])[:12]


def is_reverse_edge(edge):
    """A target prerequisite order_edges made here: a forward goal before the reverse goal of the same element. Unlike
    an existence edge this is not brought forward outside today's tiers — the reverse question is the second pass over
    content the forward question already covers, so it waits for its turn."""
    return re.fullmatch(r'REV-[0-9a-f]{12}', edge.get('relation_id') or '') is not None


def order_edges(brief, tasks, records, relations, edges):
    """Target prerequisites from the discrimination records: the goal of a forward question before the reverse goal.
    Only goals with tasks take part; an edge that would close a cycle, or whose relation would join a concept to
    itself, is left out. Returns (relations, edges) to add."""
    targets = {t['target_id']: t for t in brief['targets']}
    owners_of = {d['direction_id']: t['target_id'] for t in brief['targets'] for d in t['directions']}
    placed = {t['question_id']: owners_of[t['direction_id']] for t in tasks}
    from_points = {p['point_id']: list(p['target_ids']) for p in brief['points']}
    target_graph, concept_graph = {}, {}
    for e in edges:
        target_graph.setdefault(e['before_target'], set()).add(e['after_target'])
    for r in relations:
        if r['kind'] == 'prerequisite':
            concept_graph.setdefault(r['from_id'], set()).add(r['to_id'])
    pairs = {(e['before_target'], e['after_target']) for e in edges}
    new_relations, new_edges = [], []
    for rec in records:
        if not rec['point_id']:
            continue
        afters = [t for t in from_points.get(rec['point_id'], []) if t in set(placed.values())]
        befores = {placed[q] for q in rec['forward_by'] if q in placed}
        for after in sorted(afters):
            for before in sorted(befores - {after}):
                if (before, after) in pairs or pre._reaches(target_graph, after, before):
                    continue
                a_ids, b_ids = targets[before]['concept_ids'], targets[after]['concept_ids']
                source = next((c for c in a_ids if c not in b_ids), a_ids[0] if a_ids else None)
                sink = next((c for c in b_ids if c not in a_ids), next((c for c in b_ids if c != source), None))
                evidence = copy.deepcopy(targets[before].get('evidence') or [])
                if source is None or sink is None or not evidence or pre._reaches(concept_graph, sink, source):
                    continue
                rid = reverse_relation_id(before, after)
                new_relations.append({'relation_id': rid, 'from_id': source, 'to_id': sink, 'kind': 'prerequisite',
                                      'condition': f"{rec['owner']}의 {rec['element']}: 먼저 정방향으로 회상한다",
                                      'evidence': evidence, 'review_status': 'reviewed',
                                      'reason': f"{DISCRIMINATE}: 단서만으로 고르기 전에 이 연결을 정방향으로 묻는다"})
                new_edges.append({'before_target': before, 'after_target': after, 'relation_id': rid})
                pairs.add((before, after))
                target_graph.setdefault(before, set()).add(after)
                concept_graph.setdefault(source, set()).add(sink)
    return new_relations, new_edges


# ---------------------------------------------------------------- report (R9)
def named_owner_in_stem(doc, records, bank):
    """The reverse questions whose stem names the owner anyway — the one rule this policy asks for, measured rather
    than enforced (a hard failure would hold a whole lecture over one stem). The owner's own words are matched: its
    label and each name inside it."""
    pids = {r['point_id']: r for r in records or [] if r['point_id']}
    by_point = _by_point(records)
    found = []
    for q in bank['questions']:
        mine = [p for p in q.get('point_ids', []) if p in pids]
        if not mine:
            continue
        stem = _norm(v3._front(q).get('question', ''))
        for p in mine:
            for rec in by_point.get(p, []):
                words = [rec['owner'], *named(rec['owner'])]
                hit = next((w for w in words if len(_norm(w)) >= 3 and _norm(w) in stem), None)
                if hit:
                    found.append({'question_id': q['question_id'], 'owner': rec['owner'], 'named': hit})
                    break
            else:
                continue
            break
    return found


def report(records, doc, bank):
    """R9 counts of one result: elements judged discriminable, already asked by the cue alone, given a reverse goal
    with a task, still open, and the reverse stems that named their owner."""
    placed = {t['question_id'] for t in doc['tasks']}
    owners_of = {d['direction_id']: t['target_id'] for t in doc['review']['targets'] for d in t['directions']}
    task_targets = {owners_of[t['direction_id']] for t in doc['tasks']}
    points = {p['point_id']: p['target_ids'] for p in doc['review']['points']}
    asked = [r for r in records if r['asked_by']]
    goal = [r for r in records if r['point_id'] and set(points.get(r['point_id'], [])) & task_targets]
    open_ = [r for r in records if r['point_id'] and r not in goal]
    return {'discriminable': len(records), 'alreadyAsked': len(asked), 'reverseGoal': len(goal),
            'open': [f"{r['owner']}의 {r['element']}" for r in open_],
            'ownerInStem': named_owner_in_stem(doc, records, bank),
            'placedReverse': len([r for r in goal if any(q in placed for q in r['forward_by'])])}

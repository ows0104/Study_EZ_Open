"""discriminate/1 (docs/changes/2026-11-16-reverse-discriminating): the goals no question asks from the other end.

A goal asks A → B: given the pathogen, the drug group, the disease, name what it has, does or needs. A learner who
only ever answers that direction cannot start from B. The `v4-discriminate` stage reads **the lecture's own goals**,
not a shape of the map, and judges per goal whether its other end deserves a question: a stem that gives only B (an
action, a target, a finding, a use) and asks for A.

It is judged per goal because a reverse is not one shape. 「이 기전을 가진 약은?」, 「이 소견을 보이는 질환은?」 and
「이 인자를 가진 균은?」 are the same move in three subjects; an earlier draft hard-coded one map shape (organism →
category → named element) and could only ever find the third (사용자 2026-11-16 「지금 이 강의에 너무 특이적으로
제한되어서 하는거 아니야? 역방향을 사실 정말 다양한 게 있을 수 있잖아」).

What keeps the count down is not the shape but the judgment: a reverse is asked only when the lecture holds other
candidates the stem has to rule out (`competitors`), so the learner really has to pick (사용자 「일단은 판별되는
연결만」). A goal nobody asks in reverse becomes an exam point of origin `discrimination`, normalized into a reverse
goal exactly as a presupposition becomes an existence goal.

The answer is what the reverse recalls; whether its wording also names the owner is the author's call (사용자 「답에
소속은 꼭 강제 안해도 될듯? 그냥 예시였어」). The one hard rule is that the stem does not give away the side it asks
for, and that lives in the add prompt and the item review, not here: the forward question already answers it, so
coverage would call such a goal covered at once. `gaps` therefore keeps a reverse goal open until a question carries
its point, and `report` counts the stems that gave it away anyway.

At assembly the forward goal is ordered before its reverse (R7). Pure functions only: no model, DB or server.
"""
import copy
import re

from studyez_contracts.learning_links.schema import obj, arr, TEXT
from studyez_contracts.learning_links.validate import require, validate_shape
from .validate import document_hash
from . import generation_v3 as v3
from . import presuppose as pre

DISCRIMINATE = 'discriminate/1'
CHUNK = 30            # goals judged per stage call; every goal and question of the lecture is the reference
ORIGIN = 'discrimination'
RELATION_PREFIX = 'RQD'

_POINT = copy.deepcopy(v3.POINT)
_POINT['properties'].pop('importance_basis')
_POINT['required'].remove('importance_basis')
# `cue`/`answer` are empty on a goal judged not worth reversing, so they are plain strings here and `check` is what
# requires them when `reversible` is true.
_MAYBE = {'type': 'string'}
ROW = obj(direction_id=TEXT, reversible={'type': 'boolean'}, cue=_MAYBE, answer=_MAYBE, competitors=arr(TEXT),
          asked_by=arr(TEXT), forward_by=arr(TEXT), point={'anyOf': [_POINT, {'type': 'null'}]}, reason=TEXT)
OUTPUT = obj(rows=arr(ROW))
# The model-facing schema has anyOf (point or null); this pure module checks `point` by hand, as presuppose does.
_CHECKED = obj(rows=arr(obj(direction_id=TEXT, reversible={'type': 'boolean'}, cue=_MAYBE, answer=_MAYBE,
                            competitors=arr(TEXT), asked_by=arr(TEXT), forward_by=arr(TEXT), reason=TEXT)))

NORMALIZE_OUTPUT = copy.deepcopy(pre.NORMALIZE_OUTPUT)


# ---------------------------------------------------------------- the goals to judge
def goals(brief):
    """Every goal of the lecture, in map order. The judgment decides which have a reverse worth asking; code does
    not pre-filter by map shape (that is what made the first draft microbiology-only)."""
    return [d['direction_id'] for t in brief['targets'] for d in t['directions']]


def stage_input(brief, bank, direction_ids, page_counts):
    """The goals to judge with their forward cue and answer, every goal of the lecture as the reference for
    competitors, the bank's fronts for `asked_by`/`forward_by`, and the pages those goals cite."""
    known = goals(brief)
    wanted = list(direction_ids)
    require(set(wanted) <= set(known), 'discriminate: unknown goal')
    mine = [v3._goal(brief, did) for did in wanted]
    every = [{k: g[k] for k in ('direction_id', 'cue', 'answer_scope')} for g in (v3._goal(brief, d) for d in known)]
    refs = [r for t in brief['targets'] for d in t['directions'] if d['direction_id'] in set(wanted)
            for r in (t.get('evidence') or [])]
    return {'goals': mine, 'all_goals': every,
            'all_questions': [pre._reference(q) for q in bank['questions']],
            'page_counts': dict(page_counts),
            'pages': v3.cited_pages(refs)}


# ---------------------------------------------------------------- judgment
def check(value, ctx):
    """One discriminate output: every judged goal exactly once; a goal worth reversing either names the questions
    that already ask it that way or, when none does, the exam point its reverse goal is made from."""
    require(type(value) is dict and type(value.get('rows')) is list, 'discriminate output: rows required')
    for row in value['rows']:
        require(type(row) is dict and 'point' in row and (row['point'] is None or type(row['point']) is dict),
                'discriminate output: point is an object or null')
    validate_shape({'rows': [{k: v for k, v in r.items() if k != 'point'} for r in value['rows']]},
                   _CHECKED, 'discriminate output')
    judged = [g['direction_id'] for g in ctx['goals']]
    rows = [r['direction_id'] for r in value['rows']]
    require(sorted(rows) == sorted(judged) and len(rows) == len(set(rows)),
            'discriminate: rows must name every judged goal once')
    known_q = {q['question_id'] for q in ctx['all_questions']}
    for row in value['rows']:
        did = row['direction_id']
        for key in ('asked_by', 'forward_by'):
            ids = row[key]
            require(len(ids) == len(set(ids)) and set(ids) <= known_q,
                    f"discriminate {did}: {key} names unknown questions")
        if not row['reversible']:
            require(not row['asked_by'] and row['point'] is None,
                    f"discriminate {did}: a goal not worth reversing carries no point")
            continue
        require(len(row['competitors']) >= 1,
                f"discriminate {did}: a reverse needs the candidates its stem rules out")
        require(row['cue'].strip() and row['answer'].strip(),
                f"discriminate {did}: the reverse needs a cue and an answer")
        if row['asked_by']:
            require(row['point'] is None, f"discriminate {did}: a reverse already asked carries no point")
        else:
            require(row['point'] is not None, f"discriminate {did}: a reverse nobody asks needs its point")
            v3._check_point({**row['point'], 'importance_basis': []})
            for ref in row['point']['source_refs']:
                # A source without pages (text) has page count None: it is cited by locator only.
                require(ref['source_id'] in ctx['page_counts'], f"discriminate {did}: point pages outside the sources")
                count = ctx['page_counts'][ref['source_id']]
                require(all(count is not None and 1 <= p <= count for p in ref['pages']),
                        f"discriminate {did}: point pages outside the sources")
    return value


def _norm(text):
    return re.sub(r'\s+', ' ', text or '').strip().casefold()


def records(outputs, bank, points_doc, brief, reserved=()):
    """Every goal judged reversible, in map order, and the new exam points of the reverses nobody asks. One point
    per (answer, cue) and one per point text. Questions that left the bank since the judgment are dropped from
    `asked_by`/`forward_by`.

    Returns (points_doc, records, new_points)."""
    present = {q['question_id'] for q in bank['questions']}
    order = {did: n for n, did in enumerate(goals(brief))}
    numbers = [int(m.group(1)) for pid in [*(p['point_id'] for p in points_doc['points']), *reserved]
               for m in [re.fullmatch(r'P(\d+)', pid)] if m]
    nxt = max(numbers, default=0) + 1
    value = copy.deepcopy(points_doc)
    made, by_text, out, new = {}, {}, [], []
    rows = [r for got in outputs for r in got['rows'] if r['reversible']]
    for row in sorted(rows, key=lambda r: order.get(r['direction_id'], len(order))):
        pid = None
        if not row['asked_by']:
            key, text = (_norm(row['answer']), _norm(row['cue'])), _norm(row['point']['point'])
            pid = made.get(key) or by_text.get(text)
            if pid is None:
                pid = f'P{nxt:03d}'
                nxt += 1
                point = {'point_id': pid, **copy.deepcopy(row['point']), 'origin': ORIGIN,
                         'origin_direction_id': row['direction_id']}
                value['points'].append(point)
                new.append(point)
            made.setdefault(key, pid)
            by_text.setdefault(text, pid)
        out.append({'direction_id': row['direction_id'], 'cue': row['cue'], 'answer': row['answer'],
                    'competitors': list(row['competitors']),
                    'asked_by': [q for q in row['asked_by'] if q in present],
                    'forward_by': [q for q in row['forward_by'] if q in present], 'point_id': pid})
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
    """The coverage rows of brand-new reverse goals. No judgment is asked for them: the forward question already
    answers the same content, so a judgment would call the goal covered and `_join_points` would hand that question
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


def written_for(bank, brief, records, exclude=()):
    """Reverse goals a question was already written for (a discrimination point in its point_ids). Each such goal
    gets one question; a later add round does not ask it again (presuppose/1 R7's lesson).

    `exclude`: the questions already in the bank before this run wrote any. A reverse goal starts with a blank
    coverage row (`blank_rows`), so `_join_points` cannot hand its point to one of them before the first add round —
    but a later round's coverage can, and then the goal would look written for (presuppose/1 hit exactly that)."""
    pids = {r['point_id'] for r in records or [] if r['point_id']}
    skip = set(exclude)
    asked = {p for q in bank['questions'] if q['question_id'] not in skip
             for p in q.get('point_ids', []) if p in pids}
    tids = {t for p in brief['points'] if p['point_id'] in asked for t in p['target_ids']}
    return {d['direction_id'] for t in brief['targets'] if t['target_id'] in tids for d in t['directions']}


def gaps(brief, records, bank, exclude=()):
    """Reverse goals still open, with all their members. Not a coverage verdict: the forward question answers the
    same content, so coverage calls such a goal covered as soon as it looks (that is the whole point of the goal —
    the same connection from the other end). A reverse goal is open until a question carries its point."""
    every = {d['direction_id']: d for t in brief['targets'] for d in t['directions']}
    done = written_for(bank, brief, records, exclude=exclude)
    return {did: [c['component_id'] for c in every[did]['components']]
            for did in reverse_directions(brief, records) if did not in done and did in every}


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


def _told(records, stems):
    return [{'cue': r['cue'], 'answer': r['answer'], 'competitors': list(r['competitors']),
             'forward_by': [{'question_id': q, 'question': stems.get(q, '')} for q in r['forward_by']]}
            for r in records]


def mark_add(ctx, brief, records, bank):
    """Add input: a goal made from a discrimination point carries `discrimination` — the reverse cue, what it must
    recall, the candidates the stem has to rule out, and the forward questions' stems (not to copy). Changes `ctx`
    in place and returns it."""
    stems = {q['question_id']: v3._front(q).get('question', '') for q in bank['questions']}
    by_point, by_target = _by_point(records), _goal_points(brief)
    owners_of = {d['direction_id']: t['target_id'] for t in brief['targets'] for d in t['directions']}
    for goal in ctx['goals']:
        mine = [r for pid in by_target.get(owners_of.get(goal['direction_id']), []) for r in by_point.get(pid, [])]
        if mine:
            goal['discrimination'] = _told(mine, stems)
    return ctx


def mark_review(ctx, brief, records, bank):
    """Item review and fix input: `discrimination`, one row per question of the batch written for a reverse goal,
    with the cue it asks by and the stems of the forward questions. Without it the review reads a cue-only stem as an
    incomplete question and the fix puts the answer's own side back into it — which is the one thing this goal
    forbids (presuppose/1 hit exactly this: 「too easy, ask by a condition」,
    docs/changes/2026-11-16-existence-question-shape). Changes `ctx` in place; no key when none."""
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
                if (r['cue'], r['answer']) not in seen:
                    seen.append((r['cue'], r['answer']))
                    got.append(r)
        every = [d for p in mine for tid in points[p]['target_ids'] if tid in targets
                 for d in targets[tid]['directions']]
        cues = []
        for d in every:
            if d not in cues:
                cues.append(d)
        rows.append({'question_id': q['question_id'],
                     'goals': [{'cue': d['cue'], 'components': [c['text'] for c in d['components']],
                                'relation_ids': list(d['relation_ids'])} for d in cues],
                     'reverses': _told(got, stems)})
    if rows:
        ctx['discrimination'] = rows
    return ctx


# ---------------------------------------------------------------- study order at assembly
def reverse_relation_id(before, after):
    return 'REV-' + document_hash([before, after])[:12]


def is_reverse_edge(edge):
    """A target prerequisite order_edges made here: a forward goal before its reverse. Unlike an existence edge this
    is not brought forward outside today's tiers — the reverse is the second pass over content the forward question
    already covers, so it waits for its turn."""
    return re.fullmatch(r'REV-[0-9a-f]{12}', edge.get('relation_id') or '') is not None


def order_edges(brief, tasks, records, relations, edges):
    """Target prerequisites from the discrimination records: the forward goal (the judged goal itself, and the goals
    of the questions that ask it forward) before the reverse goal. Only goals with tasks take part; an edge that
    would close a cycle, or whose relation would join a concept to itself, is left out."""
    targets = {t['target_id']: t for t in brief['targets']}
    owners_of = {d['direction_id']: t['target_id'] for t in brief['targets'] for d in t['directions']}
    placed = {t['question_id']: owners_of[t['direction_id']] for t in tasks}
    task_targets = set(placed.values())
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
        afters = [t for t in from_points.get(rec['point_id'], []) if t in task_targets]
        befores = {placed[q] for q in rec['forward_by'] if q in placed}
        own = owners_of.get(rec['direction_id'])
        if own in task_targets:
            befores.add(own)
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
                                      'condition': f"{rec['answer']}: 먼저 정방향으로 회상한다", 'evidence': evidence,
                                      'review_status': 'reviewed',
                                      'reason': f"{DISCRIMINATE}: 단서만으로 고르기 전에 이 연결을 정방향으로 묻는다"})
                new_edges.append({'before_target': before, 'after_target': after, 'relation_id': rid})
                pairs.add((before, after))
                target_graph.setdefault(before, set()).add(after)
                concept_graph.setdefault(source, set()).add(sink)
    return new_relations, new_edges


# ---------------------------------------------------------------- report (R9)
def _names(text):
    """The names of an answer: its Latin/English words of three characters or more. A Korean word is not taken
    apart, because the words an answer shares with its own question are its category (「내성 유형은? → 내인성
    내성」, 「원인균은? → V. vulnificus 중증 감염」) and a stem cannot ask without them — matching those called
    three of 17 stems a give-away on the 2026-11-16 trial when none was. The whole answer in the stem is the
    Korean case, and `answer_in_stem` looks for that separately."""
    return re.findall(r'[A-Za-z][A-Za-z0-9\-]{2,}', text or '')


def placed_on_reverse(doc, records):
    """The questions a document places on a reverse goal. Carrying a discrimination point is not the same thing:
    `_join_points` hands that point to every question the coverage judgment ties to the goal, forward ones included,
    and those keep their own goals. Without this the measurement read a forward stem as a give-away — all 8 hits on
    261116_02 were forward questions (2026-11-16, 다른 세션이 짚었다). None when the document is not at hand."""
    if not doc:
        return None
    pids = {r['point_id'] for r in records or [] if r['point_id']}
    tids = {t for p in doc['review']['points'] if p['point_id'] in pids for t in p['target_ids']}
    owners_of = {d['direction_id']: t['target_id'] for t in doc['review']['targets'] for d in t['directions']}
    return {t['question_id'] for t in doc['tasks'] if owners_of.get(t['direction_id']) in tids}


def answer_in_stem(doc, records, bank):
    """The reverse questions whose stem gives away the side it asks for — the one rule this policy asks for,
    measured rather than enforced (a hard failure would hold a whole lecture over one stem). A stem gives it away
    when it carries a name of the answer, or the answer whole. Only the questions the document places on a reverse
    goal are read; with no document every carrier of the point is read."""
    by_point = _by_point(records)
    only = placed_on_reverse(doc, records)
    found = []
    for q in bank['questions']:
        mine = [p for p in q.get('point_ids', []) if p in by_point]
        if not mine or (only is not None and q['question_id'] not in only):
            continue
        stem = _norm(v3._front(q).get('question', ''))
        hit = None
        for p in mine:
            for rec in by_point[p]:
                whole = _norm(rec['answer'])
                if whole and whole in stem:
                    hit = rec['answer']
                    break
                hit = next((w for w in _names(rec['answer']) if _norm(w) in stem), None)
                if hit:
                    break
            if hit:
                break
        if hit:
            found.append({'question_id': q['question_id'], 'gave_away': hit})
    return found


def report(records, doc, bank):
    """R9 counts of one result. Three numbers that are easy to mistake for each other, so each says what it counts:

    - `reversible`: connections judged worth asking from the other end (one per judged goal).
    - `goalsMade` / `goalsWithTask`: the reverse **goals** those connections became, and how many got a question.
      Fewer than the connections, because normalize merges the ones that ask the same thing (261116_06: 19 points →
      14 goals). An earlier draft reported the connection count under the name 역방향 목표 and read 17 there, which
      is neither the goals made nor the goals asked (2026-11-16, 다른 세션이 짚었다).
    - `connectionsPlaced`: connections whose goal got a question — the connection-side view of the same fact.
    """
    owners_of = {d['direction_id']: t['target_id'] for t in doc['review']['targets'] for d in t['directions']}
    task_targets = {owners_of[t['direction_id']] for t in doc['tasks']}
    points = {p['point_id']: p['target_ids'] for p in doc['review']['points']}
    made = {t for r in records if r['point_id'] for t in points.get(r['point_id'], ())}
    asked = [r for r in records if r['asked_by']]
    goal = [r for r in records if r['point_id'] and set(points.get(r['point_id'], [])) & task_targets]
    open_ = [r for r in records if r['point_id'] and r not in goal]
    cues = sorted(len(r['cue']) for r in records if r['point_id'])
    return {'reversible': len(records), 'alreadyAsked': len(asked), 'goalsMade': len(made),
            'goalsWithTask': len(made & task_targets), 'connectionsPlaced': len(goal),
            'open': [r['answer'] for r in open_], 'answerInStem': answer_in_stem(doc, records, bank),
            # A distribution, not a limit: a cue that copies the whole forward answer turns the stem into 「list it
            # all and ask one thing」 (사용자 2026-11-16). The prompt asks for the narrowest clue; this shows whether
            # that held, and a long tail is a reason to look, not to fail a lecture.
            'cueLength': {'median': cues[len(cues) // 2] if cues else 0, 'max': max(cues, default=0),
                          'over60': sum(1 for n in cues if n > 60)}}

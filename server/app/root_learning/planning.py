"""Deterministic finite daily plans. No synthetic mastery or inferred prerequisites."""
from collections import defaultdict
from datetime import date, timedelta
from fractions import Fraction
from math import ceil
from statistics import median
from .policy import instant, study_day
from .state import targets, direction_owners, replay, replay_tasks, per_task


def existence_links(doc, records):
    """Question-level existence prerequisites from the presuppose/1 records of the generation that made `doc`
    (docs/changes/2026-11-18-existence-prereq-by-question R1): {question X: [questions Y]} where X's stem presupposes a
    link that Y recalls (`recalled_by`, or a question placed on the goal made from the record's point). A pair is kept only
    when (Y's goal, X's goal) is an existence edge of the document, so no edge the document left out (a cycle, the same
    goal) comes back. Questions not placed in the document are ignored."""
    from studyez_contracts.roots.presuppose import is_existence_edge
    owners = direction_owners(doc)
    placed = {t['question_id']: owners[t['direction_id']] for t in doc['tasks'] if t['direction_id'] in owners}
    on_target = defaultdict(list)
    for question_id, target_id in placed.items():
        on_target[target_id].append(question_id)
    existence = {(e['before_target'], e['after_target']) for e in doc['prerequisites'] if is_existence_edge(e)}
    point_targets = {p['point_id']: p.get('target_ids') or [] for p in doc['review'].get('points') or []}
    links = defaultdict(set)
    for record in records:
        after = placed.get(record['question_id'])
        if after is None:
            continue
        befores = {q for q in record.get('recalled_by') or [] if q in placed}
        if record.get('point_id'):
            befores |= {q for t in point_targets.get(record['point_id'], []) for q in on_target[t]}
        links[record['question_id']] |= {q for q in befores if (placed[q], after) in existence}
    return {q: sorted(ys) for q, ys in sorted(links.items()) if ys}


def plan(doc, events, available, now, policy, focus=None, new_goals=None, links=None, prereqs=True):
    """`focus`, a subset of `available`, narrows the candidates only (오늘 학습 중요도 필터). An unassessed question
    prerequisite of a planned task is brought forward by order_plan even outside the focus; one that is not available
    is passed over. A target prerequisite brings in (「명시적 선행 연결」) an existence goal from `available` and any other
    prior goal only from the candidates (inside the focus), and otherwise just orders. Without a focus every available task is a candidate
    (docs/changes/2026-11-12-plan-prereq-closure, 2026-11-16-prereq-question-only).
    With `links` (existence_links) an existence edge brings in, from `available`, only the questions that recall what a
    planned question presupposes, not its whole prior goal (docs/changes/2026-11-18-existence-prereq-by-question).

    오늘 학습 이어 풀기(docs/changes/2026-11-14-continuous-today): `new_goals` fixes the new-goal quota (capped by
    the prepared unseen goals) for a stream that 「더 풀기」 lengthened. Without it the quota is the former one.

    선행 문항 포함/미포함(docs/changes/2026-11-18-prereq-toggle): with `prereqs` false and a focus, prerequisites come in
    only from the focus. One outside it counts as not available: passed over, never holding back the task after it."""
    if per_task(doc):
        return plan_tasks(doc, events, available, now, policy, focus, new_goals, links, prereqs)
    pool = available if focus is None else focus
    reach = available if prereqs or focus is None else focus
    rows, states = replay(doc, events, now, policy)
    by_target = {r['id']: r for r in rows}
    owners = direction_owners(doc)
    target_list = targets(doc)
    order = {t['target_id']: i for i, t in enumerate(target_list)}
    authored = {t['target_id']: t for t in target_list}
    # One prepared task per direction. Optional directions do not replace required ones.
    candidates = {}
    for task in doc['tasks']:
        if task['task_id'] in pool:
            candidates.setdefault(task['direction_id'], task)
    today = study_day(now, policy)
    day = today  # 남은 일수도 학습일(새벽 4시)로 센다(2026-11-11 사용자 지시).
    deadline = date.fromisoformat(doc['exam_date']) - timedelta(days=policy['deadline_offset']) if doc['exam_date'] else None
    days = (deadline - day).days + 1 if deadline else None
    unseen = [t['target_id'] for t in target_list if not by_target[t['target_id']]['learned']
              and any(owners[d] == t['target_id'] for d in candidates)]
    quota = min(len(unseen), ceil(len(unseen) / days)) if days is not None and days > 0 else len(unseen)
    if new_goals is not None:
        quota = min(len(unseen), max(0, new_goals))
    def priority(tid):
        return (not by_target[tid]['important'], order[tid])
    unseen.sort(key=priority)
    selected = []
    def add(did, reason):
        task = candidates.get(did)
        if task and not any(x['task_id'] == task['task_id'] for x in selected):
            selected.append({**task, 'reason': reason})
    for tid in unseen[:quota]:
        for direction in authored[tid]['directions']:
            add(direction['direction_id'], '새 목표')
    due = [d for d in candidates if states.get(d, {}).get('rating') is not None and
           states[d]['effectiveDue'] <= today.isoformat()]
    # A same-day failure never expands this session, or immediately creates forced repeats.
    due = [d for d in due if study_day(instant(states[d]['lastAt']), policy) != today]
    due.sort(key=lambda d: (*priority(owners[d]), states[d]['effectiveDue'], d))
    for did in due:
        add(did, '복습 확인')
    # Incomplete learned goals retain all unassessed directions, including optional detail.
    for did in candidates:
        if by_target[owners[did]]['learned'] and not states.get(did, {}).get('rating') and states.get(did, {}).get('lastDay') != today:
            add(did, '미평가 방향')
    history = defaultdict(set)
    for event in events:
        if event['kind'] == 'reveal' and event['payload'].get('attempted'):
            when = study_day(instant(event['at']), policy)
            if when < today:
                history[when].add((event['revision'], event['payload']['task_id']))
    habitual = int(median([len(history[d]) for d in sorted(history)[-7:]])) if history else None
    for tid in unseen[quota:]:
        if habitual is None or len(selected) >= habitual:
            break
        for direction in authored[tid]['directions']:
            add(direction['direction_id'], '새 범위 보완')
    # Explicit prerequisite relations reorder already-selected tasks and may bring a prepared
    # prerequisite forward. Failure on it never locks the following direction.
    chosen_targets = {owners[t['direction_id']] for t in selected}
    prereqs = defaultdict(set)
    for edge in doc['prerequisites']:
        prereqs[edge['after_target']].add(edge['before_target'])
    expanded = set()
    def prerequisites(tid, visiting):
        if tid in visiting or tid in expanded:
            return
        for parent in sorted(prereqs[tid], key=lambda p: order[p]):
            prerequisites(parent, visiting | {tid})
            if not by_target[parent]['learned']:
                for direction in authored[parent]['directions']:
                    add(direction['direction_id'], '명시적 선행 연결')
        expanded.add(tid)
    for tid in sorted(chosen_targets, key=lambda t: order[t]):
        prerequisites(tid, set())
    emitted, result = set(), []
    def emit(tid):
        if tid in emitted:
            return
        emitted.add(tid)
        for parent in sorted(prereqs[tid], key=lambda p: order[p]):
            emit(parent)
        result.extend(t for t in selected if owners[t['direction_id']] == tid)
    for task in selected:
        emit(owners[task['direction_id']])
    if doc.get('generation_policy')=='root-generation/2':
        from studyez_contracts.roots.generation_v2 import order_plan
        assessed={t['question_id']for t in doc['tasks']if states.get(t['direction_id'],{}).get('rating')is not None}
        result=order_plan(doc,result,reach,assessed)
    return {'tasks': result, 'newGoalQuota': quota, 'days': days, 'habitualTasks': habitual,
            'deadline': deadline.isoformat() if deadline else None,
            'preparedUnseen': len(unseen), 'unpreparedGoals': sum(
                not any(owners[d] == t['target_id'] for d in candidates) for t in target_list),
            'scopeNote': '준비된 학습 범위 기준 · 앞으로 들어올 자료량 추정 없음'}


def _habitual(events, today, policy):
    history = defaultdict(set)
    for event in events:
        if event['kind'] == 'reveal' and event['payload'].get('attempted'):
            when = study_day(instant(event['at']), policy)
            if when < today:
                history[when].add((event['revision'], event['payload']['task_id']))
    return int(median([len(history[d]) for d in sorted(history)[-7:]])) if history else None


def spread_directions(tasks):
    """Tasks of one direction ask the same concept, from another side or in another form. They are not served
    back to back: every direction's first task comes in the given order, and its k-th of n tasks sits k/n of the
    way through what follows. A direction with many tasks is spread over the whole session and not left for the end
    (taking turns would serve the last tasks of the largest direction one after another).

    Only the order changes. With one task per direction it is the given order
    (docs/changes/2026-11-12-goal-dedupe: 261111_02 served one fact three times among its first five tasks)."""
    count = defaultdict(int)
    for task in tasks:
        count[task['direction_id']] += 1
    turn, ranked = defaultdict(int), []
    for index, task in enumerate(tasks):
        did = task['direction_id']
        ranked.append((Fraction(turn[did], count[did]), index, task))
        turn[did] += 1
    return [task for _, _, task in sorted(ranked, key=lambda row: row[:2])]


REVIEW_REASON = '복습 확인'
PULLED_REASON = '명시적 선행 연결'


def task_pages(doc):
    """The slide page of every task: its question's `learning_page`. A task without one (a personal question, an older
    import) takes the page of the task before it in the document, so it stays beside its neighbour (a personal
    question sits right after its anchor)."""
    pages = {q['question_id']: q.get('learning_page') for q in doc['bank_snapshot']['questions']}
    out, last = {}, 0
    for task in doc['tasks']:
        page = pages.get(task['question_id'])
        if type(page) is int:
            last = page
        out[task['task_id']] = last
    return out


def slide_flow(doc, selected, edges, existence, links, owner):
    """The order of today's tasks (docs/changes/2026-11-26-slide-flow-order, 사용자 2026-11-26 「슬라이드 흐름으로」).

    New learning comes first and in slide order (the question's page, then the document's task order); reviews follow,
    also in slide order. Importance chooses what is in today's list (above) and never orders it. Only an explicit
    prerequisite moves a task: an existence question goes right before the first question that presupposes it (with
    `links`, question by question; without, goal by goal), a reverse goal after its forward goal, and any other target
    prerequisite before its goal. A task that comes first only as a prerequisite takes the place of the earliest task
    that needs it. Two tasks of one direction on the same page are not served back to back when another task of that
    page can go between them (a personal question stays right after its anchor)."""
    import heapq
    # 내 문제(mine.with_mine)는 기준 과제와 같은 방향·task_id == question_id로 붙는다. mine을 import하면 DB 설정을 읽는다.
    is_mine = lambda task: task['task_id'] == task['question_id']
    page = task_pages(doc)
    position = {t['task_id']: i for i, t in enumerate(doc['tasks'])}
    by_id = {t['task_id']: t for t in selected}
    by_question = {t['question_id']: t['task_id'] for t in selected}
    by_target = defaultdict(list)
    for task in selected:
        by_target[owner(task)].append(task['task_id'])
    later = defaultdict(set)
    for after_target, befores in edges.items():
        for before_target in befores:
            if (before_target, after_target) in existence and links is not None:
                continue  # 문항 단위로 아래에서
            for a in by_target.get(after_target, ()):
                for b in by_target.get(before_target, ()):
                    if a != b:
                        later[b].add(a)
    if links is not None:
        for task in selected:
            for question_id in links.get(task['question_id'], ()):
                before = by_question.get(question_id)
                if before is not None and before != task['task_id']:
                    later[before].add(task['task_id'])

    def block(task):
        return {PULLED_REASON: 2, REVIEW_REASON: 1}.get(task['reason'], 0)
    own = {i: (block(t), page[i], position[i]) for i, t in by_id.items()}
    key, visiting = {}, set()

    def earliest(i):
        if i in key:
            return key[i]
        visiting.add(i)
        best = own[i]
        for a in later[i]:
            if a not in visiting:
                best = min(best, earliest(a))
        visiting.discard(i)
        key[i] = best
        return best
    for i in by_id:
        earliest(i)
    waiting = {i: 0 for i in by_id}
    for b in later:
        for a in later[b]:
            waiting[a] += 1
    ready = [(key[i], own[i], i) for i in by_id if waiting[i] == 0]
    heapq.heapify(ready)
    result, done, last = [], set(), None
    while len(result) < len(by_id):
        if not ready:
            # a cycle the document checks should have refused: serve the earliest left, never fail the plan
            i = min((i for i in by_id if i not in done), key=lambda i: (key[i], own[i], i))
            ready = [(key[i], own[i], i)]
        item = heapq.heappop(ready)
        i = item[2]
        if last is not None and by_id[i]['direction_id'] == last and not is_mine(by_id[i]):
            same = [r for r in ready if r[0][:2] == item[0][:2] and by_id[r[2]]['direction_id'] != last]
            if same:
                other = min(same)
                ready.remove(other)
                heapq.heapify(ready)
                heapq.heappush(ready, item)
                i = other[2]
        done.add(i)
        result.append(by_id[i])
        last = by_id[i]['direction_id']
        for a in later[i]:
            waiting[a] -= 1
            if waiting[a] == 0 and a not in done:
                heapq.heappush(ready, (key[a], own[a], a))
    return result


def plan_tasks(doc, events, available, now, policy, focus=None, new_goals=None, links=None, prereqs=True):
    """root-generation/4 (spec R8 option B): every prepared task is a candidate, not one per direction.

    Same rules as plan() with the learner state of each task: new goals by the target quota (unchanged,
    target-based), due tasks, unassessed tasks of learned goals, history fill and explicit prerequisites.
    Importance (a target's exam/clinical evidence) chooses which new goals come in today; the order of what comes in
    is the slide flow (slide_flow, docs/changes/2026-11-26-slide-flow-order). Until then the important goals came
    first as one block and the document's goal grouping held, so a goal with only structural evidence (피부근염
    「IIM의 세 가지 범주」) waited behind every important one."""
    rows, _, states = replay_tasks(doc, events, now, policy)
    by_target = {r['id']: r for r in rows}
    owners = direction_owners(doc)
    target_list = targets(doc)
    order = {t['target_id']: i for i, t in enumerate(target_list)}
    authored = {t['target_id']: t for t in target_list}
    position = {t['task_id']: i for i, t in enumerate(doc['tasks'])}
    pool = available if focus is None else focus
    # 선행을 끌어올 범위(2026-11-18-prereq-toggle): 끄면 필터 안에서만.
    reach = available if prereqs or focus is None else focus
    candidates = [t for t in doc['tasks'] if t['task_id'] in pool and t['direction_id'] in owners]
    by_direction = defaultdict(list)
    for task in candidates:
        by_direction[task['direction_id']].append(task)
    owner = lambda task: owners[task['direction_id']]
    today = study_day(now, policy)
    day = today  # 남은 일수도 학습일(새벽 4시)로 센다(2026-11-11 사용자 지시).
    deadline = date.fromisoformat(doc['exam_date']) - timedelta(days=policy['deadline_offset']) if doc['exam_date'] else None
    days = (deadline - day).days + 1 if deadline else None
    prepared = {owner(t) for t in candidates}
    unseen = [t['target_id'] for t in target_list if not by_target[t['target_id']]['learned'] and t['target_id'] in prepared]
    quota = min(len(unseen), ceil(len(unseen) / days)) if days is not None and days > 0 else len(unseen)
    if new_goals is not None:
        quota = min(len(unseen), max(0, new_goals))
    def priority(tid):
        # Which goals come in today when not all fit (사용자 2026-11-26 「오늘 범위 고르기에만」): the important ones first,
        # and with them the skeleton — a goal with structural evidence, which the others stand on (피부근염 「정의와
        # 아형」 had only that and never came in first). It never orders today's list (slide_flow does).
        axes = authored[tid].get('importance') or {}
        skeleton = (axes.get('structural') or {}).get('status') == 'supported'
        return (not (by_target[tid]['important'] or skeleton), order[tid])
    unseen.sort(key=priority)
    selected, chosen = [], set()
    def add(task, reason):
        if task['task_id'] not in chosen:
            chosen.add(task['task_id'])
            selected.append({**task, 'reason': reason})
    def add_target(tid, reason, tasks=by_direction):
        for direction in authored[tid]['directions']:
            for task in tasks[direction['direction_id']]:
                add(task, reason)
    # 존재 목표(presuppose/1)는 중요도 필터 밖에 있어도 끌어온다(tree-edge-goals spec R2). 그래서 끌어올 과제는 pool이 아니라
    # available에서 찾는다. 지도 관계에서 온 목표 선행은 필터 안(pool)에서만 끌어온다 — 앞 목표 전체가 뒤 목표 전체의 선행이라
    # 261109_02에서 Essential만 고른 목록에 35과제가 끌려왔다(docs/changes/2026-11-16-prereq-question-only).
    from studyez_contracts.roots.presuppose import is_existence_edge
    existence = {(e['before_target'], e['after_target']) for e in doc['prerequisites'] if is_existence_edge(e)}
    prepared_tasks = defaultdict(list)
    for task in doc['tasks']:
        if task['task_id'] in reach and task['direction_id'] in owners:
            prepared_tasks[task['direction_id']].append(task)
    target_tasks = defaultdict(list)
    for task in doc['tasks']:
        if task['direction_id'] in owners:
            target_tasks[owners[task['direction_id']]].append(task['task_id'])
    def pull(parent):
        """복습에서 선행 목표를 세부 목표에 묶어 끌어올지(docs/changes/2026-11-15-tree-edge-goals spec R2).
        안 배웠으면 끌어온다. 배웠으면 평가한 과제가 모두 independent(쉽게 맞힘)일 때 풀어 준다.
        오늘 이미 푼 선행은 다시 끌어오지 않는다(같은 날 실패로 세션을 늘리지 않는 규칙과 같다)."""
        if not by_target[parent]['learned']:
            return True
        values = [states.get(task_id, {}) for task_id in target_tasks[parent]]
        if any(v.get('lastDay') == today for v in values):
            return False
        rated = [v['rating'] for v in values if v.get('rating') is not None]
        return not rated or any(r != 'independent' for r in rated)
    for tid in unseen[:quota]:
        add_target(tid, '새 목표')
    due = [t for t in candidates if states.get(t['task_id'], {}).get('rating') is not None and
           states[t['task_id']]['effectiveDue'] <= today.isoformat()]
    # A same-day failure never expands this session, or immediately creates forced repeats.
    due = [t for t in due if study_day(instant(states[t['task_id']]['lastAt']), policy) != today]
    due.sort(key=lambda t: (*priority(owner(t)), states[t['task_id']]['effectiveDue'], position[t['task_id']]))
    for task in due:
        add(task, '복습 확인')
    # Incomplete learned goals retain every unassessed task, including optional detail.
    for task in candidates:
        value = states.get(task['task_id'], {})
        if by_target[owner(task)]['learned'] and not value.get('rating') and value.get('lastDay') != today:
            add(task, '미평가 과제')
    habitual = _habitual(events, today, policy)
    for tid in unseen[quota:]:
        if habitual is None or len(selected) >= habitual:
            break
        add_target(tid, '새 범위 보완')
    # Explicit target prerequisites reorder already-selected tasks and bring a prepared prior goal forward: an
    # existence goal from every prepared task (with `links`: only the questions a planned question presupposes, below),
    # another target only from today's candidates. Question prerequisites come in by order_plan. Failure on one never
    # locks the following direction.
    prereqs = defaultdict(set)
    for edge in doc['prerequisites']:
        prereqs[edge['after_target']].add(edge['before_target'])
    expanded = set()
    def prerequisites(tid, visiting):
        if tid in visiting or tid in expanded:
            return
        for parent in sorted(prereqs[tid], key=lambda p: order[p]):
            prerequisites(parent, visiting | {tid})
            if (parent, tid) in existence and links is not None:
                continue  # 문항 단위로 아래에서 끌어온다
            if pull(parent):
                add_target(parent, '명시적 선행 연결', prepared_tasks if (parent, tid) in existence else by_direction)
        expanded.add(tid)
    # 존재 목표 선행을 문항 단위로(docs/changes/2026-11-18-existence-prereq-by-question R2): 오늘 고른 문항이 전제하는 연결을
    # 답하는 문항만 필터 밖에서도 끌어온다. 261110_02에서 존재 목표 T020 전체가 끌려와, 어느 문항의 전제도 아닌 Optional Q107이 나왔다.
    by_question = {t['question_id']: t for ts in prepared_tasks.values() for t in ts}
    def wanted(task_id):
        value = states.get(task_id, {})
        return value.get('lastDay') != today and value.get('rating') != 'independent'
    done = 0
    while True:
        for tid in sorted({owner(t) for t in selected}, key=lambda t: order[t]):
            prerequisites(tid, set())
        if links is None:
            break
        while done < len(selected):
            task = selected[done]
            done += 1
            for question_id in links.get(task['question_id'], ()):
                before = by_question.get(question_id)
                if before is not None and wanted(before['task_id']):
                    add(before, '명시적 선행 연결')
        if all(owner(t) in expanded for t in selected):
            break
    result = slide_flow(doc, selected, prereqs, existence, links, owner)
    from studyez_contracts.roots.generation_v2 import order_plan
    assessed = {t['question_id'] for t in doc['tasks'] if states.get(t['task_id'], {}).get('rating') is not None}
    # With `links` the existence edges were ordered question by question above; order_plan would put the whole prior
    # goal back in front (피부근염: 26쪽 「진단 후 평가할 동반질환」 before 7쪽, for an Optional 7쪽 question not in
    # today's list). It still adds question prerequisites and keeps the other target edges.
    ordering = {**doc, 'prerequisites': [e for e in doc['prerequisites'] if not is_existence_edge(e)]} if links is not None else doc
    result = order_plan(ordering, result, reach, assessed)
    return {'tasks': result, 'newGoalQuota': quota, 'days': days, 'habitualTasks': habitual,
            'deadline': deadline.isoformat() if deadline else None,
            'preparedUnseen': len(unseen), 'unpreparedGoals': sum(t['target_id'] not in prepared for t in target_list),
            'scopeNote': '준비된 학습 범위 기준 · 앞으로 들어올 자료량 추정 없음'}


def shuffled(tasks, seed):
    """사진 반입 판의 「랜덤」 순서(docs/changes/2026-11-15-photo-quiz-shuffle). 같은 seed·같은 과제 묶음이면 넣은 순서와
    상관없이 늘 같은 순서다 — 칩을 바꿔 뒷부분을 다시 골라도 출렁이지 않는다. 선행 연결이 없는 판(사진 반입)에만 쓴다."""
    import hashlib
    return sorted(tasks, key=lambda t: hashlib.sha256(f"{seed}\0{t['task_id']}".encode()).hexdigest())

"""모아풀기 시작 화면 선택지(docs/changes/2026-11-18-mix-options).

강의 하나의 과제를 강의 목록 칸과 같은 단위로 「미열람·복습 대상·나중」으로 나누고(R1), 고른 중요도와 두 체크
(기존 학습률 무시·미열람 문항 보기)로 모아풀기 회차의 과제를 고른다(R2). 순서는 판 문서의 과제 순서 또는
선행 문항을 지키는 무작위 순서다(R4). 기록·복습일 계산은 바꾸지 않는다 — 읽기만 한다."""
import hashlib
from .policy import TIERS, instant, study_day
from datetime import date
from .state import _mastery_now, direction_owners, per_task, replay, replay_tasks

KINDS = ('unseen', 'due', 'later')
TOUCHED = ('reveal', 'rate', 'skip')


def units(doc, available):
    """강의 목록 칸과 같은 단위(state.question_progress): /4 판은 준비된 과제마다, 그 전 판은 방향마다 첫 과제."""
    owners = direction_owners(doc)
    tasks = [t for t in doc['tasks'] if t['task_id'] in available and t['direction_id'] in owners]
    if per_task(doc):
        return tasks
    served = {}
    for task in tasks:
        served.setdefault(task['direction_id'], task)
    return list(served.values())


def classify(doc, events, available, now, policy):
    """task_id → 'unseen' | 'due' | 'later'. 급함 값까지 필요하면 `classify_urgency`."""
    return classify_urgency(doc, events, available, now, policy)[0]


def urgency_of(value, today, now):
    """복습 주기 이전 문항의 급함(2026-11-19-mix-urgency-order). 작을수록 급하다.
    복습일까지 남은 날(오늘 이전이면 0) + 지금 기억 확률(0–1): 복습일이 이른 것, 같으면 더 잊었을 것이 먼저."""
    due = value.get('effectiveDue')
    days = max(0, (date.fromisoformat(due) - today).days) if due else 0
    return days + min(max(_mastery_now(value, now), 0.0), 0.999)


def classify_urgency(doc, events, available, now, policy):
    """(task_id → 'unseen' | 'due' | 'later', 「나중」 task_id → 급함 값).

    - unseen: 시도·평가 기록 없음(강의 목록 「미열람」).
    - due: 평가했고 복습일(effectiveDue)이 오늘 이전이며 오늘 평가하지 않았다(오늘 추천 「복습 확인」),
      또는 시도했지만 평가가 없고 오늘 건드리지 않았다(오늘 추천 「미평가 과제」).
    - later: 나머지 본 과제."""
    today = study_day(now, policy)
    if per_task(doc):
        _, _, values = replay_tasks(doc, events, now, policy)
        value_of = lambda task: values.get(task['task_id'], {})
    else:
        _, values = replay(doc, events, now, policy)
        value_of = lambda task: values.get(task['direction_id'], {})
    # 오늘 답을 보거나 넘긴 과제(평가 전): 오늘 추천처럼 다시 내지 않는다.
    today_events = [e for e in events if e['kind'] in TOUCHED and e['revision'] == doc['revision']
                    and study_day(instant(e['at']), policy) == today]
    touched_tasks = {e['payload'].get('task_id') for e in today_events}
    touched_directions = {e['payload'].get('direction_id') for e in today_events}
    out, urgency = {}, {}
    for task in units(doc, available):
        value = value_of(task)
        urgency[task['task_id']] = urgency_of(value, today, now)
        if not value.get('learned') and value.get('rating') is None:
            out[task['task_id']] = 'unseen'
        elif value.get('rating') is not None:
            due = (value.get('effectiveDue') and value['effectiveDue'] <= today.isoformat()
                   and not (value.get('lastAt') and study_day(instant(value['lastAt']), policy) == today))
            out[task['task_id']] = 'due' if due else 'later'
        else:
            touched = task['task_id'] in touched_tasks or (not per_task(doc) and task['direction_id'] in touched_directions)
            out[task['task_id']] = 'later' if touched or value.get('lastDay') == today.isoformat() else 'due'
    return out, {t: u for t, u in urgency.items() if out.get(t) == 'later'}


def counts(classes, tiers):
    """중요도마다 {unseen, due, later}. 웹이 칩·체크를 바꿀 때 서버를 다시 부르지 않고 합한다(R5)."""
    out = {tier: dict.fromkeys(KINDS, 0) for tier in TIERS}
    for task_id, kind in classes.items():
        out[tiers.get(task_id, 'Core')][kind] += 1
    return out


def select(doc, classes, tiers, chosen, unseen, ignore_schedule, prereqs=False, links=None):
    """고른 중요도 ∩ (복습 대상 ∪ 나중(기존 학습률 무시) ∪ 미열람(미열람 문항 보기)). 판 문서의 과제 순서.

    선행 문항 포함(2026-11-18-prereq-toggle): 고른 과제의 문항 선행과 존재 연결(`links`, 문항 → 전제를 답하는 문항)을
    따라가며, 미열람·복습 대상인 과제를 중요도·체크와 상관없이 더한다. 「나중」(이미 익힌 것)은 더하지 않는다."""
    kinds = {'due'} | ({'later'} if ignore_schedule else set()) | ({'unseen'} if unseen else set())
    chosen = set(chosen)
    picked = {t['task_id'] for t in doc['tasks'] if classes.get(t['task_id']) in kinds and tiers.get(t['task_id'], 'Core') in chosen}
    if prereqs and picked:
        picked |= _prerequisites(doc, classes, picked, links or {})
    return [t for t in doc['tasks'] if t['task_id'] in picked]


def _prerequisites(doc, classes, picked, links):
    """고른 과제에서 거슬러 올라가 닿는, 아직 익히지 않은(미열람·복습 대상) 선행 과제."""
    deps = _question_dependencies(doc)
    by_question = {}
    for task in doc['tasks']:
        if task['task_id'] in classes:
            by_question.setdefault(task['question_id'], task['task_id'])
    question_of = {t['task_id']: t['question_id'] for t in doc['tasks']}
    out, stack = set(), list(picked)
    while stack:
        task_id = stack.pop()
        before = list(deps.get(task_id, [])) + [by_question[q] for q in links.get(question_of.get(task_id), ()) if q in by_question]
        for pre in before:
            if pre not in picked and pre not in out and classes.get(pre) in ('unseen', 'due'):
                out.add(pre)
                stack.append(pre)
    return out


def _question_dependencies(doc):
    try:
        from studyez_contracts.roots.generation_v2 import question_dependencies
        return question_dependencies(doc)
    except Exception:
        # 문항 선행을 적지 않은 옛 판: 지킬 순서가 없다.
        return {}


GROUPS = {'due': 0, 'unseen': 1, 'later': 2}


def arrange(doc, tasks, classes, urgency, order, seed):
    """모아풀기 회차의 과제 순서와 묶음(2026-11-19-mix-urgency-order R2).

    ① 복습 대상 ② 미열람: 순서대로 = 판 순서, 섞어서 = seed 무작위(선행 지킴). ③ 나중(복습 주기 이전): 급한 순.
    함께 골린 선행 문항은 묶음을 넘어서도 뒤 문항보다 앞이다. 앞으로 끌려온 선행은 그 자리의 묶음으로 센다(뒤에서부터 가장 이른 묶음).
    반환: (과제 목록, {'due': ①칸 수, 'unseen': ②칸 수, 'urgency': ③칸마다 급함 값})."""
    position = {t['task_id']: i for i, t in enumerate(doc['tasks'])}
    group = lambda t: GROUPS.get(classes.get(t['task_id']), 0)
    parts = [[t for t in tasks if group(t) == g] for g in range(3)]
    for g in (0, 1):
        parts[g] = shuffled(doc, parts[g], seed) if order == 'random' else sorted(parts[g], key=lambda t: position.get(t['task_id'], 0))
    parts[2] = sorted(parts[2], key=lambda t: (urgency.get(t['task_id'], 0), position.get(t['task_id'], 0)))
    listed = _prerequisites_first(doc, [t for part in parts for t in part])
    groups = [group(t) for t in listed]
    phase, lowest = [0] * len(listed), 2
    for i in range(len(listed) - 1, -1, -1):
        lowest = min(lowest, groups[i])
        phase[i] = lowest
    return listed, {'due': phase.count(0), 'unseen': phase.count(1),
                    'urgency': [round(urgency.get(t['task_id'], 0), 6) for t, p in zip(listed, phase) if p == 2]}


def _prerequisites_first(doc, tasks):
    """주어진 순서를 지키되, 함께 골린 선행 문항은 그 문항을 전제로 한 문항 앞에 둔다."""
    deps = _question_dependencies(doc)
    chosen = {t['task_id']: t for t in tasks}
    done, visiting, result = set(), set(), []

    def emit(task_id):
        if task_id in done or task_id in visiting:
            return
        visiting.add(task_id)
        for before in deps.get(task_id, []):
            if before in chosen:
                emit(before)
        visiting.discard(task_id)
        done.add(task_id)
        result.append(chosen[task_id])
    for task in tasks:
        emit(task['task_id'])
    return result


def shuffled(doc, tasks, seed):
    """강의 안 무작위 순서(R4). seed가 같으면 같은 순서. 선행 문항이 함께 골렸으면 그 문항이 뒤 문항보다 앞이다.
    목표 사이 선행(지도 관계)은 지키지 않는다 — 지키면 목표 순서 그대로라 섞이지 않는다."""
    key = lambda t: hashlib.sha256(f"{seed}\0{t['task_id']}".encode()).hexdigest()
    order = sorted(tasks, key=key)
    deps = _question_dependencies(doc)
    chosen = {t['task_id']: t for t in tasks}
    done, visiting, result = set(), set(), []

    def emit(task_id):
        if task_id in done or task_id in visiting:
            return
        visiting.add(task_id)
        for before in sorted((d for d in deps.get(task_id, []) if d in chosen), key=lambda d: key(chosen[d])):
            emit(before)
        visiting.discard(task_id)
        done.add(task_id)
        result.append(chosen[task_id])
    for task in order:
        emit(task['task_id'])
    return result

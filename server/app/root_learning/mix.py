"""모아풀기 시작 화면 선택지(docs/changes/2026-11-18-mix-options).

강의 하나의 과제를 강의 목록 칸과 같은 단위로 「미열람·복습 대상·나중」으로 나누고(R1), 고른 중요도와 두 체크
(기존 학습률 무시·미열람 문항 보기)로 모아풀기 회차의 과제를 고른다(R2). 순서는 판 문서의 과제 순서 또는
선행 문항을 지키는 무작위 순서다(R4). 기록·복습일 계산은 바꾸지 않는다 — 읽기만 한다."""
import hashlib
from .policy import TIERS, instant, study_day
from .state import direction_owners, per_task, replay, replay_tasks

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
    """task_id → 'unseen' | 'due' | 'later'.

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
    out = {}
    for task in units(doc, available):
        value = value_of(task)
        if not value.get('learned') and value.get('rating') is None:
            out[task['task_id']] = 'unseen'
        elif value.get('rating') is not None:
            due = (value.get('effectiveDue') and value['effectiveDue'] <= today.isoformat()
                   and not (value.get('lastAt') and study_day(instant(value['lastAt']), policy) == today))
            out[task['task_id']] = 'due' if due else 'later'
        else:
            touched = task['task_id'] in touched_tasks or (not per_task(doc) and task['direction_id'] in touched_directions)
            out[task['task_id']] = 'later' if touched or value.get('lastDay') == today.isoformat() else 'due'
    return out


def counts(classes, tiers):
    """중요도마다 {unseen, due, later}. 웹이 칩·체크를 바꿀 때 서버를 다시 부르지 않고 합한다(R5)."""
    out = {tier: dict.fromkeys(KINDS, 0) for tier in TIERS}
    for task_id, kind in classes.items():
        out[tiers.get(task_id, 'Core')][kind] += 1
    return out


def select(doc, classes, tiers, chosen, unseen, ignore_schedule):
    """고른 중요도 ∩ (복습 대상 ∪ 나중(기존 학습률 무시) ∪ 미열람(미열람 문항 보기)). 판 문서의 과제 순서."""
    kinds = {'due'} | ({'later'} if ignore_schedule else set()) | ({'unseen'} if unseen else set())
    chosen = set(chosen)
    return [t for t in doc['tasks'] if classes.get(t['task_id']) in kinds and tiers.get(t['task_id'], 'Core') in chosen]


def _question_dependencies(doc):
    try:
        from studyez_contracts.roots.generation_v2 import question_dependencies
        return question_dependencies(doc)
    except Exception:
        # 문항 선행을 적지 않은 옛 판: 지킬 순서가 없다.
        return {}


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

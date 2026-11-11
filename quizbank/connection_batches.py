"""Item review/fix batches of root-generation /3 and /4 side by side (docs/changes/2026-11-11-root-batch-parallel).

261102_02 (2026-11-10) spent about 50 of its 80 model minutes on four review/fix batches run one after another,
though no conflict record or prerequisite link joined two of them. Each batch now starts from the same snapshot
of the run, reads its own copy of the material and runs the unchanged loop (review → fix → re-review → revert →
coverage re-check, at most FIX_LIMIT fixes per question). The batches are merged in batch order, so the result
and the ledger do not depend on which batch finished first, and a resumed run finds each completed stage with the
same input.

A run whose batches share a conflict record or a prerequisite link, a run of one batch, and a ledger made before
this change (no `batchMode`) run the batches one after another on one shared state, exactly as before.
"""
import copy
import filecmp
import os
import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

BATCH_MODE = 'parallel/1'
# Model calls of one run side by side. Three was the first, untested ceiling ("the runner already runs three
# Codex sessions at once"): a lecture of 200+ questions has six review batches, so they ran in two waves and the
# second wave waited 13-19 minutes for the first (run 6e5c581a, 2026-11-11). Six covers such a lecture in one wave;
# the machine-wide ceiling for every process is studyez_llm.execution.slot (STUDYEZ_CODEX_SLOTS, 8).
WORKERS_ENV = 'STUDYEZ_ROOT_WORKERS'


def _workers(default=6):
    try:
        return min(12, max(1, int(os.environ.get(WORKERS_ENV) or default)))
    except ValueError:
        return default


BATCH_WORKERS = _workers()
CONFLICT_PREFIX = 'CF-B{n}-'


def parallel_calls(calls, workers=None):
    """Run the thunks side by side. Every one runs to its end, so completed stages are kept for a resume; the
    results come back in call order and the first failure in call order is raised."""
    workers = BATCH_WORKERS if workers is None else workers
    if len(calls) <= 1 or workers <= 1:
        return [c() for c in calls]
    with ThreadPoolExecutor(max_workers=min(workers, len(calls))) as pool:
        futures = [pool.submit(c) for c in calls]
    for f in futures:
        if f.exception() is not None:
            raise f.exception()
    return [f.result() for f in futures]


def judgments(st, calls):
    """Independent judgment stages `(name, ctx, accept)`: side by side in a new run, in order otherwise.
    The ledger lists them in call order either way."""
    if not st.parallel:
        return [st.judged(*c) for c in calls]
    try:
        return parallel_calls([lambda c=c: st.judged(*c) for c in calls])
    finally:
        st.canonical([c[0] for c in calls])


class Batch:
    """The run's values one batch reads and changes. In the one-after-another order all batches share one."""

    FIELDS = ('bank', 'conflicts', 'stimuli', 'basis', 'rows', 'reviews', 'fixes', 'attempts', 'restated', 'verdicts')

    def __init__(self, **values):
        self.__dict__.update({k: None for k in self.FIELDS})
        self.material, self.scope, self.stages, self.coverage = None, None, [], []
        self.__dict__.update(values)

    def copy(self):
        return Batch(**{k: copy.deepcopy(getattr(self, k)) for k in self.FIELDS})


class BatchStages:
    """The run's Stages for one batch: its own material copy, and a record of the stage names it called."""

    def __init__(self, st, batch):
        self.st, self.batch = st, batch

    def __getattr__(self, name):
        return getattr(self.st, name)

    def run(self, name, ctx, accept, state=None):
        self.batch.stages.append(name)
        return self.st.run(name, ctx, accept, state, material=self.batch.material)

    def judged(self, name, ctx, accept):
        self.batch.stages.append(name)
        return self.st.judged(name, ctx, accept, material=self.batch.material)


def coupling(bank, batches):
    """Why these batches cannot start from one snapshot: a conflict record or a prerequisite link between two."""
    where = {q: b for b, batch in enumerate(batches) for q in batch}
    cites = {}
    for q in bank['questions']:
        if q.get('conflict_id') and q['question_id'] in where:
            cites.setdefault(q['conflict_id'], set()).add(where[q['question_id']])
    reasons = []
    shared = sorted(c for c, owners in cites.items() if len(owners) > 1)
    if shared:
        reasons.append('여러 묶음의 문항이 함께 인용하는 충돌: ' + ', '.join(shared))
    links = [f"{q['question_id']}→{p}" for q in bank['questions'] if q['question_id'] in where
             for p in q.get('prerequisites', []) if p in where and where[p] != where[q['question_id']]]
    if links:
        reasons.append('묶음을 넘는 선행 연결: ' + ', '.join(links[:20]) + (f' 외 {len(links) - 20}개' if len(links) > 20 else ''))
    return reasons


def _record(st, phase, row):
    with st.lock:
        rows = [r for r in st.ledger.setdefault('batchPhases', []) if r['phase'] != phase]
        st.ledger['batchPhases'] = [*rows, {'phase': phase, **row}]
        st.save()


def review_phase(st, out, batches, state, body, apply_coverage, phase='item-review'):
    """Run `body(b, batch, S, stages)` for every batch and return the run's values after all of them.

    `state` holds the run's values at the phase start (Batch). In the one-after-another order it is changed in
    place and returned; side by side every batch gets a copy and the copies are merged in batch order.
    `apply_coverage(rows, got_rows, judged_ids)` re-applies one coverage re-check (connection_generate_v3/_v4
    `_merge_row`) on the merged coverage rows."""
    out = Path(out)
    state.material, state.scope = out / 'material', None
    if not st.parallel:
        mode, reasons = 'sequential', []
    elif len(batches) < 2:
        mode, reasons = 'single', []
    else:
        reasons = coupling(state.bank, batches)
        mode = 'sequential' if reasons else 'parallel'
    if st.parallel:
        _record(st, phase, {'mode': mode, 'batches': len(batches), 'reasons': reasons})
    if mode != 'parallel':
        for b, batch in enumerate(batches):
            body(b, batch, state, BatchStages(st, state))
        return state

    known = sorted({c['conflict_id'] for c in [*state.bank.get('source_conflicts', []), *state.conflicts]})
    copies = []
    for b, batch in enumerate(batches):
        mine = state.copy()
        mine.material = out / '.batches' / str(b) / 'material'
        shutil.copytree(out / 'material', mine.material, dirs_exist_ok=True)
        own = sorted({q['conflict_id'] for q in state.bank['questions'] if q['question_id'] in set(batch) and q.get('conflict_id')})
        mine.scope = {'new_conflict_id_prefix': CONFLICT_PREFIX.format(n=b + 1), 'own_conflict_ids': own,
                      'known_conflict_ids': known}
        copies.append(mine)
    try:
        parallel_calls([lambda b=b, mine=mine: body(b, batches[b], mine, BatchStages(st, mine)) for b, mine in enumerate(copies)])
    finally:
        st.canonical([n for mine in copies for n in mine.stages])
    return merge(st, out, state, batches, copies, apply_coverage)


def merge(st, out, snapshot, batches, copies, apply_coverage):
    """The batches' changes on the snapshot, in batch order: what the one-after-another order leaves when no
    record joins two batches."""
    result = Batch(**{k: getattr(snapshot, k) for k in Batch.FIELDS})
    result.material, result.scope = Path(out) / 'material', None
    ids = [q['question_id'] for q in snapshot.bank['questions']]

    # questions, source conflicts, other bank fields --------------------------------------------------------
    bank = copy.deepcopy(snapshot.bank)
    replaced = {}
    base_sources = snapshot.bank.get('source_conflicts', [])
    new_sources = []
    for mine, batch in zip(copies, batches):
        _require([q['question_id'] for q in mine.bank['questions']] == ids, '묶음이 문항 목록을 바꿨습니다')
        _require(all(mine.bank[k] == snapshot.bank[k] for k in snapshot.bank if k not in ('questions', 'source_conflicts')),
                 '묶음이 문항·충돌 밖의 은행 내용을 바꿨습니다')
        _require(mine.bank.get('source_conflicts', [])[:len(base_sources)] == base_sources, '묶음이 기존 원본 충돌을 바꿨습니다')
        by_id = {q['question_id']: q for q in mine.bank['questions']}
        replaced.update({q: by_id[q] for q in batch})
        new_sources.extend(mine.bank.get('source_conflicts', [])[len(base_sources):])
    _require(len({c['conflict_id'] for c in new_sources}) == len(new_sources), '두 묶음이 같은 새 충돌 ID를 썼습니다')
    bank['questions'] = [replaced.get(q['question_id'], q) for q in bank['questions']]
    if new_sources or 'source_conflicts' in bank:
        bank['source_conflicts'] = [*copy.deepcopy(base_sources), *copy.deepcopy(new_sources)]
    result.bank = bank

    # clinical facts ---------------------------------------------------------------------------------------
    base = {c['conflict_id']: c for c in snapshot.conflicts}
    changed, added = {}, []
    for mine in copies:
        facts = {c['conflict_id']: c for c in mine.conflicts}
        _require(set(base) <= set(facts), '묶음이 기존 임상 사실을 지웠습니다')
        for cid, c in facts.items():
            if cid in base and c != base[cid]:
                _require(cid not in changed, '두 묶음이 같은 충돌의 임상 사실을 고쳤습니다: ' + cid)
                changed[cid] = c
            elif cid not in base:
                added.append(c)
    _require(len({c['conflict_id'] for c in added}) == len(added), '두 묶음이 같은 새 충돌 ID를 썼습니다')
    result.conflicts = [*[copy.deepcopy(changed.get(c['conflict_id'], c)) for c in snapshot.conflicts], *copy.deepcopy(added)]

    # images: a question's images are the snapshot's unless its batch changed them ----------------------------
    def of(entries, q):
        return [s for s in entries if s['question_id'] == q]
    moved = []
    gone = set()
    for mine, batch in zip(copies, batches):
        mine_changed = {q for q in batch if of(mine.stimuli, q) != of(snapshot.stimuli, q)}
        gone |= mine_changed
        moved.extend(s for s in mine.stimuli if s['question_id'] in mine_changed)
    result.stimuli = [*[s for s in snapshot.stimuli if s['question_id'] not in gone], *moved]

    # per-question records ------------------------------------------------------------------------------------
    if snapshot.basis is not None:
        result.basis = dict(snapshot.basis)
        for mine, batch in zip(copies, batches):
            result.basis.update({q: mine.basis[q] for q in batch if q in mine.basis})
    result.reviews = dict(snapshot.reviews)
    result.attempts = dict(snapshot.attempts)
    result.fixes = list(snapshot.fixes)
    result.restated = list(snapshot.restated)
    for mine, batch in zip(copies, batches):
        result.reviews.update({q: mine.reviews[q] for q in mine.reviews if q in set(batch)})
        result.attempts.update({q: v for q, v in mine.attempts.items() if q not in snapshot.attempts})
        result.fixes.extend(mine.fixes[len(snapshot.fixes):])
        result.restated.extend(mine.restated[len(snapshot.restated):])

    # coverage re-checks, in batch order ---------------------------------------------------------------------
    result.rows = copy.deepcopy(snapshot.rows)
    result.coverage = []
    for b, mine in enumerate(copies):
        for got_rows, judged_ids, goal_ids in mine.coverage:
            apply_coverage(result.rows, got_rows, judged_ids)
            result.coverage.append((b, got_rows, judged_ids, goal_ids))

    # ledger: verdicts and fix attempts in batch order, the batches' image copies in the run's material ---------
    with st.lock:
        ledger = st.ledger
        verdicts = snapshot.verdicts
        start = len(verdicts)
        for mine in copies:
            for entry in mine.verdicts[start:]:
                if entry not in verdicts:
                    verdicts.append(entry)
        result.verdicts = verdicts
        order = [q for mine in copies for q in mine.attempts if q not in snapshot.attempts]
        attempts = ledger['fixAttempts']
        ledger['fixAttempts'] = {**{q: v for q, v in attempts.items() if q not in set(order)}, **{q: attempts[q] for q in order if q in attempts}}
        st.save()
    shared = Path(out) / 'material'
    for mine in copies:
        for path in sorted(Path(mine.material).rglob('*')):
            if path.is_file():
                target = shared / path.relative_to(mine.material)
                if target.exists():
                    _require(filecmp.cmp(path, target, shallow=False), '묶음의 자료 사본이 원래 자료와 다릅니다: ' + target.name)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(path, target)
    return result


def stale_coverage(result, batches, snapshot):
    """/4: goals a batch re-judged with a duplicate partner from another batch that the other batch then changed.
    Returns (goal_ids, judged_ids) for one more coverage judgment on the merged bank, or None."""
    where = {q: b for b, batch in enumerate(batches) for q in batch}
    before = {q['question_id']: q for q in snapshot.bank['questions']}
    after = {q['question_id']: q for q in result.bank['questions']}
    changed = {q for q in after if after[q] != before[q]}
    goals, judged = set(), set()
    for b, _, judged_ids, goal_ids in result.coverage:
        if any(where.get(q) not in (None, b) and q in changed for q in judged_ids):
            goals |= set(goal_ids)
            judged |= set(judged_ids)
    if not goals:
        return None
    order = [q['question_id'] for q in result.bank['questions']]
    return sorted(goals), [q for q in order if q in judged]


def _require(ok, message):
    if not ok:
        raise ValueError(message)

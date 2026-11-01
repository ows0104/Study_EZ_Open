"""Read multi-lecture batch states without controlling their workers."""
from pathlib import Path

from .status import JobStatus
from .status_external import _local, _read, _script_arg

DONE = {'applied', 'no-change'}
WAITING = {'queued', 'waiting-existing-job', 'waiting-approval'}
ATTENTION = {'failed', 'held-limit', 'waiting-usage'}


def collect_batches(runs: Path, processes: list[dict]):
    root = runs.resolve().parent
    boards, jobs = [], []
    for manifest in sorted((runs / 'status-jobs').glob('*.json'))[:32]:
        config = _read(manifest)
        if config.get('overview') is not True:
            continue
        try:
            state = _read(_local(root, config['state_file']))
            script = _local(root, config['script']).relative_to(root).as_posix()
            _local(root, config['outputs'])
            states = state['states']
            if not isinstance(states, dict):
                continue
        except (KeyError, TypeError, ValueError):
            continue
        live = any(p['ProcessId'] == state.get('pid') and
                   _script_arg(p.get('CommandLine') or '', script)[0] for p in processes)
        groups = {name: [] for name in ('done', 'active', 'pending', 'attention')}
        for rid, row in states.items():
            row_live, row_pid = live, state.get('pid')
            if config.get('recovery_script'):
                try:
                    recovery = _read(_local(root, str(Path(config['outputs']) / rid / 'recovery-state.json')))
                    recovery_script = _local(root, config['recovery_script']).relative_to(root).as_posix()
                    recovering = any(p['ProcessId'] == recovery.get('pid') and
                                     _script_arg(p.get('CommandLine') or '', recovery_script)[0] for p in processes)
                    if recovery and (recovering or recovery.get('stage') in ATTENTION):
                        row = dict(row, **{k:v for k,v in recovery.items() if k != 'pid'})
                        row_live, row_pid = recovering, recovery.get('pid')
                except (KeyError, TypeError, ValueError):
                    pass
            if config.get('completion_file'):
                try:
                    marker = _read(_local(root, str(Path(config['outputs']) / rid / config['completion_file'])))
                    if marker.get('publishedVerified') is True and marker.get('runId') == rid:
                        row = dict(row, stage='applied', added=marker.get('addedCount'), removed=marker.get('removedCount'))
                except (KeyError, TypeError, ValueError):
                    pass
            stage = row.get('stage', 'queued')
            dispatch = _read(_local(root, str(Path(config['outputs']) / rid / 'author-1/started.json')))
            held_dispatch = _read(_local(root, str(Path(config['outputs']) / rid / 'author-1/dispatch-hold.json')))
            handoff_wait = (stage == 'failed' and 'This attempt already started' in row.get('error','') and
                            (dispatch.get('dispatchHold') is True or held_dispatch.get('dispatchHold') is True))
            if handoff_wait:
                stage = 'queued'
            group = ('done' if stage in DONE else 'pending' if stage in WAITING else
                     'attention' if stage in ATTENTION or not row_live else 'active')
            label = config.get('stages', {}).get(stage, stage)
            if handoff_wait:
                label = '수정된 처리로 전환 대기'
            if group == 'attention' and stage not in ATTENTION:
                label += ' · 실행 프로세스 없음'
            item = dict(runId=rid, title=row.get('title') or config.get('targets', {}).get(rid, rid),
                        stage=label, error=row.get('error', ''), added=row.get('added'), removed=row.get('removed'))
            groups[group].append(item)
            if group == 'active':
                jobs.append(JobStatus(f"{config['id']}/{rid}", item['title'], row_pid,
                                      config.get('label', config['id']), (label,), (), None,
                                      config.get('owner', '일괄 작업')))
        boards.append(dict(label=config.get('label', config['id']), **groups))
    return tuple(boards), tuple(jobs)


def overview(snapshot):
    groups = {key: [] for key in ('done', 'active', 'pending', 'attention', 'other')}
    for board in snapshot.batches:
        for key in groups:
            for row in board.get(key, []):
                text = row['title'] + ' · ' + row['stage']
                if key == 'done' and row.get('added') is not None:
                    added, removed = row['added'], row.get('removed') or 0
                    text += f" · 추가 {len(added) if isinstance(added, list) else added} / 제외 {len(removed) if isinstance(removed, list) else removed}"
                groups[key].append(text)
    server = snapshot.queue or {}
    groups['pending'] += [r.get('title', r['runId']) for r in server.get('waiting', [])]
    groups['other'] += [r.get('title', r['runId']) + ' · ' + (r.get('message') or r.get('stage') or '보류')
                            for r in server.get('held', [])]
    # Running cards already contain both local and server workers.
    groups['active'] = [j.title + ' · ' + (j.stages[-1] if j.stages else j.kind) for j in snapshot.jobs]
    return groups

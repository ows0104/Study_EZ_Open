"""Follow an existing runner in the launch console without starting another worker."""
from __future__ import annotations

import argparse
import time
from pathlib import Path

from . import status


def render(snapshot: status.Snapshot) -> list[str]:
    if snapshot.error:
        return [snapshot.error]
    if not snapshot.agent_pid:
        return ['실행 중인 러너를 확인하지 못했습니다.']
    lines = [f'러너 PID {snapshot.agent_pid} · 실행 작업 {len(snapshot.jobs)}개']
    for job in snapshot.jobs:
        stage = job.stages[-1] if job.stages else '첫 단계 출력 대기'
        lines.append(f'  {job.title} ({job.run_id}) — {stage} · 프로세스 실행 중')
        lines.extend(f'    {line}' for line in job.lines[-2:])
    if not snapshot.jobs:
        lines.append('  작업 대기 또는 자료 동기화 중')
    return lines


def follow(runs: Path, interval: float = 20) -> int:
    print('기존 러너의 로그를 이 창에서 표시합니다. Ctrl+C는 표시만 종료합니다.', flush=True)
    previous: tuple[str, ...] = ()
    try:
        while True:
            snapshot = status.collect(runs)
            print(f'\n[{time.strftime("%H:%M:%S")}] ' + '\n'.join(render(snapshot)), flush=True)
            events = snapshot.events
            overlap = 0
            for count in range(min(len(previous), len(events)), 0, -1):
                if previous[-count:] == events[:count]:
                    overlap = count
                    break
            for line in events[overlap:]:
                print(line, flush=True)
            previous = events
            if not snapshot.error and not snapshot.agent_pid:
                return 0
            time.sleep(interval)
    except KeyboardInterrupt:
        return 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runs', type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(follow(args.runs))

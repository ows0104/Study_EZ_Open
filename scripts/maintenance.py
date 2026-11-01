"""Observe public StudyEZ endpoints; open deduplicated development records, never deploy."""
from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import development
import workflow_lifecycle

ROOT = Path(__file__).resolve().parents[1]


def observe(probe):
    request = urllib.request.Request(probe['url'], headers={'User-Agent': 'StudyEZ-maintenance/1'})
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            body = response.read(65536)
            if response.status != 200:
                return {'status': 'failed', 'reason': f'http_{response.status}'}
            if probe['kind'] == 'api':
                try:
                    valid = json.loads(body).get('status') == 'ok'
                except (ValueError, AttributeError):
                    valid = False
            else:
                valid = b'<html' in body.lower() and b'<script' in body.lower()
            return {'status': 'healthy' if valid else 'failed',
                    'reason': 'ok' if valid else 'unexpected_response'}
    except urllib.error.HTTPError as error:
        return {'status': 'failed', 'reason': f'http_{error.code}'}
    except (urllib.error.URLError, TimeoutError, OSError):
        # A failed observation does not prove that the service itself is down.
        return {'status': 'unknown', 'reason': 'observation_failed'}


def reconcile(state, probe, result, at, threshold, create_incident):
    previous = state.setdefault(probe['id'], {'failures': 0, 'incident': None, 'episode': 0})
    events = []
    previous['observed_at'] = at
    previous['status'] = result['status']
    previous['reason'] = result['reason']
    if result['status'] == 'healthy':
        previous['last_success'] = at
        previous['failures'] = 0
        if previous['incident']:
            events.append({'type': 'recovered', 'probe': probe['id'], 'change': previous['incident']})
            previous['last_incident'] = previous['incident']
            previous['incident'] = None
    else:
        previous['failures'] += 1
        if previous['failures'] >= threshold and not previous['incident']:
            previous['episode'] += 1
            change_id = create_incident(probe, result, at, previous['episode'])
            previous['incident'] = change_id
            events.append({'type': 'investigate', 'probe': probe['id'], 'change': change_id,
                           'status': result['status'], 'reason': result['reason']})
    return events


def incident(probe, result, at, episode):
    change_id = f'incident-{probe["id"]}-{at[:10]}-{episode}'
    folder = development.change_dir(change_id)
    if not folder.exists():
        development.create(change_id, f'StudyEZ {probe["id"]} 관측 이상', 'operations', ['regression'])
    elif (folder / 'incident.json').exists():
        # A crash before monitor state persistence must not overwrite human analysis.
        return change_id
    # Observation facts are data, never a source of implementation approval.
    evidence = {'observed_at': at, 'probe': probe['id'], 'url': probe['url'], **result}
    (folder / 'incident.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding='utf-8')
    (folder / 'intent.md').write_text(
        f'# StudyEZ {probe["id"]} 관측 이상\n\n'
        f'- 관측: {at}\n- 상태: {result["status"]}\n- 분류: {result["reason"]}\n'
        '- 목적: 같은 관측을 재현하고 서비스 장애와 관측 환경 실패를 구분한다.\n'
        '- 근거: incident.json. HTTP 본문·인증값·개인정보는 수집하지 않는다.\n'
        '- 범위: 읽기 전용 진단과 spec/plan 작성. 구현·배포 승인 없음.\n'
        '- 성공 기준: 원인과 영향 범위, 재현 검사, 수정 제안 또는 복구 증거를 기록한다.\n', encoding='utf-8')
    workflow_lifecycle.observe(change_id, 'investigating', f'{result["status"]}: {result["reason"]}', at)
    return change_id


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=ROOT / 'docs/development/monitor.json')
    args = parser.parse_args(argv)
    config = json.loads(args.config.read_text(encoding='utf-8'))
    folder = ROOT / 'runs/_maintenance'
    folder.mkdir(parents=True, exist_ok=True)
    lock = folder / 'monitor.lock'
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        print(json.dumps({'status': 'busy', 'events': [], 'reason': 'monitor_lock_present'}))
        return 2
    os.close(fd)
    try:
        path = folder / 'state.json'
        state = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
        at = datetime.now(UTC).isoformat()
        events = []
        observations = []
        for probe in config['probes']:
            result = observe(probe)
            observations.append({'id': probe['id'], **result})
            events.extend(reconcile(state, probe, result, at, config['consecutive_failures'], incident))
        # Persist recovery before clearing the monitor pointer; idempotent on retry after a crash.
        for event in events:
            if event['type'] == 'recovered':
                workflow_lifecycle.observe(event['change'], 'recovered', 'Public probe returned healthy', at)
        temp = path.with_suffix('.tmp')
        temp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
        temp.replace(path)
        print(json.dumps({'observed_at': at, 'observations': observations, 'events': events}, ensure_ascii=False))
        return 0 if all(row['status'] == 'healthy' for row in observations) else 1
    finally:
        lock.unlink()


if __name__ == '__main__':
    raise SystemExit(main())

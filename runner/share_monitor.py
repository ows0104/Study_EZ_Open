"""Keep the pharmacology production checklist verified using public HTTP only."""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
import hashlib
import json
import time
from pathlib import Path
from . import cycle, publish, shared_bank


def inspect_source(row):
    payload = {'runId': row['runId'], 'shareUrl': row['shareUrl'], 'state': 'unsupported'}
    try:
        raw, source = shared_bank.fetch_source(row['shareUrl'], row['runId'])
        dates = [t.created_at for t in source.turns if t.role == 'assistant' and shared_bank.COMPLETE in t.text and t.created_at]
        if not dates:
            return payload
        return {**payload, 'state': 'complete', 'questionCount': len(shared_bank.question_ids(raw)),
                'completedAt': datetime.fromtimestamp(max(dates), UTC).isoformat(),
                'rawHash': hashlib.sha256(raw.encode()).hexdigest()}
    except ValueError as error:
        payload['state'] = 'wrong_lecture' if '강의 ID' in str(error) else 'incomplete' if '완료 표식' in str(error) else 'unsupported'
    except (SystemExit, OSError, TimeoutError):
        payload['state'] = 'unavailable'
    return payload


def sync(client, *, force=False, report=print):
    data = client.call('GET', '/api/admin/quiz-publication/sources')
    now = datetime.now(UTC)
    wanted = []
    for row in data['lectures']:
        if row.get('responseSource') in ('manual', 'file'):
            continue
        checked = row['link'].get('checkedAt')
        if row['shareUrl'] and (force or not checked or (now - datetime.fromisoformat(checked)).total_seconds() >= 300):
            wanted.append(row)
    results = []
    with ThreadPoolExecutor(max_workers=3) as pool:
        for future in as_completed([pool.submit(inspect_source, row) for row in wanted]):
            result = future.result()
            try:
                client.call('PUT', '/api/admin/quiz-publication/check', result)
                results.append(result)
                if report:
                    report(json.dumps({k: result[k] for k in ('runId', 'state', 'questionCount', 'completedAt') if k in result}, ensure_ascii=False), flush=True)
            except publish.PublishError as error:
                if report:
                    report(f"공유 확인 저장 보류: {result['runId']} · {str(error).split(' — ')[0]}", flush=True)
    return results


def watch(client, stop):
    while not stop.is_set():
        try:
            sync(client, report=None)
        except (publish.PublishError, OSError):
            pass
        stop.wait(30)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--once', action='store_true')
    parser.add_argument('--force', action='store_true')
    parser.add_argument('--api', default=publish.DEFAULT_API_BASE)
    parser.add_argument('--state', type=Path, default=Path('runs/share-monitor.json'))
    args = parser.parse_args()
    client = publish.Client(args.api, cycle.runner_token(None))
    while True:
        try:
            results = sync(client, force=args.force)
            args.state.parent.mkdir(parents=True, exist_ok=True)
            args.state.write_text(json.dumps({'checkedAt': datetime.now(UTC).isoformat(), 'checked': len(results)}, ensure_ascii=False), encoding='utf-8')
        except (publish.PublishError, OSError) as error:
            print(f'공유 확인 재시도 대기: {type(error).__name__}', flush=True)
        if args.once:
            break
        time.sleep(30)


if __name__ == '__main__':
    main()

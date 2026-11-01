"""Durable change/incident lifecycle; never edits feedback content or grants approval."""
import argparse
import json
import re

import development as dev


def observe(change, status, evidence, at=None):
    folder, _ = dev.load(change)
    if status not in ('investigating', 'recovered'):
        raise ValueError('Unknown observation transition')
    def record(s):
        life = s.setdefault('lifecycle', {'status': 'investigating', 'events': [], 'links': []})
        key = f'{change}:{status}'
        if any(e.get('key') == key for e in life.setdefault('events', [])):
            return
        life['observation'] = status
        if status == 'investigating' and life['status'] == 'planning':
            life['status'] = 'investigating'
        life['events'].append({'key': key, 'at': at or dev.now(), 'type': status, 'evidence': evidence})
    dev.update(folder, record)


def link(change, related=None, feedback=None, fingerprint=None):
    folder, _ = dev.load(change)
    if related:
        if related == change:
            return
        other, _ = dev.load(related)
        for target, value in ((folder, related), (other, change)):
            def add(s):
                life = s.setdefault('lifecycle', {'status': 'planning', 'events': [], 'links': []})
                if value not in life['links']: life['links'].append(value)
            dev.update(target, add)
    elif feedback and re.fullmatch(r'(site|bank):\d+', feedback) and fingerprint:
        ref = {'id': feedback, 'fingerprint': fingerprint}
        def add(s):
            refs = s.setdefault('feedback_refs', [])
            if ref not in refs: refs.append(ref)
        dev.update(folder, add)
    else:
        raise ValueError('Use an existing related change, or feedback ID plus its current fingerprint')


def transition(change, status, evidence, fix=None):
    if not evidence.strip(): raise ValueError('Evidence is required')
    folder, state = dev.load(change)
    if status not in ('investigating', 'awaiting_approval', 'implementing', 'verified', 'completed_local', 'resolved'):
        raise ValueError('Unsupported lifecycle status')
    if status in ('implementing', 'verified', 'completed_local'):
        errors = dev.gate(folder, state, 'build' if status == 'implementing' else 'release')
        if errors: raise ValueError('; '.join(errors))
    resolution = None
    if status == 'resolved':
        if fix:
            _, fixed = dev.load(fix)
            deployments = fixed.get('deployments', [])
            if not deployments:
                raise ValueError('Fix has no deployment receipt')
            a = deployments[-1]
            posts = a.get('postchecks', [])
            if (a['status'] != 'succeeded' or not posts or not posts[-1]['passed']
                    or posts[-1]['revision'] != a['revision'] or posts[-1]['candidate'] != a['candidate']['id']):
                raise ValueError('Latest deployment needs successful current postchecks')
            resolution = {'kind': 'deployed_fix', 'change': fix, 'attempt': a['id'],
                          'candidate': a['candidate']['id'], 'revision': a['revision']}
            link(change, related=fix)
        elif state.get('lifecycle', {}).get('observation') == 'recovered':
            resolution = {'kind': 'observation_only', 'note': 'Recovery does not prove code was fixed or deployed'}
        else:
            raise ValueError('Need recovery evidence or a verified deployed fix')
    def record(s):
        life = s.setdefault('lifecycle', {'status': 'planning', 'events': [], 'links': []})
        life['status'] = status
        life.setdefault('events', []).append({'at': dev.now(), 'type': status, 'evidence': evidence,
                                              'resolution': resolution})
        if resolution: life['resolution'] = resolution
    dev.update(folder, record)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='action', required=True)
    t = sub.add_parser('transition'); t.add_argument('id'); t.add_argument('--status', required=True)
    t.add_argument('--evidence', required=True); t.add_argument('--fix-change')
    l = sub.add_parser('link'); l.add_argument('id'); l.add_argument('--related-id')
    l.add_argument('--feedback-id'); l.add_argument('--fingerprint')
    a = p.parse_args(argv)
    if a.action == 'transition': transition(a.id, a.status, a.evidence, a.fix_change)
    else: link(a.id, a.related_id, a.feedback_id, a.fingerprint)
    print(json.dumps(dev.load(a.id)[1].get('lifecycle'), ensure_ascii=False))


if __name__ == '__main__':
    try: main()
    except (ValueError, OSError) as e: raise SystemExit(str(e))

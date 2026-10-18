"""Stateless, authenticated prepared draws; preparation never writes study history."""

import base64
import hashlib
import hmac
import json

from .policy import DEFAULT, policy_hash
from .study_day import day_start


def context(entries: list[dict], now: int) -> str:
    facts = []
    for entry in entries:
        state = entry['state']
        session = state.get('session') or {}
        facts.append([entry['key'], entry['row'].build_id, entry['bank'], entry['exam'],
                      [[h['question_id'], h['rating'], day_start(h['timestamp'])] for h in state.get('history', [])],
                      state.get('question_tiers', {}), sorted(state.get('suspended_question_ids', [])),
                      state.get('choice_variants', {}), session.get('status'), session.get('continue_after_goal', False)])
    data = json.dumps([day_start(now), policy_hash(DEFAULT), facts], sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(data.encode()).hexdigest()


def seal(secret: str, user: str, parent: str, rating: str, fingerprint: str, scope: tuple, question: str) -> str:
    data = json.dumps([user, parent, rating, fingerprint, list(scope), question], separators=(',', ':')).encode()
    encoded = base64.urlsafe_b64encode(data).decode().rstrip('=')
    signature = hmac.new(secret.encode(), ('studyez-prepared-v1:' + encoded).encode(), hashlib.sha256).hexdigest()
    return encoded + '.' + signature


def open_draw(ticket: str | None, secret: str, user: str, parent: str, rating: str, fingerprint: str) -> tuple | None:
    if not ticket or not secret:
        return None
    try:
        encoded, signature = ticket.split('.')
        expected = hmac.new(secret.encode(), ('studyez-prepared-v1:' + encoded).encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return None
        owner, token, grade, saved_context, scope, question = json.loads(base64.urlsafe_b64decode(encoded + '=' * (-len(encoded) % 4)))
        if (owner, token, grade, saved_context) != (user, parent, rating, fingerprint):
            return None
        if not isinstance(scope, list) or len(scope) != 2 or not all(isinstance(x, str) for x in [*scope, question]):
            return None
        return tuple(scope), question
    except (ValueError, TypeError, UnicodeDecodeError):
        return None

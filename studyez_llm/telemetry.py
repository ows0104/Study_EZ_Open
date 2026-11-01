"""Per-call counters, including failures; never store prompt or response text."""
from datetime import UTC, datetime
import json
from uuid import uuid4
from .execution import usage_root


def record(*, status, model, label, cwd, prompt, stdout='', seconds=0, usage=None, session_id=None):
    now = datetime.now(UTC)
    row = {'at': now.isoformat(), 'status': status, 'model': model, 'label': label,
           'cwd': str(cwd or ''), 'promptCharacters': len(prompt),
           'responseStreamCharacters': len(stdout or ''), 'seconds': round(seconds, 2),
           'sessionId': session_id, 'usage': usage, 'partialUsageUnknown': usage is None}
    # Successful completion counters are reliable; failed partial turns can cost
    # tokens even when the CLI did not emit a final usage event.
    path = usage_root() / now.strftime('%Y%m%d') / (uuid4().hex + '.json')
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(row, ensure_ascii=False, indent=2), encoding='utf-8')
    except OSError:
        # Observability must never destroy an otherwise completed author/review.
        return None
    return path

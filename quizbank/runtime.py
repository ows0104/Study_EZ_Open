"""Record the actual CLI checkout and common prompt, independently of its caller's cwd."""
from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = ('quizbank/run.py', 'quizbank/question_first.py', 'quizbank/organize.py',
         'quizbank/repair.py', 'server/app/bank_validation/validate.py')


def record(out: Path, phase: str) -> None:
    if phase not in ('started', 'finished', 'failed'):
        raise ValueError('Unknown runtime phase')
    prompt = ROOT / 'web/src/bank/bankPrompt.md'
    data = prompt.read_bytes() if prompt.is_file() else b''
    version = re.search(r'^Version:\s*(\S+)', data.decode('utf-8')[:4096], re.M)
    snapshot = {'checkedAt': datetime.now(UTC).isoformat(), 'sourceRoot': str(ROOT),
        'pythonExecutable': sys.executable, 'commonPromptVersion': version[1] if version else 'unknown',
        'commonPromptSha256': hashlib.sha256(data).hexdigest(),
        'codeSha256': {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                       for name in FILES if (ROOT / name).is_file()}}
    out.mkdir(parents=True, exist_ok=True)
    path = out / 'runtime.json'
    envelope = json.loads(path.read_text(encoding='utf-8')) if phase != 'started' and path.is_file() else {}
    envelope[phase] = snapshot
    if phase != 'started' and envelope.get('started'):
        envelope['contractUnchanged'] = all(envelope['started'][key] == snapshot[key]
            for key in ('sourceRoot', 'commonPromptSha256', 'codeSha256'))
    path.write_text(json.dumps(envelope, ensure_ascii=False, indent=2), encoding='utf-8')

"""Explicit component inputs. Runtime/user data and secrets are never source evidence."""
import hashlib
import os

COMMON = ('.github', 'scripts', 'tests/development', 'pyproject.toml', 'requirements.txt', 'uv.lock')
GROUPS = {
    'site': ('web', 'server', 'studyez_contracts', 'content', 'bridge', 'platform', 'data/timetable', 'tests/contracts', 'tests/bridge'),
    'generation': ('quizbank', 'quizgen', 'studyez_llm', 'studyez_contracts', 'content', 'tests/quizbank', 'tests/quizgen', 'tests/contracts'),
    'integration': ('runner', 'bridge', 'quizbank', 'quizgen', 'studyez_llm', 'studyez_contracts', 'content', 'platform', 'data/timetable', 'tests/runner', 'tests/bridge', 'tests/contracts'),
    'spotter': ('spotter/scripts', 'spotter/web', 'spotter/data', 'server', 'platform', 'studyez_contracts', 'tests/spotter', 'tests/contracts'),
}
EXCLUDED = {'node_modules', '.venv', '__pycache__', 'dist', 'local_test_data', 'release', '.pytest_cache', '.ruff_cache', 'build', '.git'}


def paths(area='operations'):
    groups = GROUPS.values() if area in ('operations', 'contracts') else [GROUPS[area]]
    return sorted(set(COMMON).union(*(set(g) for g in groups)))


def files(root, area='operations'):
    found = set()
    for name in paths(area):
        base = root / name
        if base.is_file():
            found.add(base)
        elif base.is_dir():
            for current, dirs, names in os.walk(base, followlinks=False):
                from pathlib import Path
                current = Path(current)
                dirs[:] = [d for d in dirs if d not in EXCLUDED and not d.endswith('.egg-info')
                           and not (current / d).is_symlink() and not (current / d).is_junction()]
                for n in names:
                    p = current / n
                    if (not n.startswith('.env') and n not in {'bank-prompt.json', 'studyez-extension.zip'}
                            and p.suffix not in {'.pyc', '.pyo', '.tsbuildinfo'} and not p.is_symlink()):
                        found.add(p)
    return sorted(found)


def fingerprint(root, area='operations'):
    result = hashlib.sha256()
    for p in files(root, area):
        result.update(p.relative_to(root).as_posix().encode() + b'\0' + p.read_bytes() + b'\0')
    return result.hexdigest()

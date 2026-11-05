"""Run revision-bound checks for professor-aware preview notes in isolated storage."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'out' / 'professor-tests'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('group', choices=['professor-selection', 'contracts', 'runner', 'server', 'web', 'browser'])
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, 'PYTHONIOENCODING': 'utf-8', 'TEMP': str(OUT), 'TMP': str(OUT),
           'ENVIRONMENT': 'local-test', 'DATABASE_URL': 'sqlite:///' + (OUT / 'isolated.db').as_posix(),
           'STUDYEZ_LOCAL_STORAGE_DIR': str(OUT / 'storage')}
    python = str(ROOT / '.venv/Scripts/python.exe')
    server_python = str(ROOT / 'server/.venv/Scripts/python.exe')
    group = args.group
    commands = []
    if group in ('professor-selection', 'contracts', 'runner'):
        tests = 'tests/runner/test_preview_sources.py' if group == 'professor-selection' else 'tests/' + group
        groups = [[tests]]
        if group == 'runner':
            # Tcl's process-global state survives root-window destruction. Keep both
            # GUI files, but run each in a fresh interpreter as in production CI.
            gui = ['tests/runner/test_desktop_window.py', 'tests/runner/test_status_window.py']
            groups = [[tests, *['--ignore=' + name for name in gui]], *[[name] for name in gui]]
        commands = [(ROOT, [python, '-m', 'pytest', *names, '-q', '--tb=short',
                            '--basetemp=' + str(OUT / f'{group}-{time.time_ns()}-{i}')])
                    for i, names in enumerate(groups)]
    elif group == 'server':
        # The root uv launcher exports its own standard-library location. The server
        # uses another Python distribution and must resolve its own standard library.
        env.pop('PYTHONHOME', None)
        commands = [(ROOT / 'server', [server_python, '-m', 'tests', pattern]) for pattern in
                    ['preview_sources', 'matching', 'route_contract', 'immunity_timetable',
                     'smoke', 'shared_preview_prompt', 'study_retention']]
    elif group == 'web':
        npm = shutil.which('npm.cmd') or shutil.which('npm')
        if not npm:
            raise SystemExit('npm not installed')
        commands = [(ROOT, [npm, '--prefix', 'web', 'run', name]) for name in ['typecheck', 'build']]
    else:
        node = shutil.which('node')
        if not node:
            raise SystemExit('node not installed')
        env['PROFESSOR_SCREENSHOTS'] = str(OUT / 'browser')
        # The bundled runtime is optional; callers can supply their own module path.
        bundled = Path.home() / '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'
        if bundled.is_dir():
            env.setdefault('PLAYWRIGHT_MODULE', str(bundled))
        commands = [(ROOT, [node, 'web/tests/run-professor-preview.cjs', '--all'])]
    failed = []
    for cwd, command in commands:
        print('CHECK', group, command, flush=True)
        code = subprocess.run(command, cwd=cwd, env=env, shell=False).returncode
        if code:
            failed.append(code)
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())

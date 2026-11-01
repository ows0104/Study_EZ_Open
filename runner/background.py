"""Start a local command without a console; keep output in an append-only log."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path


def launch(command: list[str], *, cwd: Path, log: Path) -> subprocess.Popen:
    log.parent.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    with log.open("ab", buffering=0) as sink:
        return subprocess.Popen(command, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                                stdout=sink, stderr=subprocess.STDOUT, close_fds=True,
                                creationflags=flags, start_new_session=os.name != "nt")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cwd", type=Path, required=True)
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        parser.error("-- 뒤에 실행할 명령을 지정하세요")
    process = launch(command, cwd=args.cwd.resolve(), log=args.log.resolve())
    print(json.dumps({"pid": process.pid, "log": str(args.log.resolve())}))


if __name__ == "__main__":
    main()

"""Forward progress explicitly across Windows console-free subprocesses."""
from __future__ import annotations

import subprocess
import sys


def _output():
    for stream in (sys.stdout, sys.__stdout__):
        try:
            if stream is not None and stream.fileno() >= 0:
                return stream
        except (OSError, ValueError):
            pass
    return subprocess.DEVNULL


def run_forwarded(argv, **kwargs):
    # CREATE_NO_WINDOW does not reliably inherit unspecified standard handles.
    # Set all three so nested quizbank progress reaches the agent's existing log.
    kwargs.setdefault("stdin", subprocess.DEVNULL)
    kwargs.setdefault("stdout", _output())
    kwargs.setdefault("stderr", subprocess.STDOUT)
    kwargs.setdefault("creationflags", getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return subprocess.run(argv, **kwargs)

"""Main-Quiz phases and time-based remaining estimates for the status window.

Read-only: looks at file names and modification times under runs/_root-generation.
A phase only moves forward. Durations come from earlier local runs; with no sample
for a phase we return no number rather than invent one.
"""
from __future__ import annotations

import re
import statistics
from dataclasses import dataclass
from pathlib import Path

PHASES = ('지도·포인트', '커버 확인', '추가 출제', '검토·수정', '의학 검토', '게시')
SAMPLE_RUNS = 12


def phase_of(relative: str) -> int | None:
    """Phase index for one file path relative to a generation folder."""
    path = relative.replace('\\', '/')
    name = path.rsplit('/', 1)[-1]
    if path.startswith('front/'):
        return 0
    if path == 'published.json' or path == 'generation/result.json':
        return 5
    if not path.startswith('generation/') or path.count('/') != 1:
        return None
    stem = name.removesuffix('.json')
    if stem == 'normalize':
        return 1
    if re.match(r'medical-\d', stem) or re.match(r'v\d-context-\d', stem):
        return 4
    if re.match(r'v\d-(review|fix|coverage-fix)-', stem):
        return 3
    if re.match(r'v\d-add-\d', stem):
        return 2
    if re.match(r'v\d-(brief-fix|coverage|map-check|supplement)', stem):
        return 1
    return None


def starts(folder: Path, since: float = 0.0) -> dict[int, float]:
    """First time each phase began in one run. Files older than `since` are a resumed run's past."""
    first: dict[int, float] = {}
    try:
        files = [p for p in folder.rglob('*.json') if p.is_file()]
    except OSError:
        return {}
    for path in files:
        relative = path.relative_to(folder).as_posix()
        if relative.endswith('.input.json'):
            # A stage's input is written when it starts; use it as that stage's start.
            relative = relative.removesuffix('.input.json') + '.json'
        elif relative.endswith(('.raw.json', '.usage.json')):
            continue
        index = phase_of(relative)
        if index is None:
            continue
        try:
            stamp = path.stat().st_mtime
        except OSError:
            continue
        if stamp < since:
            continue
        first[index] = min(first.get(index, stamp), stamp)
    # Phases only move forward: a later phase cannot start before an earlier one.
    ordered: dict[int, float] = {}
    floor = 0.0
    for index in sorted(first):
        floor = max(floor, first[index])
        ordered[index] = floor
    return ordered


def durations(root: Path, exclude: set[str] = frozenset()) -> dict[int, float]:
    """Median seconds per phase over recent runs where the next phase also began."""
    try:
        folders = sorted((p for p in root.iterdir() if p.is_dir() and p.name not in exclude),
                         key=lambda p: p.stat().st_mtime, reverse=True)[:SAMPLE_RUNS]
    except OSError:
        return {}
    samples: dict[int, list[float]] = {}
    for folder in folders:
        begun = starts(folder)
        for index, start in begun.items():
            if index == 5:
                published, result = folder / 'published.json', folder / 'generation/result.json'
                if published.is_file() and result.is_file():
                    end = published.stat().st_mtime
                else:
                    continue
            elif index + 1 in begun:
                end = begun[index + 1]
            else:
                continue
            # A phase that took more than three hours was a resume after a stop, not a run.
            if 0 <= end - start <= 3 * 3600:
                samples.setdefault(index, []).append(end - start)
    return {index: statistics.median(values) for index, values in samples.items()}


@dataclass(frozen=True)
class Progress:
    phase: int                 # current phase index
    in_phase: float            # seconds spent in the current phase
    remaining: float | None    # seconds left, None when any phase lacks a sample
    overrun: bool              # current phase is past its usual length


def progress(folder: Path, started_at: float, now: float, typical: dict[int, float]) -> Progress | None:
    begun = starts(folder, since=started_at - 60)
    if not begun:
        # Nothing written yet in this job: still at the start of the first phase.
        begun = {0: started_at}
    phase = max(begun)
    phase_start = max(begun[phase], started_at)
    in_phase = max(0.0, now - phase_start)
    if any(index not in typical for index in range(phase, len(PHASES))):
        return Progress(phase, in_phase, None, False)
    usual = typical[phase]
    later = sum(typical[index] for index in range(phase + 1, len(PHASES)))
    return Progress(phase, in_phase, max(0.0, usual - in_phase) + later, in_phase > usual)


def fraction(elapsed: float, remaining: float | None, overrun: bool) -> float | None:
    """Share of time used. Never full while still running."""
    if remaining is None:
        return None
    total = elapsed + remaining
    value = elapsed / total if total > 0 else 0.0
    return min(value, 0.97 if overrun or remaining < 60 else 0.99)


def phase_line(phase: int) -> str:
    marks = ('✓' if index < phase else '●' if index == phase else '○' for index in range(len(PHASES)))
    return '   '.join(f'{mark} {name}' for mark, name in zip(marks, PHASES))

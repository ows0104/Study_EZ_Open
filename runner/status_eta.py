"""Empirical duration ranges and scheduling estimates for the monitor."""
from __future__ import annotations

import heapq
import math


def bounds(row: dict, samples: list[dict]) -> tuple[int, int, int] | None:
    candidates = [s for s in samples if s['kind'] == row['kind'] and s['subject'] == row['subject']]
    same = [s for s in candidates if bool(s['force']) == bool(row.get('force'))]
    chosen = same if len(same) >= 3 else candidates
    values = sorted(s['seconds'] for s in chosen[:30])
    if len(values) < 3:
        return None
    # Middle half of recent successful runs. This is a typical range, not a deadline.
    return values[(len(values) - 1) // 4], values[math.ceil((len(values) - 1) * .75)], len(values)


def estimate(value: dict, now: float, checked_at: float) -> dict:
    samples = value.get('timingSamples', [])
    running, waiting = value.get('running', []), value.get('waiting', [])
    workers = max(1, int(value.get('maxRunning', 2)))
    estimates, lows, highs = {}, [], []
    missing = False
    for row in running:
        span = bounds(row, samples)
        elapsed = row.get('elapsedSeconds', 0) + max(0, int(now - checked_at))
        if span is None or elapsed >= span[1]:
            estimates[row['id']] = {'range': None, 'overrun': span is not None}
            missing = True
            continue
        low, high, count = span
        remaining = (max(60, low - elapsed), max(60, high - elapsed))
        estimates[row['id']] = {'range': remaining, 'samples': count}
        lows.append(remaining[0]); highs.append(remaining[1])
    for _ in range(max(0, workers - len(running))):
        lows.append(0); highs.append(0)
    heapq.heapify(lows); heapq.heapify(highs)
    for row in waiting:
        span = bounds(row, samples)
        if span is None or not lows:
            missing = True
            continue
        low, high, count = span
        resume = row.get('resumeAt')
        if resume:
            from datetime import datetime
            delay = max(0, int(datetime.fromisoformat(resume).timestamp() - now))
        else:
            delay = 0
        heapq.heappush(lows, max(heapq.heappop(lows), delay) + low)
        heapq.heappush(highs, max(heapq.heappop(highs), delay) + high)
    return {'running': estimates, 'total': None if missing or not (running or waiting) else (max(lows, default=0), max(highs, default=0))}


def range_text(span: tuple[int, int]) -> str:
    low, high = (max(1, math.ceil(s / 300) * 5) for s in span)
    def label(minutes):
        if minutes < 60:
            return f'{minutes}분'
        hours, rest = divmod(minutes, 60)
        return f'{hours}시간' + (f' {rest}분' if rest else '')
    return f'약 {label(low)}~{label(high)}' if low != high else f'약 {label(high)}'

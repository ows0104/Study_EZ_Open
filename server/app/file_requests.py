"""File request intent, independent of transfer/attachment completion.

Legacy aggregate counts stay unknown. Snapshot their timestamps before adding
the first classified request so later requests cannot move them into a new window.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal, get_args

FilePurpose = Literal["download", "view", "preview_attach", "review_attach", "quiz_attach", "unknown"]
FILE_PURPOSES = get_args(FilePurpose)


def iso(stamp: datetime) -> str:
    return (stamp if stamp.tzinfo else stamp.replace(tzinfo=UTC)).isoformat()


def request_stats(grab) -> dict[str, dict]:
    """Read without mutating ORM JSON; old clients/rows contribute only unknown."""
    stats = {purpose: dict(value) for purpose, value in (grab.request_stats or {}).items()
             if purpose in FILE_PURPOSES}
    remainder = max(0, (grab.count or 0) - sum(value["count"] for value in stats.values()))
    if remainder:
        old = stats.get("unknown")
        stats["unknown"] = {
            "count": remainder + (old["count"] if old else 0),
            "firstAt": old["firstAt"] if old else iso(grab.first_at),
            "lastAt": iso(grab.last_at),
        }
    return stats


def add_request(grab, purpose: FilePurpose, now: datetime) -> None:
    stats = request_stats(grab)
    previous = stats.get(purpose)
    stats[purpose] = {
        "count": (previous["count"] if previous else 0) + 1,
        "firstAt": previous["firstAt"] if previous else iso(now),
        "lastAt": iso(now),
    }
    grab.request_stats = stats
    grab.count = (grab.count or 0) + 1
    grab.last_at = now

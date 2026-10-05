"""모델에서 공유하는 UTC 시각 기본값."""

from __future__ import annotations

from datetime import UTC, datetime


def _now() -> datetime:
    return datetime.now(UTC)

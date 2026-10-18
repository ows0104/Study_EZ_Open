"""Quiz Bank 학습일은 한국 시간 04시에 시작한다."""

from datetime import datetime, timedelta, timezone

KOREA = timezone(timedelta(hours=9))
DAY_START_HOUR = 4


def day_start(now: int) -> int:
    local = datetime.fromtimestamp(now / 1000, KOREA)
    shifted = local - timedelta(hours=DAY_START_HOUR)
    start = shifted.replace(hour=DAY_START_HOUR, minute=0, second=0, microsecond=0)
    return int(start.timestamp() * 1000)

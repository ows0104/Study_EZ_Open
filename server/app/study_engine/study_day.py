"""Quiz Bank 학습일은 한국 시간 새벽 4시에 시작한다(2026-11-11 사용자 지시: 모든 날짜 전환은 새벽 4시).

2026-10-19의 09시 경계를 되돌렸다. 기존 풀이 이력은 그대로이고 경계만 다시 계산한다.
"""

from datetime import datetime, timedelta, timezone

KOREA = timezone(timedelta(hours=9))
DAY_START_HOUR = 4


def day_start(now: int) -> int:
    local = datetime.fromtimestamp(now / 1000, KOREA)
    shifted = local - timedelta(hours=DAY_START_HOUR)
    start = shifted.replace(hour=DAY_START_HOUR, minute=0, second=0, microsecond=0)
    return int(start.timestamp() * 1000)

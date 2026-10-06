"""간소화한 망각 추정. FSRS v4의 곡선 형태만 사용하며 개인별 보정 모델은 아니다.

R(t,S) = 1 / (1 + t / (9S)). S일 뒤 마지막 평가 지수의 90%가 남는다.
출처: https://github.com/open-spaced-repetition/fsrs4anki/wiki/The-Algorithm/d040f23afdfcc33a1fab734f821008668ccfd116
S의 초기값·갱신 규칙은 Study_EZ의 조정 가능한 휴리스틱(policy.json)이다.
저장된 mastery는 마지막 평가 직후 값이며 조회는 그 값을 덮어쓰지 않는다.
"""

from .policy import DEFAULT

DAY_MS = 86_400_000


def stability_days(dim: dict, policy: dict = DEFAULT) -> float:
    f = policy["forgetting"]
    # 옛 기록은 평가 시각은 있지만 안정성은 없다. 횟수만으로 장기 기억을 가정하지 않는다.
    return max(f["minDays"], min(f["maxDays"], dim.get("stability_days", f["legacyDays"])))


def elapsed_days(dim: dict, now: int) -> float:
    updated = dim.get("updated_at")
    # 시각이 없는 옛 기록의 나이는 알 수 없다. 다음 평가부터 시각과 안정성을 저장한다.
    return max(0, now - updated) / DAY_MS if updated is not None else 0


def retention(dim: dict, now: int, policy: dict = DEFAULT) -> float:
    return 1 / (1 + elapsed_days(dim, now) / (9 * stability_days(dim, policy)))


def memory_snapshot(state: dict, now: int | None, policy: dict = DEFAULT) -> dict:
    """읽기 전용 계산용 상태. 원본·history를 변경하거나 이 결과를 DB에 저장하지 않는다."""
    if now is None:
        return state  # 시각 없는 순수 함수 호출은 마지막 평가 직후 값을 읽는다.
    return {**state, "dimensions": {
        key: {**dim, "mastery": dim.get("mastery", 0) * retention(dim, now, policy)}
        for key, dim in state["dimensions"].items()
    }}


def next_stability(dim: dict, rating: str, now: int, policy: dict = DEFAULT) -> float:
    f = policy["forgetting"]
    if not dim.get("reviews"):
        value = f["initialDays"][rating]
    else:
        previous = stability_days(dim, policy)
        elapsed = elapsed_days(dim, now)
        if rating == "Again":
            value = min(f["lapseMaxDays"], previous * f["lapseMultiplier"])
        elif elapsed < f["minSpacingDays"]:
            value = previous
        else:
            # 간격/S에 비례해 늘리되 한 번의 늦은 복습으로 무한히 늘어나지는 않는다.
            value = previous * (1 + (f["growth"][rating] - 1) * min(1, elapsed / previous))
    return max(f["minDays"], min(f["maxDays"], value))

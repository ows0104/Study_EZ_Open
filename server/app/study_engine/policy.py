"""Study Engine 의 수치 — `policy.json` 이 원본이다.

AdaptiveStudy3/study_engine/policy.mjs 를 옮겼다(2026-10-04). **수치는 시제품 그대로다.**
관리자: 「수치는 조정해 보긴 해야 할 듯」 — 근거 없이 정한 값이라는 뜻이다. 고칠 때는
`policy.json` 만 고치고 version 을 올린다. 학습 기록에 version·hash 가 남는다.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
from functools import lru_cache
from pathlib import Path

POLICY_PATH = Path(__file__).with_name("policy.json")


def _shape(value, expected, key: str = "policy") -> None:
    if isinstance(expected, list):
        if not isinstance(value, list) or not value or len(set(map(str, value))) != len(value):
            raise ValueError(f"{key}: 비어 있거나 중복된 목록")
        for v in value:
            _shape(v, expected[0], key)
        return
    if isinstance(expected, dict):
        if not isinstance(value, dict) or sorted(value) != sorted(expected):
            raise ValueError(f"{key}: 정책 필드 누락/오류")
        for k in expected:
            _shape(value[k], expected[k], f"{key}.{k}")
        return
    if isinstance(expected, bool) or isinstance(value, bool):
        ok = isinstance(value, bool) and isinstance(expected, bool)
    elif isinstance(expected, (int, float)):
        ok = isinstance(value, (int, float)) and math.isfinite(value) and value >= 0
    else:
        ok = isinstance(value, type(expected))
    if not ok:
        raise ValueError(f"{key}: 정책 값 오류")


def validate_policy(p: dict, template: dict | None = None) -> dict:
    _shape(p, template if template is not None else _template())

    def unit(v) -> bool:
        return 0 < v <= 1

    m = p["mastery"]
    if not p["version"].strip() or not unit(m["alpha"]) or not unit(m["maxTarget"]):
        raise ValueError("숙련도 정책 범위 오류")
    r = m["ratings"]
    if not (r["Again"] == 0 and 0 < r["Hard"] < r["Good"] < r["Easy"] == 1):
        raise ValueError("평가 목표는 Again < Hard < Good < Easy=1 순서여야 합니다.")
    if m["maxTarget"] >= r["Good"] or any(not unit(n) or n > m["maxTarget"] for n in [*m["targets"].values(), *m["tierTargets"].values()]):
        raise ValueError("목표 숙련도는 Good 목표보다 낮아야 합니다.")
    if not m["tierTargets"]["Core"] > m["tierTargets"]["Important"] > m["tierTargets"]["Optional"]:
        raise ValueError("중요도별 목표 숙련도는 Core > Important > Optional이어야 합니다.")
    f = p["forgetting"]
    if not (0 < f["minDays"] <= f["legacyDays"] <= f["maxDays"]
            and f["minDays"] <= f["lapseMaxDays"] <= f["maxDays"]
            and 0 < f["lapseMultiplier"] < 1 and 0 < f["minSpacingDays"] <= f["maxDays"]):
        raise ValueError("망각 정책 범위 오류")
    initial = f["initialDays"]
    growth = f["growth"]
    if not (f["minDays"] <= initial["Again"] <= initial["Hard"] <= initial["Good"] <= initial["Easy"] <= f["maxDays"]
            and 1 <= growth["Hard"] <= growth["Good"] <= growth["Easy"]):
        raise ValueError("평가별 기억 유지 기간 순서 오류")
    pr = p["progression"]
    gates = [*pr["thresholds"].values(), pr["prerequisiteMastery"], pr["advancedCore"], pr["optionalCore"]]
    if any(not unit(n) or n >= r["Good"] for n in gates):
        raise ValueError("진입 기준은 Good으로 도달 가능해야 합니다.")
    e = p["exam"]
    if not e["closeDays"] < e["middleDays"] < e["farDays"]:
        raise ValueError("시험 단계 경계 순서 오류")
    counts = [p["remediation"]["maxReviews"], p["recency"]["window"], p["recency"]["diversityWindow"],
              p["session"]["defaultSize"], *p["session"]["sizes"], *p["ordering"].values()]
    if any(not isinstance(n, int) or not 1 <= n <= 1000 for n in counts):
        raise ValueError("횟수/회차 크기 범위 오류")
    spacing = p["ordering"]
    if not spacing["minIntervening"] <= spacing["targetIntervening"] <= spacing["maxIntervening"]:
        raise ValueError("회상방향 간격 순서 오류")
    if p["session"]["defaultSize"] not in p["session"]["sizes"] or any(
            x not in ("Good", "Easy") for x in p["remediation"]["successRatings"]):
        raise ValueError("회차/보충 성공 정책 오류")
    if not isinstance(pr["maxStageAhead"], int) or pr["maxStageAhead"] > 3 or not 1 <= pr["highImportance"] <= 5:
        raise ValueError("단계/중요도 범위 오류")
    return p


@lru_cache(maxsize=1)
def _template() -> dict:
    return json.loads(POLICY_PATH.read_text(encoding="utf-8"))


def load_policy() -> dict:
    """복사본을 준다 — 호출한 쪽이 고쳐도 원본이 안 바뀐다."""
    return validate_policy(copy.deepcopy(_template()))


DEFAULT = load_policy()


def policy_hash(p: dict) -> str:
    return hashlib.sha256(json.dumps(p, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()

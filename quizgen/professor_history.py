"""원본 근거로 확인한 교수 이력 정정. 강의·연도를 좁혀 적용한다."""
from __future__ import annotations

import copy
import json
from pathlib import Path

from .textutil import norm_key

RULES = json.loads(Path(__file__).with_suffix(".json").read_text(encoding="utf-8"))


def history(title: str, cells: dict, years=()) -> tuple[dict, list[dict]]:
    corrected = copy.deepcopy(cells)
    records = []
    for rule in RULES:
        if norm_key(title) not in {norm_key(t) for t in rule["titles"]}:
            continue
        year = rule["year"]
        if year[2:] not in cells and not any(str(y).split("-")[0] == year for y in years):
            continue
        corrected[year[2:]] = list(rule["professors"])
        records.append({k: copy.deepcopy(rule[k]) for k in ("year", "professors", "table_professors", "evidence")})
    return corrected, records


def corrected_payload(payload: dict) -> dict:
    result = copy.deepcopy(payload)
    stats = result.setdefault("stats", {})
    cells, records = history(result["title"], stats.get("professors_by_year", {}),
                             [q["year"] for q in result.get("questions", [])])
    if not records:
        return result
    stats["professors_by_year"] = cells
    stats["professor_history_corrections"] = records
    for q in result.get("questions", []):
        for record in records:
            if str(q["year"]).split("-")[0] == record["year"]:
                q["by"] = list(record["professors"])
    return result

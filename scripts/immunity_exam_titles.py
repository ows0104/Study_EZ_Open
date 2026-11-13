"""Conditional data-only update: name the 2026-11-20/27 exam cells 「감염과 면역 1차/2차 시험」.

Bare 「시험」 titles leave `/api/study-plan` with no plan, so the calendar 「오늘 복습」 shows 「–」
(docs/changes/2026-11-13-immunity-exam-titles). Only title·course·course_key of the two rows change.
The default run only checks. Database writes require --apply (and the change's deploy approval).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
CHANGE = ROOT / "docs/changes/2026-11-13-immunity-exam-titles"
SOURCE = ROOT / "data/timetable/2026_본1_2학기_시간표.json"
KEPT = ("date", "details", "category")


def pairs() -> list[dict]:
    record = json.loads((CHANGE / "source.json").read_text(encoding="utf-8"))
    assert record["after_sha256"] == hashlib.sha256(SOURCE.read_bytes()).hexdigest(), "Timetable JSON differs from the reviewed after"
    rows = {r["id"]: r for r in json.loads(SOURCE.read_text(encoding="utf-8"))}
    for pair in record["changed"]:
        assert rows[pair["after"]["id"]] == pair["after"]
    return record["changed"]


def columns(title: str) -> dict:
    from app.naming import course_from_title, normalize_stem
    course = course_from_title(title)
    return {"title": title, "course": course, "course_key": normalize_stem(course)}


def update_database(engine, *, apply: bool = False, reverse: bool = False) -> dict:
    from sqlalchemy import MetaData, select, update
    metadata = MetaData()
    metadata.reflect(bind=engine, only=["timetable_event"])
    events = metadata.tables["timetable_event"]
    changes, result = pairs(), {"apply": apply, "reverse": reverse, "rows": []}
    with engine.begin() as conn:
        for pair in changes:
            before, after = (pair["after"], pair["before"]) if reverse else (pair["before"], pair["after"])
            row = conn.execute(select(events).where(events.c.id == before["id"])).mappings().one()
            assert row["date"].isoformat() == before["date"] and row["details"] == before["details"] \
                and row["category"] == "exam", f"{before['id']}: date/details/category differ; stop"
            current = {k: row[k] for k in ("title", "course", "course_key")}
            origin, target = columns(before["title"]), columns(after["title"])
            assert current in (origin, target), f"{before['id']}: {current} is neither reviewed value; stop"
            result["rows"].append({"id": before["id"], "from": current["title"], "to": target["title"],
                                   "changed": current != target})
            if apply and current != target:
                conn.execute(update(events).where(events.c.id == before["id"]).values(**target))
        if apply:
            for pair in changes:
                wanted = columns((pair["before"] if reverse else pair["after"])["title"])
                row = conn.execute(select(events).where(events.c.id == pair["after"]["id"])).mappings().one()
                assert {k: row[k] for k in wanted} == wanted
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", choices=["production", "local"], required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--reverse", action="store_true")
    args = parser.parse_args()
    if args.apply and args.database == "production":
        sys.path.insert(0, str(ROOT / "scripts"))
        import development as dev
        folder, state = dev.load(CHANGE.name)
        errors = dev.gate(folder, state, "deploy")
        if errors:
            raise SystemExit("; ".join(errors))
    if args.database == "local":
        os.environ.update(ENVIRONMENT="local-test",
                          DATABASE_URL="sqlite:///" + (ROOT / "server/local_test_data/studyez.db").as_posix())
    else:
        from dotenv import load_dotenv
        load_dotenv(ROOT / "server/.env", override=True)
    sys.path.insert(0, str(ROOT / "server"))
    from app.database import engine
    print(json.dumps(update_database(engine, apply=args.apply, reverse=args.reverse), ensure_ascii=False))


if __name__ == "__main__":
    main()

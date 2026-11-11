"""Reviewed, conditional data-only update for the 2026-11-05 timetable notice.

No table creation, lecture rekeying, file replacement, or question changes.
The default command validates local inputs. Database writes require --apply.
"""
from __future__ import annotations

import argparse
from datetime import date
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
CHANGE = ROOT / "docs/changes/2026-11-05-immunity-timetable"
SOURCE = ROOT / "data/timetable/2026_본1_2학기_시간표.json"
# The 11-05 stable IDs, kept here after 2026-11-11-immunity-renumber emptied the live alias files.
IDENTITIES = CHANGE / "identities/2026-2.json"
FIELDS = {"date": "date", "start_time": "startTime", "end_time": "endTime",
          "title": "title", "details": "details", "professor": "professor", "category": "category"}


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()


def inputs():
    rows, patch, identities = read(SOURCE), read(CHANGE / "timetable-patch.json"), read(IDENTITIES)
    assert len(rows) == len({r["id"] for r in rows}) == 369, "Event IDs changed/duplicated"
    assert len(patch) == len({r["before"]["id"] for r in patch}) == 16
    by_id = {r["id"]: r for r in rows}
    for pair in patch:
        assert pair["before"]["id"] == pair["after"]["id"]
        assert pair["after"] == by_id[pair["after"]["id"]], "Patch differs from source"
    moved = {p["before"]["id"]: p for p in patch
             if (p["before"]["date"], p["before"]["startTime"]) !=
                (p["after"]["date"], p["after"]["startTime"])}
    assert len(moved) == len(identities) == 12 and moved.keys() == identities.keys()
    for event_id, pair in moved.items():
        r = pair["before"]
        assert identities[event_id] == r["date"].replace("-", "")[2:] + f"_{int(r['startTime'][:2])-8:02d}"
    assert read(CHANGE / "source.json")["after_sha256"] == hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    return rows, patch, identities


def values(raw):
    from app.naming import course_from_title, normalize_stem, slot_from_time
    result = {k: raw[v] for k, v in FIELDS.items()}
    result["date"] = date.fromisoformat(raw["date"])
    result["course"] = course_from_title(raw["title"])
    result["course_key"] = normalize_stem(result["course"])
    result["slot"] = slot_from_time(raw["startTime"])
    return result


def lecture_snapshot(connection, table):
    from sqlalchemy import select
    return {(r["subject"], r["run_id"]): dict(r)
            for r in connection.execute(select(table)).mappings()}


def protected_snapshot(connection, metadata):
    """Store only counts/hashes; never persist links, responses, or personal data."""
    from sqlalchemy import select
    result = {}
    for name, table in sorted(metadata.tables.items()):
        if name in {"lecture", "timetable_event"} or not {"subject", "run_id"} <= set(table.c.keys()):
            continue
        hashes = sorted(fingerprint(dict(r)) for r in connection.execute(
            select(table).where(table.c.subject == "감염과 면역")).mappings())
        result[name] = {"rows": len(hashes), "sha256": fingerprint(hashes)}
    return result


def update_database(engine, *, apply=False, reverse=False, previous_receipt=None):
    from sqlalchemy import MetaData, select, update
    rows, patch, identities = inputs()
    metadata = MetaData()
    metadata.reflect(bind=engine)
    events, lectures = metadata.tables["timetable_event"], metadata.tables["lecture"]
    previous = read(previous_receipt) if previous_receipt else None
    if reverse and not previous:
        raise ValueError("Rollback requires the original successful receipt")
    expected = {r["id"]: values(r) for r in rows}
    old = dict(expected)
    for pair in patch:
        old[pair["before"]["id"]] = values(pair["before"])
    target, origin = (old, expected) if reverse else (expected, old)
    receipt = {"patch_sha256": fingerprint(patch), "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
               "reverse": reverse, "applied": False}
    with engine.begin() as conn:
        if engine.dialect.name == "postgresql" and apply:
            conn.exec_driver_sql("SET LOCAL lock_timeout = '10s'")
            # Short table locks prevent a concurrent registration from seeing half a swap.
            conn.exec_driver_sql("LOCK TABLE timetable_event, lecture IN SHARE ROW EXCLUSIVE MODE")
        present = {r["id"]: {k: r[k] for k in next(iter(expected.values()))}
                   for r in conn.execute(select(events)).mappings()}
        assert present.keys() == expected.keys(), "Unexpected/missing timetable events; stop"
        assert present == origin or present == target, "Database differs from both reviewed versions; stop"
        before = lecture_snapshot(conn, lectures)
        protected = protected_snapshot(conn, metadata)
        changed_flags = []
        if present != target and apply:
            for pair in patch:
                event_id = pair["before"]["id"]
                conn.execute(update(events).where(events.c.id == event_id).values(**target[event_id]))
            if reverse:
                for saved in previous["confirmed_links"]:
                    key = (saved["subject"], saved["run_id"])
                    assert before[key]["timetable_event_id"] == saved["event_id"]
                    conn.execute(update(lectures).where(lectures.c.subject == key[0], lectures.c.run_id == key[1])
                                 .values(match_confirmed=saved["before"]))
                    changed_flags.append(saved)
            else:
                for key, row in before.items():
                    event_id = row["timetable_event_id"]
                    if event_id not in identities or row["match_confirmed"]:
                        continue
                    assert key == ("감염과 면역", identities[event_id]), "Unreviewed moved lecture; stop"
                    saved = {"subject": key[0], "run_id": key[1], "event_id": event_id,
                             "before": row["match_confirmed"]}
                    changed_flags.append(saved)
                    conn.execute(update(lectures).where(lectures.c.subject == key[0], lectures.c.run_id == key[1])
                                 .values(match_confirmed=True))
            receipt["applied"] = True
        after = lecture_snapshot(conn, lectures)
        assert before.keys() == after.keys(), "Lecture identities changed"
        flags = {(x["subject"], x["run_id"]): (x["before"] if reverse else True) for x in changed_flags}
        for key, row in before.items():
            wanted = dict(row)
            if key in flags:
                wanted["match_confirmed"] = flags[key]
            assert after[key] == wanted, "Unexpected lecture mutation"
        assert protected_snapshot(conn, metadata) == protected, "Protected data changed"
        final = {r["id"]: {k: r[k] for k in next(iter(expected.values()))}
                 for r in conn.execute(select(events)).mappings()}
        assert final == (target if apply else present)
        receipt.update(events=len(final), changed_events=sum(present[k] != target[k] for k in target),
                       lectures=len(before), confirmed_links=changed_flags, protected=protected,
                       lecture_keys_sha256=fingerprint(sorted(before)),
                       lecture_links_sha256=fingerprint(sorted((k, r["timetable_event_id"]) for k, r in before.items())),
                       missing_links=sum(r["timetable_event_id"] is None for r in after.values()),
                       timetable_sha256=fingerprint(final), preservation_verified=True)
    return receipt


def prepare_candidate():
    """A data-only candidate, separate from server/web application packages."""
    import development as dev
    import release_evidence as release
    import shutil
    folder, state = dev.load(CHANGE.name)
    errors = dev.gate(folder, state, "release")
    if errors:
        raise ValueError("; ".join(errors))
    entries = [SOURCE, IDENTITIES, IDENTITIES.with_name("2026-2-notes.json"),
               CHANGE / "timetable-patch.json", CHANGE / "source.json", Path(__file__)]
    candidate = {**dev.evidence(folder, state), "config": {"target": "timetable-data",
                 "destination": "StudyEZ configured production DB: timetable_event and reviewed lecture.match_confirmed only",
                 "rollback": "conditional reverse patch with original receipt; restore local source from recorded before values"},
                 "files": {str(p.relative_to(ROOT)).replace("\\", "/"): hashlib.sha256(p.read_bytes()).hexdigest() for p in entries},
                 "environment_files": ["server/.env"], "environment_hash": release.environment_hash("server"),
                 "release_hash": dev.digest([folder / "release.md"])}
    token = release.value_hash(candidate)
    dest = ROOT / "runs/_development" / CHANGE.name / "candidates" / token
    for p in entries:
        target = dest / p.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            assert target.read_bytes() == p.read_bytes()
        else:
            shutil.copyfile(p, target)
    assert release.manifest(dest) == candidate["files"]
    candidate.update(id=token, artifact=dest.relative_to(ROOT).as_posix())
    dev.update(folder, lambda s: s.update(candidate=candidate))
    return {"candidate": token, "target": "timetable-data", "files": len(entries)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", choices=["production", "local"])
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--reverse", action="store_true")
    parser.add_argument("--previous-receipt", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--prepare", action="store_true")
    args = parser.parse_args()
    rows, patch, identities = inputs()
    if args.prepare:
        print(json.dumps(prepare_candidate()))
        return
    if not args.database:
        print(json.dumps({"events": len(rows), "changed": len(patch), "stable_identities": len(identities)}))
        return
    if args.apply:
        if not args.output or args.output.exists():
            raise ValueError("Apply requires a new receipt output path")
        import development as dev
        folder, state = dev.load(CHANGE.name)
        errors = dev.gate(folder, state, "deploy")
        if errors:
            raise ValueError("; ".join(errors))
    if args.database == "local":
        os.environ.update(ENVIRONMENT="local-test", DATABASE_URL="sqlite:///" + (ROOT / "server/local_test_data/studyez.db").as_posix())
    else:
        from dotenv import load_dotenv
        load_dotenv(ROOT / "server/.env", override=True)
    sys.path.insert(0, str(ROOT / "server"))
    from app.database import engine
    result = update_database(engine, apply=args.apply, reverse=args.reverse, previous_receipt=args.previous_receipt)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k not in {"protected", "confirmed_links"}}, ensure_ascii=False))


if __name__ == "__main__":
    main()

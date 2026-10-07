"""Read-only feedback collection and a durable, versioned local review ledger.

Run with server/.venv/Scripts/python.exe -m runner.feedback. Collection never
updates production data. Actual corrections use the existing admin routes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from collections import Counter
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_HOME = ROOT / "runs" / "_feedback"
STATES = ("pending", "needs_info", "awaiting_approval", "approved", "deferred",
          "resolved", "dismissed")


def now() -> str:
    return datetime.now(UTC).isoformat()


def fingerprint(value: dict) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":")).encode()).hexdigest()


def read_json(path: Path, default: dict) -> dict:
    if not path.exists():
        return default
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Invalid JSON object: {path.name}")
    return value


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix=".feedback-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


@contextmanager
def locked(home: Path):
    home.mkdir(parents=True, exist_ok=True)
    path = home / ".lock"
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        raise RuntimeError("Feedback ledger is busy; retry later.") from None
    try:
        os.write(fd, str(os.getpid()).encode())
        yield
    finally:
        os.close(fd)
        path.unlink()


def reconcile(ledger: dict, items: list[dict]) -> dict:
    """Keep decisions across identical pulls; changed sources revoke old approval."""
    records = ledger.setdefault("items", {})
    ids = [item["id"] for item in items]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate feedback IDs in collection")
    for source in items:
        key = source["id"]
        revision = fingerprint(source)
        entry = records.get(key)
        if entry is None:
            entry = records[key] = {"history": [], "firstSeenAt": now()}
        if entry.get("fingerprint") != revision or entry.get("sourceClosed"):
            if "fingerprint" in entry:
                entry["history"].append({"at": now(), "event": "source_changed_or_reopened",
                                         "source": entry["source"],
                                         "fingerprint": entry["fingerprint"],
                                         "decision": entry.get("decision")})
            entry.update(state="pending", fingerprint=revision, decision=None)
        entry.update(source=source, sourceClosed=False)
    for key, entry in records.items():
        if key not in ids:
            entry["sourceClosed"] = True
    ledger.update(schemaVersion=1, lastSuccessfulPullAt=now())
    return ledger


def record(ledger: dict, decision: dict) -> dict:
    key, state = decision.get("id"), decision.get("state")
    entry = ledger.get("items", {}).get(key)
    if not entry or entry.get("sourceClosed"):
        raise ValueError("Feedback is missing or already closed at the source")
    if decision.get("fingerprint") != entry["fingerprint"]:
        raise ValueError("Feedback changed; review the current source before deciding")
    if state not in STATES or not str(decision.get("note") or "").strip():
        raise ValueError("A valid state and review note are required")
    previous = entry.get("decision") or {}
    if state == "awaiting_approval" and not decision.get("proposal"):
        raise ValueError("An approval request must contain a concrete proposal")
    if state == "approved":
        if entry["state"] != "awaiting_approval" or not decision.get("approval"):
            raise ValueError("Approval requires a pending proposal and the user's approval reference")
        decision = {**previous, **decision}
        # A user's approval cannot silently authorize a different proposal.
        if decision.get("proposal") != previous.get("proposal"):
            raise ValueError("Changed proposals must be presented for approval again")
    if state == "resolved":
        if not decision.get("evidence") or not decision.get("validation"):
            raise ValueError("Resolution requires evidence and post-change validation")
        if entry["source"]["kind"] == "site":
            if entry["state"] != "approved" or not previous.get("approval"):
                raise ValueError("Site feedback requires explicit user approval before resolution")
            decision = {**previous, **decision}
    if state == "dismissed" and not decision.get("evidence"):
        raise ValueError("Dismissing a report requires a reason backed by evidence")
    if entry.get("decision"):
        entry["history"].append({"at": now(), "event": "decision_updated",
                                 "fingerprint": entry["fingerprint"],
                                 "decision": entry["decision"]})
    entry.update(state=state, decision={**decision, "at": now()})
    return ledger


def collect(home: Path) -> list[dict]:
    """Use the configured operator DB, in a database-enforced read-only transaction.

    No contact details are exported. A stale bank report never receives the
    replacement question's content, even if its question ID was reused.
    """
    from dotenv import load_dotenv

    load_dotenv(ROOT / "server" / ".env", override=False)
    sys.path.insert(0, str(ROOT / "server"))
    from sqlalchemy import select, text
    from sqlalchemy.orm import Session

    from app.database import engine
    from app.models import Asset, BankFeedback, Lecture, QuizBank, SiteFeedback

    items, attachments = [], []
    with engine.connect() as connection, connection.begin():
        if connection.dialect.name == "postgresql":
            connection.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
            connection.execute(text("SET LOCAL statement_timeout = '30s'"))
        elif connection.dialect.name == "sqlite":
            connection.execute(text("PRAGMA query_only = ON"))
        else:
            raise RuntimeError("Read-only collection supports PostgreSQL or SQLite")
        with Session(bind=connection) as db:
            for row in db.scalars(select(SiteFeedback).where(SiteFeedback.status == "open")
                                  .order_by(SiteFeedback.id)):
                shots = [{"index": i, "name": shot.get("name", ""),
                          "contentType": shot.get("contentType", "")}
                         for i, shot in enumerate(row.screenshots or [])]
                items.append({"id": f"site:{row.id}", "kind": "site", "reportId": row.id,
                              "message": row.message, "page": row.page,
                              "createdAt": row.created_at.isoformat(), "screenshots": shots})
                attachments.extend((row.id, i, shot) for i, shot in enumerate(row.screenshots or []))
            banks, lectures, assets = {}, {}, {}
            for row in db.scalars(select(BankFeedback).where(BankFeedback.status == "open",
                                                            BankFeedback.category != "good")
                                  .order_by(BankFeedback.id)):
                key = (row.subject, row.run_id)
                if key not in banks:
                    banks[key] = db.get(QuizBank, key)
                    lectures[key] = db.get(Lecture, key)
                    assets[key] = [{"id": a.id, "kind": a.kind, "filename": a.filename,
                                    "slideNo": a.slide_no}
                                   for a in db.scalars(select(Asset).where(
                                       Asset.subject == row.subject, Asset.run_id == row.run_id,
                                       Asset.kind.in_(("notes_current", "notes_prev", "bank_media")))
                                       .order_by(Asset.id))]
                bank, lecture = banks[key], lectures[key]
                stale = bank is None or bank.build_id != row.build_id
                question = next((q for q in ((bank.bank or {}).get("questions", []) if bank else [])
                                 if q["question_id"] == row.question_id), None) if not stale else None
                items.append({"id": f"bank:{row.id}", "kind": "question", "reportId": row.id,
                              "subject": row.subject, "runId": row.run_id,
                              "title": lecture.title if lecture else "", "buildId": row.build_id,
                              "questionId": row.question_id, "category": row.category,
                              "message": row.comment, "createdAt": row.created_at.isoformat(),
                              "stale": stale, "bankStatus": bank.status if bank else None,
                              "question": question, "assets": assets[key]})
    if attachments:
        from app.storage import ObjectStorage

        storage = ObjectStorage()
        for report_id, index, shot in attachments:
            suffix = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}.get(
                shot.get("contentType"))
            if not suffix:
                raise RuntimeError("Unknown feedback screenshot format")
            path = home / "screenshots" / f"site-{report_id}-{index}{suffix}"
            if not path.exists():
                body = storage.get_bytes(shot["key"])
                if body is None:
                    raise RuntimeError(f"Screenshot unavailable: site:{report_id}/{index}")
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(body)
    return items


def summary(ledger: dict) -> dict:
    active = {key: entry for key, entry in ledger.get("items", {}).items()
              if not entry.get("sourceClosed")}
    return {"lastSuccessfulPullAt": ledger.get("lastSuccessfulPullAt"),
            "counts": dict(Counter(entry["state"] for entry in active.values())),
            "pending": [key for key, entry in active.items() if entry["state"] == "pending"],
            "approved": [key for key, entry in active.items() if entry["state"] == "approved"]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("pull", "status", "record"))
    parser.add_argument("--home", type=Path, default=DEFAULT_HOME)
    parser.add_argument("--decision", type=Path, help="JSON decision file; required for record")
    args = parser.parse_args(argv)
    if args.command == "record" and args.decision is None:
        parser.error("record requires --decision")
    try:
        with locked(args.home):
            path = args.home / "ledger.json"
            ledger = read_json(path, {"schemaVersion": 1, "items": {}})
            if args.command == "pull":
                # Collection must succeed fully before replacing the last good ledger.
                ledger = reconcile(ledger, collect(args.home))
                write_json(path, ledger)
            elif args.command == "record":
                ledger = record(ledger, read_json(args.decision, {}))
                write_json(path, ledger)
            print(json.dumps(summary(ledger), ensure_ascii=False))
        return 0
    except Exception as exc:
        # DB/storage exception text may contain connection credentials; never print it.
        message = str(exc) if isinstance(exc, ValueError) else type(exc).__name__
        print(f"Feedback operation failed: {message}. Last successful ledger retained.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Offline packaging of explicitly supplied, authored connection reviews."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

from studyez_contracts import learning_links
from studyez_contracts.learning_links import HASH_POLICY, SCHEMA_VERSION, SOURCES_SCHEMA, LinkValidationError, validate_review
from studyez_contracts.learning_links.validate import index_by, require, validate_shape
from .connection_report import render_report

TOOL_VERSION = "connection-plan/1"


def file_hash(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, f"JSON: duplicate key {key}")
        result[key] = value
    return result


def _invalid_constant(value):
    raise LinkValidationError(f"JSON: non-finite number {value}")


def read_json(path):
    raw = path.read_bytes()
    value = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=_unique_object,
                       parse_constant=_invalid_constant)
    return value, hashlib.sha256(raw).hexdigest()


def write_json(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n")


def build_package(review_path, bank_path, sources_path, out):
    review_path, bank_path, sources_path = (Path(p).resolve(strict=True) for p in (review_path, bank_path, sources_path))
    out = Path(out).resolve()
    require(not out.exists(), f"output already exists: {out}")
    review, review_hash = read_json(review_path)
    bank, bank_hash = read_json(bank_path)
    inventory, inventory_hash = read_json(sources_path)
    validate_shape(inventory, SOURCES_SCHEMA, "sources")
    source_rows = index_by(inventory["sources"], "source_id")
    snapshots = {review_path: review_hash, bank_path: bank_hash, sources_path: inventory_hash}
    source_hashes, source_paths = {}, {}
    for sid, entry in source_rows.items():
        path = Path(entry["path"])
        path = (sources_path.parent / path).resolve(strict=True)
        require(path.is_file(), f"source {sid}: expected file")
        digest = file_hash(path)
        require(digest == entry["sha256"], f"source {sid}: manifest revision mismatch")
        require(path not in snapshots or snapshots[path] == digest, "input changed during read")
        snapshots[path] = digest
        source_hashes[sid], source_paths[sid] = digest, str(path)
    for path in snapshots:
        require(not path.is_relative_to(out), "output must not contain input files")
    normalized = validate_review(review, bank, bank_sha256=bank_hash, source_hashes=source_hashes)
    report = render_report(normalized, bank)
    warnings = ["Structural validation only; authored judgments are not medically verified or approved for publication."]
    if review["provenance"]["independent_points"] != "confirmed":
        warnings.append("Independent point extraction is not confirmed by the supplied provenance.")
    if review["scope"]["limitations"]:
        warnings.append("Review scope has recorded limitations.")
    tool_files = [Path(__file__), Path(__file__).with_name("connection_report.py")]
    tool_files += [Path(learning_links.__file__).parent / name for name in ("__init__.py", "schema.py", "validate.py")]
    manifest = {"tool_version": TOOL_VERSION, "schema_version": SCHEMA_VERSION, "hash_policy": HASH_POLICY,
                "inputs": {"review": {"path": str(review_path), "sha256": review_hash},
                           "bank": {"path": str(bank_path), "sha256": bank_hash},
                           "source_manifest": {"path": str(sources_path), "sha256": inventory_hash},
                           "sources": {sid: {"path": source_paths[sid], "sha256": digest} for sid, digest in source_hashes.items()}},
                "tool_files": {str(path.resolve()): file_hash(path) for path in tool_files}}
    validation = {"structurally_valid": True, "medical_validation": "not_performed",
                  "publication": "not_authorized", "learner_state": "not_created",
                  "authored_review_status": normalized["provenance"]["status"],
                  "coverage_counts": dict(sorted(Counter(c["status"] for c in normalized["coverage"]).items())),
                  "warnings": warnings}
    out.mkdir(parents=True, exist_ok=False)
    try:
        write_json(out / "learning-links.json", normalized)
        write_json(out / "manifest.json", manifest)
        write_json(out / "validation.json", validation)
        with (out / "review.md").open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(report)
        for path, digest in snapshots.items():
            require(file_hash(path) == digest, f"input changed during packaging: {path}")
        outputs = {name: file_hash(out / name) for name in
                   ("learning-links.json", "manifest.json", "validation.json", "review.md")}
        write_json(out / "complete.tmp", {"status": "local_package_complete", "outputs": outputs,
                                          "medical_validation": "not_performed", "publication": "not_authorized"})
        (out / "complete.tmp").rename(out / "complete.json")
    except Exception as error:
        # Keep partial outputs for diagnosis. No completion marker is written on failure.
        try:
            write_json(out / "failure.json", {"status": "incomplete", "error": str(error)})
        except OSError:
            pass
        raise
    return {"status": "local_package_complete", "output": str(out), "coverage_counts": validation["coverage_counts"]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("review", "bank", "sources", "out"):
        parser.add_argument(f"--{name}", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        result = build_package(args.review, args.bank, args.sources, args.out)
    except (OSError, ValueError, UnicodeError, RecursionError) as error:
        print(json.dumps({"status": "failed", "error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

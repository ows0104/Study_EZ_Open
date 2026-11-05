"""Pure structural checks. Authored semantic judgments remain unverified claims."""
from __future__ import annotations

import copy
import hashlib
import json
import re
from collections import Counter, deque

from .schema import HASH_POLICY, REVIEW_SCHEMA


class LinkValidationError(ValueError):
    pass


def canonical_json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def question_hash(question, bank):
    """Hash the whole question and bank context (including validation/personal edits).

    Conservative: even unrelated context changes require an explicit new review.
    Whitespace in strings and array order are intentionally significant.
    """
    payload = {"policy": HASH_POLICY, "question": question,
               "bank_context": {key: value for key, value in bank.items() if key != "questions"}}
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def require(condition, message):
    if not condition:
        raise LinkValidationError(message)


def validate_shape(value, schema, path="review"):
    """Validate the small JSON Schema subset used by our published v1 schemas."""
    kinds = schema["type"]
    kinds = [kinds] if isinstance(kinds, str) else kinds
    checks = {"object": lambda x: type(x) is dict, "array": lambda x: type(x) is list,
              "string": lambda x: type(x) is str, "integer": lambda x: type(x) is int,
              "null": lambda x: x is None,"boolean":lambda x:type(x)is bool,
              "number":lambda x:type(x)in (int,float)}
    require(any(checks[k](value) for k in kinds), f"{path}: expected {kinds}")
    if "enum" in schema:
        require(value in schema["enum"], f"{path}: invalid enum {value!r}")
    if value is None:
        return
    if isinstance(value, dict):
        require(set(schema.get('required',schema['properties']))<=set(value)<=set(schema['properties']), f"{path}: missing or unknown fields")
        for key, field in schema["properties"].items():
            if key in value:validate_shape(value[key], field, f"{path}.{key}")
    elif isinstance(value, list):
        require(len(value) >= schema.get("minItems", 0), f"{path}: too few entries")
        require(len(value)<=schema.get('maxItems',len(value)),f'{path}: too many entries')
        if schema.get("uniqueItems"):
            require(len({canonical_json(x) for x in value}) == len(value), f"{path}: duplicate entries")
        for index, item in enumerate(value):
            validate_shape(item, schema["items"], f"{path}[{index}]")
    elif isinstance(value, str):
        require(len(value.strip()) >= schema.get("minLength", 0), f"{path}: empty text")
        if "pattern" in schema:
            require(re.fullmatch(schema["pattern"], value) is not None, f"{path}: invalid pattern")
    elif type(value) in (int,float):
        require(value >= schema.get("minimum", value), f"{path}: below minimum")
        require(value<=schema.get('maximum',value),f'{path}: above maximum')


def index_by(rows, key):
    result = {}
    for row in rows:
        identity = row[key]
        require(identity not in result, f"{key}: duplicate {identity}")
        result[identity] = row
    return result


def refs_exist(ids, known, label):
    require(set(ids) <= set(known), f"{label}: unknown references {sorted(set(ids) - set(known))}")


def acyclic(edges, label):
    graph, incoming = {}, Counter()
    for left, right in edges:
        graph.setdefault(left, set()).add(right)
        graph.setdefault(right, set())
    for neighbors in graph.values():
        incoming.update(neighbors)
    queue = deque(node for node in graph if not incoming[node])
    visited = 0
    while queue:
        node = queue.popleft()
        visited += 1
        for child in graph[node]:
            incoming[child] -= 1
            if not incoming[child]:
                queue.append(child)
    require(visited == len(graph), f"{label}: cycle")


def bank_questions(bank):
    require(type(bank) is dict and type(bank.get("questions")) is list, "bank: questions array required")
    for row in bank["questions"]:
        require(type(row) is dict and type(row.get("question_id")) is str
                and row["question_id"].strip(), "bank: question_id required")
        for field in ("question", "answer"):
            require(type(row.get(field)) is str and row[field].strip(), f"bank: {field} required")
    return index_by(bank["questions"], "question_id")


def validate_review(review, bank, *, bank_sha256, source_hashes):
    """Return an independent normalized copy; never mutate bank or review.

    Hash arguments must be computed from the supplied files by the caller.
    This function performs no file, network, model, database, or clock access.
    """
    if review.get('schema_version')=='learning-links/2':
        from ..roots.generation_v2 import REVIEW2
        validate_shape(review,REVIEW2)
    else:validate_shape(review, REVIEW_SCHEMA)
    require(review["bank_sha256"] == bank_sha256, "bank: revision mismatch")
    if isinstance(bank, dict) and "lecture_id" in bank:
        require(bank["lecture_id"] == review["lecture_id"], "bank: lecture mismatch")
    sources = index_by(review["sources"], "source_id")
    require(set(sources) == set(source_hashes), "sources: inventory mismatch")
    for sid, source in sources.items():
        require(source["sha256"] == source_hashes[sid], f"source {sid}: revision mismatch")

    def evidence(refs):
        for ref in refs:
            require(ref["source_id"] in sources, f"evidence: unknown source {ref['source_id']}")
            count = sources[ref["source_id"]]["page_count"]
            require(not ref["pages"] or (count is not None and max(ref["pages"]) <= count),
                    "evidence: pages require a matching declared page_count")

    concepts = index_by(review["concepts"], "concept_id")
    for cid, concept in concepts.items():
        refs_exist(concept["parent_ids"], concepts, f"concept {cid}")
    acyclic([(parent, cid) for cid, c in concepts.items() for parent in c["parent_ids"]], "hierarchy")
    relations = index_by(review["relations"], "relation_id")
    for rid, relation in relations.items():
        refs_exist([relation["from_id"], relation["to_id"]], concepts, f"relation {rid}")
        evidence(relation["evidence"])
        if relation["review_status"] == "reviewed":
            require(relation["evidence"], f"relation {rid}: reviewed claim needs evidence")
    for kind in ("prerequisite", "classification"):
        acyclic([(r["from_id"], r["to_id"]) for r in relations.values() if r["kind"] == kind], kind)

    targets = index_by(review["targets"], "target_id")
    directions, owners = {}, {}
    allowed_basis = {"structural": {"structural_rationale"},
                     "exam": {"observed_exam", "exam_forecast", "teaching_emphasis"},
                     "clinical": {"clinical_rationale"}}
    for tid, target in targets.items():
        refs_exist(target["concept_ids"], concepts, f"target {tid}")
        refs_exist(target["relation_ids"], relations, f"target {tid}")
        evidence(target["evidence"])
        for axis, importance in target["importance"].items():
            require(importance["status"] != "supported" or importance["evidence"],
                    f"target {tid}: supported {axis} needs evidence")
            for item in importance["evidence"]:
                require(item["kind"] in allowed_basis[axis], f"target {tid}: wrong {axis} basis")
                evidence(item["refs"])
        for direction in target["directions"]:
            did = direction["direction_id"]
            require(did not in directions, f"direction_id: duplicate {did}")
            directions[did], owners[did] = direction, tid
            refs_exist(direction["relation_ids"], target["relation_ids"], f"direction {did}")
        require(set(target["relation_ids"]) == {r for d in target["directions"] for r in d["relation_ids"]},
                f"target {tid}: relations missing from directions")

    questions = bank_questions(bank)
    tested = {did: set() for did in directions}
    seen = set()
    question_roles = {}
    for mapping in review["mappings"]:
        qid, tid, did = (mapping[k] for k in ("question_id", "target_id", "direction_id"))
        require(qid in questions and tid in targets and owners.get(did) == tid, "mapping: unknown/mismatched reference")
        identity = (qid, did)
        require(identity not in seen, "mapping: duplicate question/direction")
        seen.add(identity)
        require(mapping["question_sha256"] == question_hash(questions[qid], bank), f"question {qid}: revision mismatch")
        groups = [set(mapping[k]) for k in ("tested_relation_ids", "provided_relation_ids", "explanation_relation_ids")]
        for group in groups:
            refs_exist(group, relations, "mapping relations")
        require(any(groups), "mapping: empty relation assignment")
        require(not (groups[0] & groups[1] or groups[0] & groups[2] or groups[1] & groups[2]),
                "mapping: tested/provided/explanation must be disjoint")
        for role, group in enumerate(groups):
            for rid in group:
                key = (qid, rid)
                require(key not in question_roles or question_roles[key] == role,
                        f"question {qid}: inconsistent relation role across mappings")
                question_roles[key] = role
        refs_exist(groups[0], directions[did]["relation_ids"], "mapping tested relations")
        require(all(relations[r]["review_status"] == "reviewed" for r in groups[0]),
                "mapping: unreviewed relation cannot be tested evidence")
        tested[did].update(groups[0])

    points = index_by(review["points"], "point_id")
    covered_targets = set()
    for pid, point in points.items():
        evidence(point["evidence"])
        refs_exist(point["target_ids"], targets, f"point {pid}")
        if point["scope_status"] == "included":
            require(point["target_ids"], f"point {pid}: included point needs targets")
            covered_targets.update(point["target_ids"])
        else:
            require(not point["target_ids"], f"point {pid}: excluded point cannot hide targets")
    require(covered_targets == set(targets), "points: targets missing from independent point comparison")
    coverage = index_by(review["coverage"], "point_id")
    require(set(coverage) == set(points), "coverage: every point needs exactly one result")
    for pid, check in coverage.items():
        relevant = {did for did, tid in owners.items() if tid in points[pid]["target_ids"]}
        confirmed, partial, missing, unknown = (set(check[k]) for k in
                                      ("confirmed_direction_ids", "partial_direction_ids", "missing_direction_ids", "unknown_direction_ids"))
        groups = (confirmed, partial, missing, unknown)
        require(sum(map(len, groups)) == len(set.union(*groups)), "coverage: overlapping directions")
        require(set.union(*groups) == relevant, f"point {pid}: every direction needs a result")
        for did in confirmed:
            require(set(directions[did]["relation_ids"]) <= tested[did], f"point {pid}: confirmed direction not directly tested")
        for did in partial:
            require(tested[did] and not set(directions[did]["relation_ids"]) <= tested[did],
                    f"point {pid}: partial direction needs some but not all relations tested")
        for did in missing:
            require(not tested[did], f"point {pid}: missing direction has tested relations")
        status = check["status"]
        if points[pid]["scope_status"] == "excluded":
            require(status == "excluded" and check["exclusion_basis"] is not None, "coverage: exclusion basis required")
            continue
        require(status != "excluded" and check["exclusion_basis"] is None, "coverage: included point cannot be excluded")
        if status == "covered":
            required = {did for did in relevant if directions[did]["requirement"] == "required"}
            require(required and required <= confirmed, f"point {pid}: required directions not covered")
            require(all(directions[did]["requirement"] != "undecided" for did in relevant),
                    f"point {pid}: undecided requirements cannot be covered")
        elif status == "partial":
            require((confirmed or partial) and (partial or missing or unknown),
                    f"point {pid}: partial needs tested and unresolved content")
        elif status == "gap":
            require(missing and not confirmed and not partial and not unknown, f"point {pid}: gap needs reviewed absence")
        else:
            # Retrieval evidence and curriculum requirement are separate axes.
            # A fully tested point can still have undefined required coverage.
            required = {did for did in relevant if directions[did]['requirement'] == 'required'}
            unsettled = any(directions[did]['requirement'] == 'undecided' for did in relevant)
            require(unknown or unsettled or not required,
                    f"point {pid}: unknown needs an unknown direction or unresolved required coverage")
    return copy.deepcopy(review)

"""Versioned, standalone authoring contract; no bank or learner-state mutation."""

SCHEMA_VERSION = "learning-links/1"
HASH_POLICY = "learning-links-question/1"
TEXT = {"type": "string", "minLength": 1}
HASH = {"type": "string", "pattern": "^[0-9a-f]{64}$"}


def obj(**fields):
    return {"type": "object", "properties": fields, "required": list(fields),
            "additionalProperties": False}


def arr(item, minimum=0):
    return {"type": "array", "items": item, "minItems": minimum, "uniqueItems": True}


def enum(*values):
    return {"type": "string", "enum": list(values)}


REF = obj(source_id=TEXT, locator=TEXT,
          pages=arr({"type": "integer", "minimum": 1}))
REFS = arr(REF)
SOURCE = obj(source_id=TEXT, label=TEXT, sha256=HASH,
             kind=enum("lecture", "notes", "exam", "other"),
             professor={"type": ["string", "null"], "minLength": 1},
             year={"type": ["integer", "null"], "minimum": 1},
             page_count={"type": ["integer", "null"], "minimum": 1})
BASIS = obj(kind=enum("structural_rationale", "observed_exam", "exam_forecast",
                     "teaching_emphasis", "clinical_rationale"), reason=TEXT,
            refs=arr(REF, 1))
IMPORTANCE = obj(status=enum("supported", "insufficient", "unreviewed"),
                 reason=TEXT, evidence=arr(BASIS))
DIRECTION = obj(direction_id=TEXT, cue=TEXT, answer_scope=TEXT,
                requirement=enum("required", "optional", "undecided"),
                relation_ids=arr(TEXT, 1))
TARGET = obj(target_id=TEXT, title=TEXT, concept_ids=arr(TEXT, 1),
             relation_ids=arr(TEXT, 1), role=enum("root", "branch", "leaf"),
             reason=TEXT, evidence=REFS, directions=arr(DIRECTION, 1),
             importance=obj(structural=IMPORTANCE, exam=IMPORTANCE, clinical=IMPORTANCE))
REVIEW_SCHEMA = obj(
    schema_version=enum(SCHEMA_VERSION), lecture_id=TEXT, bank_sha256=HASH,
    hash_policy=enum(HASH_POLICY),
    scope=obj(label=TEXT, included=arr(TEXT, 1), excluded=arr(TEXT),
              reviewed=arr(TEXT), limitations=arr(TEXT), outside_list_review=TEXT),
    provenance=obj(status=enum("draft", "reviewed"), method=TEXT, reviewer=TEXT,
                   independent_points=enum("confirmed", "unverified", "derived"), notes=TEXT),
    sources=arr(SOURCE, 1),
    concepts=arr(obj(concept_id=TEXT, label=TEXT, parent_ids=arr(TEXT)), 1),
    relations=arr(obj(relation_id=TEXT, from_id=TEXT, to_id=TEXT,
                      kind=enum("classification", "causal", "comparison", "sequence",
                                "prerequisite", "association"), condition=TEXT,
                      evidence=REFS, review_status=enum("reviewed", "unreviewed"), reason=TEXT), 1),
    targets=arr(TARGET, 1),
    points=arr(obj(point_id=TEXT, text=TEXT, evidence=REFS, target_ids=arr(TEXT),
                   scope_status=enum("included", "excluded"), reason=TEXT), 1),
    mappings=arr(obj(question_id=TEXT, question_sha256=HASH, target_id=TEXT,
                     direction_id=TEXT, tested_relation_ids=arr(TEXT),
                     provided_relation_ids=arr(TEXT), explanation_relation_ids=arr(TEXT), reason=TEXT)),
    coverage=arr(obj(point_id=TEXT, status=enum("covered", "partial", "gap", "unknown", "excluded"),
                     confirmed_direction_ids=arr(TEXT), partial_direction_ids=arr(TEXT), missing_direction_ids=arr(TEXT),
                     unknown_direction_ids=arr(TEXT), reason=TEXT,
                     exclusion_basis={"type": ["string", "null"],
                                      "enum": [None, "out_of_scope", "duplicate", "non_retrievable"]}), 1),
)
SOURCES_SCHEMA = obj(schema_version=enum("learning-link-sources/1"),
                     sources=arr(obj(source_id=TEXT, path=TEXT, sha256=HASH), 1))

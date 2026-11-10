"""Cache administrator bank summaries by the database row's revision.

Overview requests always read current revision stamps and source filenames. Only
changed banks need their question data and the validation fields used by summary().
The original responses and complete review reports stay in the database.

The overview is a list of every lecture, so it leaves out the repair history
(`validation.revision`) that summary() gives the per-lecture admin views. Up to
2026-11-10 it carried that history for all 40 banks — 19 of the overview's 20 MB,
10–12 s per load in production — and the admin page renders nothing until the
overview arrives. The admin screen never read it; the per-lecture bank view still does.
"""

from collections import OrderedDict
from copy import deepcopy
from threading import RLock

from sqlalchemy import JSON, case, func, null, select, tuple_, type_coerce
from sqlalchemy.orm import Session

from app.models import Asset, Lecture, QuizBank
from app.routes.bank import summary

_LIMIT = 256
_cache: OrderedDict = OrderedDict()
_lock = RLock()

# Every validation key summary() reads except `revision` (see the module docstring).
VALIDATION_KEYS = ("pass", "publication", "coverage", "errors", "dropped")
# (type of a JSON value, aggregate key/value rows into one object) per dialect.
_JSON_FUNCS = {"postgresql": ("json_typeof", "json_object_agg"), "sqlite": ("json_type", "json_group_object")}


def _validation_subset(dialect: str):
    """Only the validation keys summary() reads, built from **one** pass over the document.

    `validation` is a `json` (not `jsonb`) column, so every `validation->'key'` makes
    Postgres decompress and re-parse the whole document. Review histories make one
    bank's validation 20 MB (2026-11-10). `json_each` walks the top level once; the
    large review keys are filtered out before anything leaves the database.
    Non-object documents (JSON null) yield NULL.
    """
    typeof, aggregate = _JSON_FUNCS.get(dialect, _JSON_FUNCS["postgresql"])
    entry = func.json_each(QuizBank.validation).table_valued("key", "value").alias("validation_entry")
    subset = (select(getattr(func, aggregate)(entry.c.key, entry.c.value))
              .where(entry.c.key.in_(VALIDATION_KEYS)).scalar_subquery())
    return type_coerce(case((getattr(func, typeof)(QuizBank.validation) == "object", subset), else_=null()), JSON)


def _summary_rows(keys, dialect: str = "postgresql"):
    # Extract JSON fields in the database rather than transferring the full validation
    # document (including large conflict/evidence review histories) to the API.
    fields = (
        QuizBank.subject, QuizBank.run_id, QuizBank.status, QuizBank.build_id,
        QuizBank.open_to_students, QuizBank.share_url, QuizBank.conversation_url,
        QuizBank.linked_at, QuizBank.built_at, QuizBank.responded_at,
        QuizBank.prompt_version, QuizBank.message, QuizBank.bank,
    )
    return select(
        *fields,
        _validation_subset(dialect).label("validation_subset"),
        QuizBank.review["counts"].label("review_counts"),
    ).where(tuple_(QuizBank.subject, QuizBank.run_id).in_(keys))


def summaries(db: Session, lectures: list[Lecture]) -> dict[tuple[str, str], dict]:
    by_key = {(row.subject, row.run_id): row for row in lectures}
    if not by_key:
        return {}
    versions = db.execute(select(QuizBank.subject, QuizBank.run_id, QuizBank.updated_at)
                          .where(tuple_(QuizBank.subject, QuizBank.run_id).in_(by_key))).all()
    sources = {}
    for subject, run_id, filename in db.execute(select(Asset.subject, Asset.run_id, Asset.filename)
            .where(Asset.kind == "notes_current", tuple_(Asset.subject, Asset.run_id).in_(by_key))):
        sources.setdefault((subject, run_id), filename)

    bind = db.get_bind()
    result = {}
    # Coalesce simultaneous cold requests so they don't all download the same banks.
    with _lock:
        missing = {}
        for subject, run_id, updated_at in versions:
            key = (subject, run_id)
            cache_key = (bind, *key)
            version = (updated_at, sources.get(key))
            cached = _cache.get(cache_key)
            if cached is not None and cached[0] == version:
                _cache.move_to_end(cache_key)
                result[key] = deepcopy(cached[1])
            else:
                missing[key] = version
        if missing:
            for values in db.execute(_summary_rows(missing, bind.dialect.name)).mappings():
                values = dict(values)
                validation = values.pop("validation_subset") or {}
                # Keep absent/null optional JSON fields equivalent to the original
                # summary reader's defaults, without attaching this object to a session.
                validation = {key: value for key, value in validation.items()
                              if key in VALIDATION_KEYS and value is not None}
                review_counts = values.pop("review_counts")
                row = QuizBank(**values, validation=validation, review={"counts": review_counts})
                key = (row.subject, row.run_id)
                data = summary(db, by_key[key], row, is_admin=True)
                data.pop("revision", None)
                _cache[(bind, *key)] = (missing[key], deepcopy(data))
                _cache.move_to_end((bind, *key))
                result[key] = data
                while len(_cache) > _LIMIT:
                    _cache.popitem(last=False)
    return result

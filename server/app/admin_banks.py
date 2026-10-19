"""Cache administrator bank summaries by the database row's revision.

Overview requests always read current revision stamps and source filenames. Only
changed banks need their question data and the validation fields used by summary().
The original responses and complete review reports stay in the database.
"""

from collections import OrderedDict
from copy import deepcopy
from threading import RLock

from sqlalchemy import select, tuple_
from sqlalchemy.orm import Session

from app.models import Asset, Lecture, QuizBank
from app.routes.bank import summary

_LIMIT = 256
_cache: OrderedDict = OrderedDict()
_lock = RLock()


def _summary_rows(keys):
    # Extract JSON fields in Postgres rather than transferring the full validation
    # document (including large conflict/evidence review histories) to the API.
    fields = (
        QuizBank.subject, QuizBank.run_id, QuizBank.status, QuizBank.build_id,
        QuizBank.open_to_students, QuizBank.share_url, QuizBank.conversation_url,
        QuizBank.linked_at, QuizBank.built_at, QuizBank.responded_at,
        QuizBank.prompt_version, QuizBank.message, QuizBank.bank,
    )
    validation_keys = ("pass", "publication", "coverage", "revision", "errors", "dropped")
    return select(
        *fields,
        *(QuizBank.validation[key].label(f"validation_{key}") for key in validation_keys),
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
            for values in db.execute(_summary_rows(missing)).mappings():
                values = dict(values)
                validation = {key.removeprefix("validation_"): values.pop(key)
                              for key in list(values) if key.startswith("validation_")}
                # Keep absent/null optional JSON fields equivalent to the original
                # summary reader's defaults, without attaching this object to a session.
                validation = {key: value for key, value in validation.items() if value is not None}
                review_counts = values.pop("review_counts")
                row = QuizBank(**values, validation=validation, review={"counts": review_counts})
                key = (row.subject, row.run_id)
                data = summary(db, by_key[key], row, is_admin=True)
                _cache[(bind, *key)] = (missing[key], deepcopy(data))
                _cache.move_to_end((bind, *key))
                result[key] = data
                while len(_cache) > _LIMIT:
                    _cache.popitem(last=False)
    return result

"""강의별 족보 풀이 자료(jokbo-solve/1). 원문·정답은 족보 그대로, 해설은 따로 얹는다."""
from .solve import (
    ANSWER_STATUSES,
    EXPLAIN_SCHEMA,
    SCHEMA,
    SECTION_KINDS,
    JokboSolveError,
    answer_status,
    validate_explain,
    validate_lecture,
)

__all__ = [
    "ANSWER_STATUSES", "EXPLAIN_SCHEMA", "SCHEMA", "SECTION_KINDS",
    "JokboSolveError", "answer_status", "validate_explain", "validate_lecture",
]

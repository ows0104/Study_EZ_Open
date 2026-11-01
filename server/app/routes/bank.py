"""Stable Bank API entry point. Read bank_api/CLAUDE.md for responsibility ownership.

Existing Python imports remain available; new code should use the owning module.
HTTP handlers, models, access checks, and study policy retain their behavior.
"""

from fastapi import APIRouter

from app import study_engine as engine

from app.preview_links import share_url as valid_share_url

from .bank_api import publication, common, presentation, feedback, editing, catalog, state, study, personal

from .bank_api.publication import (
    ResponseFileIn, ResponseIn, put_bank_response, get_bank_response, get_bank_source_context,
    BankLinksIn, put_bank_links, SharedResponseIn, get_bank_shared_source,
    put_bank_shared_response, GeneratedResponseIn, put_generated_response, BankIn, put_bank,
    request_bank_audit, request_runner_bank_audit, OpenIn, delete_bank, put_bank_open,
    get_bank_admin, COMPLETE_MARK,
)

from .bank_api.common import (
    _iso, _save_share_link, bank_sources, exam_date_for, _bank_or_404, _usable, summary,
    SOURCE_KINDS,
)

from .bank_api.presentation import (
    _public, _served_question, _slide_url, _slides, _jokbo_slides, _answer, ANSWER_FIELDS,
)

from .bank_api.feedback import (
    bank_feedback, FeedbackStatusIn, set_bank_feedback_status, FeedbackIn, post_bank_feedback,
    FEEDBACK_CATEGORIES, FEEDBACK_STATUSES,
)

from .bank_api.editing import (
    bank_review, BankCardIn, edit_bank_card,
)

from .bank_api.catalog import (
    download_bank_anki, read_bank, read_bank_catalog, read_catalog_answer, ExcludedDecisionIn,
    decide_excluded,
)

from .bank_api.state import (
    _study_bank, _load_state, _save,
)

from .bank_api.study import (
    StartIn, start_bank_session, EndIn, end_bank_session, next_bank_question,
    _next_bank_question, TokenIn, PriorityIn, set_bank_priority, SuspensionIn,
    set_bank_suspension, show_bank_options, prepare_bank_answer, RevealIn, reveal_bank_answer,
    BatchLectureIn, RateIn, _advance_token, _draw_entries, _draw_context, _seal_draw,
    _reviewed_state, rate_bank_answer, undo_bank_answer, BatchIn, BatchUndoIn, NextPreviewIn,
    prepare_next_bank_question, BufferPreviewIn, prepare_bank_buffer, _batch_entries,
    _refresh_batch_entry, _batch_undo, _batch_reply, next_batch_question, _next_batch_question,
    undo_batch_question, end_batch_session,
)

from .bank_api.personal import (
    _personal_source, read_personal_question, PersonalEditIn, PersonalQuestionIn,
    add_personal_question, personal_question_slides, delete_personal_question,
    save_personal_question,
)

router = APIRouter()

router.include_router(feedback.router)

router.include_router(catalog.router)

router.include_router(study.router)

router.include_router(personal.router)

admin_router = APIRouter()

admin_router.include_router(publication.admin_router)

admin_router.include_router(feedback.admin_router)

admin_router.include_router(editing.admin_router)

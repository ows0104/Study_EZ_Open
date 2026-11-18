"""Single registration point for usage collection, names, units and automatic UI.

Add an Action and its source when adding a product action; the admin UI consumes
catalog() and never maintains a separate action list. See development/usage-actions.
"""
from __future__ import annotations

from dataclasses import dataclass

ACTION_GROUPS = [
    {"key": "personal", "label": "대화 만들기·링크 저장"},
    {"key": "links", "label": "링크 열기"},
    {"key": "quizzes", "label": "퀴즈 풀이"},
    {"key": "records", "label": "회독·메모"},
    # 파일 요청은 「누른 화면이 무엇을 하려고 자료를 받았나」로 가른다(file_requests.FilePurpose).
    # 목적을 모르는 것은 2026-11-02 목적 구분 전의 기록뿐이다 — 칸 전체가 미상이 아니다.
    {"key": "files", "label": "자료 첨부·받기"},
]


@dataclass(frozen=True)
class Action:
    key: str
    label: str
    group: str
    summary_path: tuple[str, ...]
    detail_path: tuple[str, ...] = ()
    time_path: tuple[str, ...] = ()
    summary_unit: str = "강의"
    detail_unit: str = "회"
    file_purpose: str | None = None
    preview_kind: str | None = None
    grades_path: tuple[str, ...] = ()


ACTIONS = (
    *(Action(code, label, 'quizzes', (field,), (field, 'count'), (field, 'lastAt'), '작업', '작업')
      for code, label, field in (
          ('root_start', 'Main Quiz 시작·재개 저장', 'rootStarts'),
          ('root_attempt', 'Main Quiz 시도 후 답 확인 저장', 'rootAttempts'),
          ('root_rate', 'Main Quiz 자기평가 저장 (취소 별도)', 'rootRatings'),
          ('root_undo', 'Main Quiz 자기평가 취소', 'rootUndos'),
          ('root_tier', 'Main Quiz 내 중요도 변경 저장', 'rootTiers'),
          ('root_generation', 'Main Quiz 생성 요청 저장', 'rootGenerations'),
          ('root_generated', 'Main Quiz 생성·검수 게시 완료', 'rootGenerated'),
          ('root_skip', 'Main Quiz 문제 보류', 'rootSkips'),
          ('root_exclude', 'Main Quiz 문항 제외', 'rootExcludes'),
          ('root_mine', 'Main Quiz 내 문제 저장·삭제', 'rootMine'),
          ('root_memo', 'Main Quiz 뒷면 메모 저장', 'rootMemos'),
          ('root_map_view', '개념 지도 열기 (강의·하루에 한 번)', 'rootMapViews'),
      )),
    # jokbo_mark 한 줄 = 족보 한 문항을 푼 사람(마지막으로 푼 때). 같은 문항을 다시 풀어도 한 줄이다.
    Action('jokbo_answer', '족보 퀴즈 풀이', 'quizzes', ('jokboAnswers',),
           ('jokboAnswers', 'count'), ('jokboAnswers', 'lastAt'), '문항', '문항'),
    Action('connection_save', '연결 학습 저장 (이동·열람·자기확인)', 'quizzes', ('connectionSaves',),
           ('connectionSaves', 'count'), ('connectionSaves', 'lastAt'), '작업', '작업'),
    # bank_feedback 한 줄 = 「문제 수정·제보」 저장 한 번(기존 은행·Main-Quiz 공통). 되돌리기는 줄을 남기지 않는다.
    Action('question_report', '문제 수정·제보 저장', 'quizzes', ('questionReports',),
           ('questionReports', 'count'), ('questionReports', 'lastAt'), '건', '건'),
    # 만들기는 버튼을 누른 시도다. 확장이 첨부·전송을 끝냈는지는 모른다(링크 저장이 따로 있다).
    Action("personal_preview_create", "개인 예습 대화 만들기 시도", "personal", ("previewCreates",),
           ("previewCreates", "count"), ("previewCreates", "lastAt"), preview_kind="create"),
    Action("shared_preview_create", "공통 예습 대화 만들기 시도 (관리자)", "personal", ("sharedCreates",),
           ("sharedCreates", "count"), ("sharedCreates", "lastAt"), preview_kind="screate"),
    Action("personal_review_create", "개인 복습 대화 만들기 시도", "personal", ("reviewCreates",),
           ("reviewCreates", "count"), ("reviewCreates", "lastAt"), preview_kind="rcreate"),
    # 관리자가 공통 대화를 만들면 그 대화 주소가 만든 사람의 개인 예습 링크로도 저장된다(UserPreview).
    Action("personal_preview_saved", "개인 예습 링크 저장", "personal", ("previewSaves",),
           ("preview",), ("previewSavedAt",), detail_unit="개"),
    Action("personal_review_saved", "개인 복습 링크 저장", "personal", ("reviewSaves",),
           ("review",), ("reviewSavedAt",), detail_unit="개"),
    Action("shared_preview_open", "공통 예습 링크 열기", "links", ("opens", "share"),
           ("opens", "share"), ("opensAt", "share"), preview_kind="share"),
    Action("personal_preview_open", "개인 예습 링크 열기", "links", ("opens", "mine"),
           ("opens", "mine"), ("opensAt", "mine"), preview_kind="mine"),
    Action("personal_review_open", "개인 복습 링크 열기", "links", ("reviewOpens",),
           ("reviewOpens", "count"), ("reviewOpens", "lastAt"), preview_kind="rmine"),
    Action("pre_quiz_answer", "예습 퀴즈 풀이", "quizzes", ("quizzes", "pre"),
           ("pre", "cards"), ("quizLastAt", "pre"), "문항", "문항", grades_path=("pre", "grades")),
    Action("main_quiz_answer", "복습 퀴즈 풀이 (기존)", "quizzes", ("quizzes", "main"),
           ("main", "cards"), ("quizLastAt", "main"), "문항", "문항", grades_path=("main", "grades")),
    Action("bank_quiz_answer", "복습 퀴즈 풀이 (복습 카드)", "quizzes", ("quizzes", "bank"),
           ("bank", "cards"), ("quizLastAt", "bank"), "문항", "문항", grades_path=("bank", "grades")),
    # note_read 한 줄 = 강의록 1회독. 지우면 줄이 사라지므로 지금 남아 있는 회독만 센다.
    Action("note_read", "강의록 회독 기록 (지운 것 제외)", "records", ("noteReads",),
           ("noteReads", "count"), ("noteReads", "lastAt"), "회", "회"),
    # lecture_memo 는 강의마다 한 줄이고 마지막 저장 시각만 남는다.
    Action("lecture_memo", "강의 메모 저장 (마지막 저장 기준)", "records", ("memos",),
           ("memo", "count"), ("memo", "lastAt"), detail_unit="개"),
    *(Action(f"file_{purpose}", label, "files", ("fileRequests", purpose), file_purpose=purpose)
      for purpose, label in (
          ("download", "자료 직접 받기"), ("view", "자료 브라우저로 열기"),
          # 대화 만들기를 누르면 화면이 자료마다 서명 링크를 받아 확장에 넘긴다. 그 받은 기록이다.
          ("preview_attach", "예습 대화 만들기 — 작년 필기·족보 첨부"),
          ("review_attach", "복습 대화 만들기 — 올해 필기·족보 첨부"),
          ("quiz_attach", "퀴즈 만들기 — 자료 첨부"),
          ("unknown", "목적 기록 전 요청 (2026-11-02 이전)"),
      )),
)


def catalog():
    return [{"key": a.key, "label": a.label, "group": a.group,
             "summaryUnit": a.summary_unit, "detailUnit": a.detail_unit,
             "filePurpose": a.file_purpose} for a in ACTIONS]


def _read(row, path):
    for field in path:
        row = row[field]  # Missing collection paths must fail tests, not silently disappear.
    return row


def collect(row, *, detail=False):
    result = {}
    for action in ACTIONS:
        if detail and action.file_purpose is not None:
            files = [f for f in row["fileRequests"] if f["purpose"] == action.file_purpose]
            metric = {"count": sum(f["count"] for f in files),
                      "lastAt": max((f["lastAt"] for f in files), default=None)}
        else:
            metric = {"count": int(_read(row, action.detail_path if detail else action.summary_path)),
                      "lastAt": _read(row, action.time_path) if detail and action.time_path else None}
        if detail and action.grades_path:
            metric["grades"] = _read(row, action.grades_path)
        result[action.key] = metric
    return result

# Quiz Bank API 읽기 지도

2026-11-11부터 Quiz Bank는 legacy다. 이 API는 `?legacy=1` 화면·관리자 도구·기록 보존을 위해 남는다.
사이트 학습률은 Main-Quiz(`app/root_learning/score.py`)다.

부모 server/CLAUDE.md와 docs/development/README.md의 보존·승인 절차를 따른다.
기존 app.routes.bank는 router 조립과 Python 호출자 호환 진입점이다.
새 구현·mock은 실제 소유 모듈을 참조한다. 다른 책임 파일 전체를 먼저 읽을 필요는 없다.

| 작업 | 시작 파일 | 관련 검사 |
|---|---|---|
| 응답 수집·러너 업로드·공개·보강 | publication.py | bank_publication, bank_response, bank_coverage, bank_timeline |
| 관리자 문항 검토·수정 | editing.py | bank_card, bank_edit, bank_review |
| 학생 신고·관리자 처리 | feedback.py | bank_feedback |
| 학생 요약·문항 목록·제외 문항·Anki | catalog.py | bank_catalog, bank_excluded, bank_anki |
| 개인 문항·개인 수정 | personal.py | bank_personal |
| 문항/정답 응답·근거 슬라이드 | presentation.py | bank_slides, bank_buffer, matching_presentation |
| 학습 상태 읽기·저장 | state.py | study_retention, bank_coverage, bank_advance |
| 세션·다음 문항·평가·undo·모아풀기 | study.py | bank, prepared_selection_api, question_order_api |
| 요약·은행 접근·자료 목록·시험일 | common.py | admin_egress, bank_timeline, lecture_mastery |

의존성은 common → state/presentation → HTTP 책임 파일 방향으로 읽는다.
presentation은 저장소와 표시만 다루며 state를 import하지 않는다.
실제 학습 정책은 app/study_engine, 보존은 app/bank_retention·study_retention에 있다.
단일/모아풀기와 평가 후 다음 문항은 상호 호출이 있어 study.py에 함께 둔다.

API 계약 변경 시 test_route_contract와 호출자 검사를 실행한다. 구조 분리에서는
OpenAPI 요청 모델 이름도 유지한다. feedback.FeedbackIn의 __module__은 기존 공개
스키마 이름을 지키기 위한 고정 메타데이터다. 해당 파일에서 지연 문자열 annotation을
켜면 Pydantic이 호환 진입점에서 타입을 찾다가 실패할 수 있으므로 스키마 생성도 검사한다.
mock은 함수가 참조하는 위치에 둔다(예: presentation.ObjectStorage, study._next_bank_question).

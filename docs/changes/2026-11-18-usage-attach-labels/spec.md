# 이용현황 자료 첨부 칸 정리와 빠진 행동 기록 — 설계

## 요구사항과 수용 기준
- `ACTION_GROUPS`: personal → 「대화 만들기·링크 저장」, files → 「자료 첨부·받기」. 어떤 칸·행동 이름에도 「미상」이 없다.
- 파일 목적 이름: download 「자료 직접 받기」, view 「자료 브라우저로 열기」, preview_attach 「예습 대화 만들기 — 작년 필기·족보 첨부」,
  review_attach 「복습 대화 만들기 — 올해 필기·족보 첨부」, quiz_attach 「퀴즈 만들기 — 자료 첨부」, unknown 「목적 기록 전 요청 (2026-11-02 이전)」.
- 새 `preview_open.kind`(8자 칸): `screate` 공통 예습 대화 만들기, `rcreate` 개인 복습 대화 만들기, `rmine` 개인 복습 링크 열기.
  `PREVIEW_ACTION_KINDS`에 더하고 `PREVIEW_OPEN_KINDS`(share/mine)와 `opensSince`는 그대로.
- 새 행동: shared_preview_create, personal_review_create, personal_review_open, personal_review_saved,
  root_skip, root_exclude, root_mine, root_memo, root_map_view. 요약은 강의 수(링크·만들기)·작업 수(Main-Quiz), 상세는 횟수·마지막 시각.
- 웹: 공통 대화 만들기 시작 시 `screate`, 복습 대화 만들기 시작 시 `rcreate`, 저장된 복습 개인 대화 링크 클릭 시 `rmine`.

## 책임·입출력 계약·오류 상태
- 기록은 기존 `POST /lectures/{s}/{r}/preview-open`(204, 실패해도 화면 동작을 막지 않음)을 그대로 쓴다.
- `/api/admin/usage` 행에 `sharedCreates`·`reviewCreates`·`reviewOpens`·`reviewSaves`·`rootSkips` 등 필드가 더해지고,
  `/api/admin/usage/{id}` 강의 행에 같은 이름의 {count,lastAt}과 `review`·`reviewSavedAt`이 더해진다. 기존 필드는 그대로.
- `lastAt`(마지막 활동)에 `user_review.updated_at`이 더해진다.
- 개인 대화 URL은 응답에 나오지 않는다.

## 호환성과 데이터 보존
- DB 스키마·기존 행 변경 없음. 새 kind는 기존 칸 길이(8자) 안이다.
- `root_event` 중 publication(러너)·focus·optional(과목 설정)·map(지도 펼침)은 여전히 세지 않는다.
- 과거의 공통 대화 만들기·복습 만들기·복습 열기는 기록이 없어 소급하지 않는다(화면에 2026-11-18부터라고 적는다).
- 관리자가 만든 공통 대화가 만든 사람의 개인 예습 링크로도 저장되는 기존 동작은 그대로 두고 화면에 적는다.

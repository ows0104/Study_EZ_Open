# 이용현황 자료 첨부 칸 정리와 빠진 행동 기록 — 배포 준비

## 코드 리뷰·검증 결과
- server: `-m tests usage`(usage 회귀·usage_actions 28개·file_request_purpose) · route_contract · smoke 통과. 새 검사: screate·rcreate·rmine 갈래 분리,
  복습 링크 저장 요약·상세, 복습 URL 비노출, Main-Quiz 갈래 5개 집계와 publication·focus·map 제외, 칸·행동 이름에 「미상」 없음.
- web: typecheck·production build 통과. `node --test tests/preview-actions.test.cjs` 21/21.
- 브라우저(헤드리스, tests/review-actions.html): 공통 대화 만들기 → `screate`+preview_attach, 개인 예습 만들기 → `create`+preview_attach,
  복습 개인 대화 만들기 → `rcreate`+review_attach. 실제 관리 화면은 운영 DB 없이 열 수 없어 보지 않았다 — 표는 API 카탈로그를 그대로 그린다.
- 리뷰: 새 kind는 `preview_open.kind` 8자 안. 옛 서버는 모르는 kind를 조용히 버린다(기록 누락만). 기존 필드·숫자 변화 없음.

## 배포 대상 버전·순서·데이터 변경
- master 병합 → 자동 배포(API → Pages). DB 스키마·데이터 변경 없음.

## 배포 후 확인·롤백·필요한 사람 승인
- 확인: 관리 → 이용현황 마지막 칸 머리 「자료 첨부·받기」, 「예습 대화 만들기 — 작년 필기·족보 첨부」 이름, 펼친 상세의 복습 링크 저장 줄.
- 롤백: git revert. 새로 쌓인 screate·rcreate·rmine 행은 옛 코드가 무시한다.
- master 병합(=배포)은 사용자 확인 뒤.

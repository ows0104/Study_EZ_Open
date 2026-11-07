# 자유 노트 — 배포 준비

## 코드 리뷰·검증 결과
- 서버: `server/tests/test_notes.py` 통과(본인 노트만·남의 id 404, 태그 공백/중복 정리, 블록 11종 외 422,
  제목 200·태그 30×40·블록 html 20,000자 제한, 사용자당 500개 409, 최근 수정 순, 삭제, 미승인 403·미로그인 401, sqlite에서도 UTC 시각).
  `test_route_contract` 경로 170개 일치. 전체 서버 검사 결과는 PR 본문에 적는다.
- 웹: `npm run typecheck`, `npm run build` 통과.
- 로컬 실행 확인(격리 sqlite `server/local_test_data/notes.db`, local-test 토큰, 운영 DB·저장소 미사용):
  새 노트 → 제목·`##`/`-`/`[]`/`/콜` 블록·`**굵게**` 변환, 글자색(빨강)·배경색(노랑)·「기본」 되돌리기, 태그 추가(Enter·쉼표)·중복 무시,
  할 일 체크, 블록 메뉴 삭제, 새로고침 후 그대로 복원, 노트 전환, 노트 삭제(서버 목록에서도 사라짐).
- 저장 HTML 정리: `<img onerror>`·`<script>`·`<svg>`·`on*` 속성·`javascript:` 링크·`position/background-image` 스타일이 제거되고
  편집기 서식(b·code·span 색·밑줄 등)은 남는 것을 확인. 붙여넣기는 서식 없는 글.
- 기록 메모: `state.json`의 checks 앞 5건(서버 4·웹 1)은 Git Bash가 `cmd /c`를 경로로 바꿔 실제 검사를 실행하지 못한 기록이다(로그에 cmd 머리말뿐).
  뒤의 3건(notes·route_contract·web)이 실제 실행 기록이다.
- 리뷰에서 고친 것: sqlite가 시간대를 버려 수정 시각이 9시간 어긋나던 문제(서버가 UTC 표시를 붙임), SVG 안 스크립트 글이 남던 정리 누락.
- 남은 위험: 여러 탭에서 같은 노트를 동시에 고치면 마지막 저장이 이긴다(병합 없음). 이용현황 행동 등록은 하지 않았다(intent 참고).

## 배포 대상 버전·순서·데이터 변경
- DB: 새 표 `user_note`(+RLS) 하나. 기존 표·칼럼 변경 없음.
- 순서: 운영 DB에 `user_note` 생성(`python -m app.cli init-db`의 create_all, postgres에서 RLS 자동 활성) → master 병합(API 자동 배포 → 같은 SHA로 Pages).
- 표 없이 API가 먼저 배포되면 `/api/me/notes`만 500이고 다른 화면은 영향 없다.

## 배포 후 확인·롤백·필요한 사람 승인
- 필요 승인: 운영 DB 표 생성, master 병합(=운영 배포). 이번 구현 승인 범위에 포함되지 않는다.
- 확인: `/api/health` revision, `/notes` 열기·새 노트 저장·새로고침 복원, 다른 계정에서 안 보임.
- 롤백: PR revert. `user_note` 표는 남겨도 다른 기능에 영향 없다(지우려면 별도 승인).

# 퀴즈 전체 화면 버튼 — 배포 준비

## 코드 리뷰·검증 결과
- `npm run typecheck`(development.py verify, exit 0), `npm run build` 통과.
- headless Chrome(playwright-core, channel chrome)으로 임시 고정물에서 StudyNav를 띄워 확인(고정물은 커밋하지 않음):
  클릭 진입 → `전체 화면 끝`·aria-pressed=true, 다시 클릭 해제, `exitFullscreen`(Esc 경로) 반영,
  학습 화면끼리 이동 시 유지, 캘린더 이동(StudyNav 언마운트) 시 해제, `fullscreenEnabled=false`면 버튼 없음, 페이지 오류 0.
- 데스크톱 앱 내장 브라우저 창은 전체 화면 권한을 막아(`Permissions check failed`) 그곳에서는 확인 불가 — 기능 결함 아님.
- 실제 로그인 화면(운영 데이터)에서의 확인은 하지 않았다.

## 배포 대상 버전·순서·데이터 변경
웹만. 서버·DB·러너 변경 없음. master 병합 시 일반 자동 배포(API 먼저, 같은 SHA 뒤 Pages).

## 배포 후 확인·롤백·필요한 사람 승인
master 병합(=운영 배포)은 별도 사람 승인. 배포 뒤 Main-Quiz 풀이 화면에서 버튼 동작 확인.
롤백: 커밋 revert PR 또는 Pages 이전 배포 Rollback.

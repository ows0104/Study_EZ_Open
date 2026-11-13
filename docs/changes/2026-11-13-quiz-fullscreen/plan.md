# 퀴즈 전체 화면 버튼 — 구현 계획

## 변경 범위·대상 파일·순서
1. 새 `web/src/FullscreenButton.tsx` — 버튼·`fullscreenchange` 구독·언마운트 시 해제.
2. `web/src/StudyNav.tsx` — 오른쪽에 `FullscreenButton`과 기존 `FeedbackButton`을 함께 둔다.
3. `web/src/styles/base.css` — `.study-nav` 근처에 오른쪽 묶음 간격 한 줄.

## 검사 명령과 성공 조건
- `web`: `npm run typecheck`, `npm run build` 통과.
- 로컬 개발 서버 미리보기에서 Main-Quiz 화면 버튼 클릭 → 전체 화면 진입·글자 변경, 다시 클릭/Esc 해제,
  캘린더로 이동 시 해제 확인. 미리보기 환경이 전체 화면을 막으면 그 사실을 실패와 구분해 기록한다.

## 위험·복원·승인할 범위
- 위험 낮음: 표시 전용, 데이터 변경 없음. 복원은 커밋 revert.
- 승인할 범위: 위 세 파일과 이 작업 폴더의 로컬 구현·검사, PR 생성까지.
  master 병합(=자동 배포)은 별도 승인.

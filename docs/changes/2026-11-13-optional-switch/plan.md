# Optional 제외 스위치 디자인 — 구현 계획

## 변경 범위·대상 파일·순서
- `web/src/bank/StudyOverview.tsx`: 버튼 마크업을 스위치로.
- `web/src/bank/overview.css`: 스위치 스타일.

## 검사 명령과 성공 조건
- `npm --prefix web run typecheck`, `npm --prefix web run build` 통과, PR CI 통과.
- 로컬 격리 DB 브라우저에서 켜짐/꺼짐 모양과 카드 수 변화 확인.

## 위험·복원·승인할 범위
- 웹 표시만. 복원은 PR revert.
- 승인 범위: 위 두 파일의 구현·검사·PR 생성. master 병합(=운영 배포)은 사용자 확인 후.

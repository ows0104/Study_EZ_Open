# Main-Quiz 개념 지도 바로 열기·화면 끝까지 쓰기 — 구현 계획

## 변경 범위·대상 파일·순서
1. `web/src/bank/RootLearning.tsx`: 지도 탭을 먼저 고르고 불러오는 중 상태를 둔다. 실패하면 되돌리고, 돌아가기는 `onBack`으로 넘긴다.
2. `web/src/bank/RootMap.tsx`: `onBack` 도구 버튼을 넣고, 아래 여백 0으로 맞춘다.
3. `web/src/bank/main-quiz.css`: 지도 화면에서 앱 본문 여백과 1100px 제한을 없애고, 틀 테두리를 없앤다. 크게 보기는 inset 0이다.
4. `web/tests/root-learning.tsx`·`root-learning.test.cjs`: 앱 틀을 넣고 네 변 여백 0을 확인한다. 문제 화면을 거치지 않는지도 본다.
5. 이 폴더의 `release.md`

## 검사 명령과 성공 조건
- typecheck 0, build 0
- root-ui 브라우저(격리 fixture SQLite·로컬 저장소) 전부 통과
- 실제 감염병리1 지도로 1600×900·1366×768·390×844를 확인한다.

## 위험·복원·승인할 범위
- 위험: 좌측 메뉴와 지도 사이에 틀 테두리가 없다. 메뉴의 오른쪽 경계선이 그 역할을 한다.
- 복원: 병합 커밋 revert.
- 승인: 사용자 지시(2026-11-09)가 구현 승인이다. 범위는 구현·검사·PR·master 병합이고, 서버·DB 변경은 없다.

# Main-Quiz 개념 지도 화면 정리 — 구현 계획

## 변경 범위·대상 파일·순서
1. `web/src/bank/RootMap.tsx`
   - 지우는 것: 머리말·안내·찾기·범례 줄·아래 접힘, 확대·끌기·휠·키 처리, ＋/－/전체 버튼
   - 바꾸는 것: 항상 맞춤(넘침 시 세로 스크롤), 틀 높이 측정, 겹침 패널(좌우 선택), 도구 막대 안 범례
2. `web/src/bank/main-quiz.css`: 틀·도구 막대·겹침 패널·스크롤 대체 스타일, 지도 화면의 아래 여백
3. `web/tests/root-learning.test.cjs`: 찾기·확대·틀 높이 단언을 새 수용 기준으로 바꾼다.
4. 이 폴더의 `release.md`

건드리지 않는 것: `RootLearning.tsx`, `GuidePage.tsx`, 서버·DB, `rootMapTree.ts`(#50).

## 검사 명령과 성공 조건
- `npm --prefix web run typecheck` 0
- `npm --prefix web run build` 0
- root-ui 브라우저(격리 fixture SQLite·로컬 저장소): `root-learning`과 `main-quiz-map-tree`가 모두 통과
- 실제 데이터: 감염병리1 map-tree-26110803 지도 응답을 1600×900·1366×768·390×844에서 스크린샷으로 확인한다.

## 위험·복원·승인할 범위
- 위험: 작은 화면에서는 글자가 작다. 0.5 하한과 세로 스크롤로 막고, 크게 보기를 둔다.
- 복원: 병합 커밋 revert.
- 승인: 사용자 지시(2026-11-09)가 구현 승인이다.
  - 범위는 위 파일의 구현·검사, 커밋·PR, master 병합(자동 배포)이다.
  - 서버·DB 변경이 없다.

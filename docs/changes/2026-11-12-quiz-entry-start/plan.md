# Main-Quiz 정리 화면 먼저·재개 카드 수·뒤로 — 구현 계획

## 변경 범위·대상 파일·순서
1. `web/src/bank/RootLearning.tsx` — 첫 불러오기 resume·autoStart 제거, 남은 수 읽기, 뒤로(`navigate(-1)` 또는 `/`).
2. `web/src/bank/RootToday.tsx` — `resumeCount`·`onBack`, 재개에도 배지.
3. `web/src/bank/StudyOverview.tsx` — ▶ 링크에서 `?start=1` 제거.
4. `web/src/bank/main-quiz.css` — kicker 안 뒤로 버튼 크기.
5. `web/tests/root-learning.test.cjs` — 새로고침 뒤 「오늘 학습 재개 카드 3개」·문제 화면 없음 확인, 이어 풀기는 `resume()` 클릭.

## 검사 명령과 성공 조건
- `node web/node_modules/typescript/bin/tsc -b web/tsconfig.json --noEmit` 통과.
- `python scripts/check_root_learning.py --check root-ui`(소유 fixture 8027/5193, 격리 DB) 8개 통과, 화면 resume-start.png 확인.
- `npm --prefix web run build` 통과.

## 위험·복원·승인할 범위
- 위험: 풀이 중 새로고침이 한 번 클릭을 더 요구한다(사용자 요청대로).
- 복원: git revert. 데이터 변경 없음.
- 승인 범위: 위 웹 파일과 검사. 서버·DB 변경 없음.

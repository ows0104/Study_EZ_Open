# Main-Quiz 모아풀기 — 구현 계획

## 변경 범위·대상 파일·순서
1. `web/src/bank/useRootFrames.ts`: `warm`을 export(동작 변화 없음).
2. 새 `web/src/bank/RootBatch.tsx`: 시작 화면·강의별 회차·섞기·되돌리기 스택·마침 화면(spec R2~R10). 새 `root-batch.css`.
3. `web/src/App.tsx`: `/study/mix` 경로 한 줄(lazy).
4. `web/src/bank/StudyOverview.tsx`: Main-Quiz 행 `batch: mainQuiz`. 설명 주석 갱신.
5. `web/src/bank/BankBatch.tsx`: `onStart` → `/study/mix?l=…`로 이동.
6. 검사: 새 `server/tests/serve_main_quiz_batch_fixture.py`(격리 sqlite, 합성 두 강의),
   새 `web/tests/root-batch.html·tsx·test.cjs`, `scripts/check_root_learning.py`에 `root-batch` 이름 추가.
   `web/tests/study-management.test.cjs`의 옛 모아풀기 끝부분을 새 주소 이동으로 고친다.

## 검사 명령과 성공 조건
- `npm --prefix web run typecheck` 통과.
- `npm --prefix web run build` 통과(종료 2는 prepare-prompts 재기록 — 메모대로 한 번 더, 지문 파일은 restore).
- `python scripts/check_root_learning.py root-batch`: 두 강의 섞기 순서, 되돌리기가 강의를 건너 돌아감, 마침 화면, 콘솔 오류 0.
- `python scripts/check_root_learning.py root-ui`: 강의 하나 Main-Quiz 기존 검사 회귀 없음.
- study-management 검사(목록 체크 → 막대 → 새 주소).

## 위험·복원·승인할 범위
- 사용자의 작업 요청 발언이 구현 승인이다(개발 루프 3). 운영 DB 쓰기·공개 범위 변경·학습 기록 변경이 없어 따로 묻지 않는다.
- 위험: 여러 회차를 한 쓰기 줄로 보내므로 한 강의의 409가 뒤의 다른 강의 요청까지 보존·정지시킨다. 강의 화면과 같은 보존 규칙이고 기록은 잃지 않는다.
- 위험: RootSolve props를 바꾸는 진행 중 작업(선행 정리·내 문제·선지 접기)과 병합 순서 — 나중 쪽이 rebase.
- 복원: 웹만 바뀐다. git revert와 이전 Pages 배포로 되돌린다.

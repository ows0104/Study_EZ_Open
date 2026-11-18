# 모아풀기 시작 화면 선택지 — 구현 계획

## 변경 범위·대상 파일·순서
브랜치 `claude/multi-lecture-review`는 `feat/main-quiz-batch`(#219) 위다. #219 병합 뒤 master로 rebase한다.
1. 새 `server/app/root_learning/mix.py`: 과제 분류(R1), 고르기(R2), 강의 안 순서(R4: 문서 순서 / 선행을 지키는 seed 섞기).
2. `server/app/routes/root_learning.py`: `GET …/mix`, `POST …/mix-sessions` 추가(파일 끝), `today_stream`에서 `state.mix` 회차 제외(한 줄).
3. `server/tests/test_root_mix.py`: 분류·두 체크 조합·중요도·섞기의 선행 보존·재개·멱등·오늘 흐름 분리. `test_route_contract.py`에 두 경로.
4. `web/src/types/rootLearning.ts`: 응답 타입.
5. `web/src/bank/RootBatch.tsx`: 시작 화면 선택지(R3·R5·R6), 시작은 `mix-sessions`, 다음 강의 고르기를 순서대로/섞어서로(R4). `root-batch.css`.
6. #219 검사 갱신: `server/tests/serve_main_quiz_batch_fixture.py`·`web/tests/root-batch.*`를 새 시작 화면으로.

## 검사 명령과 성공 조건
- 서버: `server/`에서 `-m tests root_mix`, `root_api`, `root_focus`, `root_photo_order`, `route_contract` 통과(격리 sqlite).
- 웹: typecheck·build 통과.
- 브라우저: `python scripts/check_root_learning.py root-batch`(격리 fixture) — 선택지·수 갱신·강의별 칩·순서대로/섞어서·재개·Z.
  `root-ui` 회귀 없음. 390px 폭.

## 위험·복원·승인할 범위
- 승인 범위: 위 파일들의 로컬 구현·검사·Draft PR. master 병합(=자동 배포)은 별도 승인.
- 위험: 「기존 학습률 무시 + 미열람」은 강의마다 수백 문항이 될 수 있다. 문항 수는 시작 전에 보인다.
- 위험: #219 세션이 RootBatch.tsx를 더 고치면 충돌 — 대시보드 행에 적어 두었다.
- 복원: git revert. 서버를 되돌려도 `state.mix` 회차는 기록으로 남고 해가 없다(spec 호환성).

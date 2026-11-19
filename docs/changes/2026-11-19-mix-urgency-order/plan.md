# 모아풀기 복습 주기 이전 문제도 보기 — 구현 계획

## 변경 범위·대상 파일·순서
브랜치 `claude/mix-urgency-order`(master a55484c1, #228 포함).
1. `server/app/root_learning/mix.py`: 분류에서 「나중」 과제의 급함 값도 낸다. 묶음 순서(R2)와 묶음을 넘는 선행 정렬 함수.
2. `server/app/routes/root_learning.py`(mix 구역만): `mix_start`가 묶음 순서로 과제를 놓고 `state.mixPhases`를 저장, 응답·`GET …/mix` `open[]`에 `phases`.
3. `server/tests/test_root_mix.py`·`test_root_mix_v4.py`: 묶음 순서, 급함 순, 선행이 묶음을 넘어 앞, 재개 시 phases, 옛 회차 phases 없음.
4. `web/src/types/rootLearning.ts`·`web/src/bank/RootBatch.tsx`: 라벨(R1), `nextLane`이 묶음과 급함을 본다(R3), phases 없는 회차는 지금 규칙.
5. `web/tests/root-batch.test.cjs`: 라벨, 묶음 순서(복습 대상 → 미열람 → 나중) 강의 건너 확인.

## 검사 명령과 성공 조건
- 서버(`server/`): `-m tests root_mix`(두 파일), `root_api`, `root_focus`, `root_prereq`(#228 검사가 있으면), `route_contract` 통과.
- 웹: typecheck·build 통과.
- 브라우저: `check_root_learning.py --check root-batch` 통과, `--check root-ui` 회귀 없음.

## 위험·복원·승인할 범위
- 승인 범위: 위 파일들의 로컬 구현·검사·PR. master 병합(=자동 배포)은 별도 승인.
- 위험: 미열람·복습 대상 수가 많으면 ③(복습일 전)은 맨 끝이다 — 사용자가 고른 순서다.
- 복원: git revert. 데이터 변경 없음(회차 상태에 칸 하나).

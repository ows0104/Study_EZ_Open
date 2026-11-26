# 구현 계획

승인: 사용자 요청 자체가 이 범위의 수정 지시. master 병합(=자동 배포)은 별도 승인.

## 파일

1. `web/src/bank/BankQuestion.tsx`: `markChoices` prop — 점수 상자와 따로, 답을 본 뒤 선지 채점 표시를 켠다.
2. `web/src/bank/RootSolve.tsx`: `markChoices`를 넘긴다.

## 검사

- `npm --prefix web run typecheck` 통과.
- `QuestionBody`를 주관식 모드와 같은 prop으로 서버 렌더(esbuild): 정답을 고르면 `is-picked is-correct`,
  오답을 고르면 고른 것 `is-picked is-wrong`·정답 `is-missed`. 고치기 전 동작(`markChoices` 없음)은 `is-picked`만.
- 미실행: 서버 fixture가 필요한 Playwright 검사(`root-recall-choices`, `bank-interactions`), 실제 사이트 확인.

## 위험·복원

- 위험 낮음: 화면 표시만. 복원은 `git revert`.

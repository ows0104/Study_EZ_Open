# Main-Quiz 「선지 보기」 다시 접기 — 구현 계획

승인: 사용자 요청(2026-11-12) 자체가 이 범위의 구현 지시. master 병합(=자동 배포)은 별도 승인.

## 파일

1. `web/src/bank/RootSolve.tsx`: 선지 상태에 `seen`(한 번이라도 폈는지) 추가, `hideChoices()`,
   V 토글, 선지가 펴져 있을 때 Z 계열은 접기, 「선지 접기 V」 버튼, reveal의 `choicesShown`은 `seen`.
   보관값 `:choices`는 `shown`(펼침) / `seen`(봤지만 접힘).
2. `web/src/notices/GuidePage.tsx`: 사용법 한 줄.
3. `web/tests/root-choice-keys.tsx`: V 다시·Ctrl+Z·Z 접기, 한글 입력 V, 서버 되돌리기 없음, 접고 답 보기 시 `choicesShown`.

## 검사

- `web/`에서 `npx tsc -b --noEmit`.
- vite(5199) + `node --test tests/bank-interactions.test.cjs`.

## 위험·복원

- 위험 낮음: 화면 상태만. 복원은 `git revert`.

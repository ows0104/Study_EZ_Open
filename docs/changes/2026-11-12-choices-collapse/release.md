# Main-Quiz 「선지 보기」 다시 접기 — 검증

- `npx tsc -b --noEmit` 통과.
- `node --test tests/bank-interactions.test.cjs`(vite 5199, 운영 DB·API 미사용): 15/15 통과.
  `root-choice-keys`의 새 검사: 「선지 접기」 표시, V 다시 → 접힘·선택 비움, 한글 입력 V로 다시 폄,
  Ctrl+Z·Z → 접힘, 접기는 이벤트·서버 되돌리기 없음, 접고 답 보기 → `choicesShown: true`·응답 없음.
- 미확인: 실제 Main-Quiz 화면(운영 데이터)에서의 손 조작. 답을 연 뒤 선지 결과 표시는 기존 경로 그대로(`seen`이면 표시).

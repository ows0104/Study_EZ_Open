# 복습 퀴즈 객관식 선지 번호 표시와 1–4 키 선택 · 5 키 제외 — 구현 계획

## 변경 범위·대상 파일·순서

1. `server/app/root_learning/content.py`: `excluded_ids(events, revision)`, `availability`에 반영.
2. `server/app/routes/root_learning.py`: Action.kind 'exclude', act의 exclude 처리·건너뛰기.
3. `server/tests/test_root_exclude.py`: 제외 → 다음 과제, 계획에서 빠짐, Z 복구, 재요청 멱등, 판 범위.
4. `web/src/types/rootLearning.ts`, `web/src/bank/RootSolve.tsx`: 1–4 선택, 5·메뉴 제외.
   `web/src/bank/RootLearning.tsx`: 제외는 서버 확인 뒤 그린다(미리 받은 다음 과제 버림, Z용 화면 보관). 막힌 과제로 넘어갈 때도 서버를 기다린다.
   `web/src/bank/BankSolve.tsx`(옛 Quiz Bank): 같은 번호 머리표가 보이므로 답 보기 전 1–4 선택을 같이 단다. `5` 비활성화는 그대로.
5. `web/src/bank/BankQuestion.tsx`: 번호 머리표.
6. `web/src/notices/GuidePage.tsx`: 단축키 안내. 웹 검사 기대값 갱신.

## 검사 명령과 성공 조건

- server: `server/`에서 `.venv/Scripts/python.exe -m tests root` (격리된 로컬 테스트 DB).
- web: `npm --prefix web run typecheck`, `node --test web/tests/answerPoints.test.cjs web/tests/answer-readable.test.cjs`,
  새 픽스처 `web/tests/root-choice-keys.html`·`choice-explanations.html` ALL PASSED(`bank-interactions.test.cjs`에 등록).
- 실패·미실행은 release.md에 구분해 적는다.

## 위험·복원·승인할 범위

- 위험: 잘못 누른 제외는 회차 안 Z로만 복구(후속: 복원 화면). 해설 본문 글자와 번호 불일치.
- 복원: 커밋 되돌리기. 'exclude' 이벤트는 남지만 옛 코드는 무시한다.
- 승인 범위: 위 파일·검사·문서, PR 생성. master 병합(=운영 배포)은 따로 묻는다.

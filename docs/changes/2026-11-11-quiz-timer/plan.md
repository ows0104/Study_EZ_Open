# 복습 퀴즈 문항 타이머 — 구현 계획

## 변경 범위·대상 파일·순서
1. `web/src/bank/quizTimer.ts`(새 파일): `questionSeconds(format)`, `ANSWER_SECONDS=40`, 토글 저장, `useQuizTimer`.
2. `web/src/bank/RootSolve.tsx`: 머리에 토글·남은 초, 키 처리에 Tab, 만료 시 `reveal()` / `rate('Again')`.
3. `web/src/bank/main-quiz.css`: 남은 초·토글의 작은 규칙.
4. `web/src/notices/GuidePage.tsx`: Main-Quiz 안내에 타이머·Tab 한 줄.
5. `web/tests/root-learning.*`: 형식별 초와 만료 동작 검사 추가(가능한 범위).

## 검사 명령과 성공 조건
- `web`에서 `npm run typecheck`, `npm run build` 통과.
- `node --test web/tests/root-learning.test.cjs` 등 기존 Main-Quiz 화면 검사 통과.
- 로컬 미리보기로 토글·남은 초·Tab 일시정지·0초 동작을 확인한다(로컬 DB만 사용, 운영 DB 사용 금지).

## 위험·복원·승인할 범위
- 해설 0초 자동 Again은 실제 학습 기록에 남는다. 탭 숨김·창 열림·일시정지 중에는 흐르지 않게 막는다.
- 타이머가 켜진 동안 풀이 화면에서 Tab 포커스 이동이 막힌다(Shift+Tab은 유지).
- 복원: 이 브랜치의 커밋을 되돌리면 된다. 서버·DB 변경 없음.
- 승인 범위: 위 파일의 화면 변경과 로컬 검사. 운영 배포는 master 병합 시 기존 자동 배포 절차를 따른다.

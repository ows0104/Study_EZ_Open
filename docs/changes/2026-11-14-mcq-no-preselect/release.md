# 검증

- `npx tsc -b --noEmit` 통과.
- vite(5199, 운영 DB·API 미사용) 고정물을 브라우저 창에서 실행(이 PC에 playwright 없음):
  `root-choice-keys` 40/40 ALL PASSED(새 검사 4개 포함), `choice-explanations`·`root-conflict-badge` ALL PASSED.
- 미실행: `root-solve-bar`(브라우저 창이 숨겨져 애니메이션 프레임이 돌지 않음, 아래 바 위치 검사로 이번 변경과 무관).
  `choice-feedback`은 BankSolve 고정물로 테스트 목록에 없고 이번 변경 전부터 실패.
- 미확인: 운영 Main-Quiz 화면에서의 손 조작.

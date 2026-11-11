# Main-Quiz 관리자 출제를 버튼 하나로 — 구현 계획

## 변경 범위·대상 파일·순서
1. `web/src/bank/RootGenerationPanel.tsx`: 구조 Mode·입력 상태·파일 업로드·설정 접기를 지우고 `NEW_REQUEST`(map-tree/3 기본값) 하나로 보낸다.
   체크박스 하나(privatePilot), 버튼 아래 승인 안내, 이어 하기의 공개 범위 표시.
2. `web/src/bank/roots.css`: 버튼과 체크박스를 한 줄(좁으면 줄바꿈)로 세우는 규칙, 호출 상한 글씨를 작게.
3. `web/src/notices/GuidePage.tsx`: 관리자 출제 안내 문단을 지금 버튼에 맞게 고친다(옛 「뿌리 학습 자동전송」·「설정·기존 지도 사용」 문구 제거).
4. 테스트: `web/tests/main-quiz-generation-button.test.cjs`(구조 선택 검사 제거, 정확한 본문·체크박스·이전 판 무시 검사 추가),
   `web/tests/root-generation.test.cjs`·`main-quiz-generation-browser.test.cjs`(없어진 설정 대신 체크박스·새 본문).

## 검사 명령과 성공 조건
- `node --test web/tests/main-quiz-generation-button.test.cjs`: 전부 통과
- `npm --prefix web run typecheck`, `npm --prefix web run build`: 통과
- 로컬 미리보기(`web/tests/main-quiz-generation.html`)에서 데스크톱·390px 화면 확인, 가로 넘침 없음

## 위험·복원·승인할 범위
- 승인 근거: 사용자 요청 원문(2026-11-11 채팅, intent.md에 인용).
- 화면만 바뀌므로 DB·운영 데이터·생성기·러너는 바뀌지 않는다. 출제는 여전히 관리자가 강의마다 버튼을 눌러야 일어나고,
  그 클릭이 그 강의의 자료 전송·공개 승인이다(2026-11-09 결정). 기본 공개 범위가 「학생 공개」인 것은 이전과 같다.
- 되돌릴 때는 커밋을 revert한다. 웹은 Pages 재배포로 복원된다.

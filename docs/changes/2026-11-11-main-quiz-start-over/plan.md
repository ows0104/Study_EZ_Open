# Main-Quiz 새로 출제 — 구현 계획

## 변경 범위·대상 파일·순서
1. `server/app/routes/root_generation.py`: `RequestIn.restart`, `generation_input`에 `restartOf`, `restart_target()`(최근 판 확인·거절),
   `request()`에서 requestId 재사용 확인 뒤 restart면 `raw`에 `restartOf`·`restartReason`을 넣는다. `public_job`에 `restartOf`를 넣는다.
2. `server/tests/test_root_restart.py`(새): R3–R6 및 옛 판 보존(행·job·operatorResumes 불변), 입력 지문, 공개 거절.
3. `web/src/bank/RootGenerationPanel.tsx`: 두 번째 버튼, 이유 칸 라벨 「이유 (이어 하기·새로 출제)」, 안내 문장.
4. `web/tests/main-quiz-generation-button.test.cjs`: 새로 출제 본문·막힘 조건, 옛 판이 map-tree가 아니면 버튼 없음.

## 검사 명령과 성공 조건
- web: `npm test`(web), `npm run typecheck`, `npm run build` 통과.
- regression: 서버 `test_root_restart.py`, `test_root_map_tree.py`, `test_root_generation_columns.py`와 서버 전체 테스트(로컬 PyMuPDF 미설치로 원래 실패하는 것은 구분).
- 모두 격리된 sqlite·로컬 저장소(root_support.setup)에서. 운영 DB·R2·모델 호출 없음.

## 위험·복원·승인할 범위
- 승인: 사용자 2026-11-11 「어 새로 출제 버튼을 만들어줘」. 코드 구현·PR·master 병합(=API·Pages 자동 배포)까지. 되돌림은 git revert.
- 실제로 261110_02에서 「새로 출제」를 누르는 것은 사용자 몫이다. 누르는 것이 그 강의 전송·공개의 승인이다.
- 위험: 상한 초기화가 남용될 수 있다 → 관리자 버튼에서만, 이유 필수, 최근 판이 끝났을 때만 허용한다. 사슬은 `restartOf`로 추적한다.

# 복습 퀴즈 객관식 모드 — 배포 준비

## 코드 리뷰·검증 결과
2026-11-14 로컬(worktree `.claude/worktrees/studyez-multiple-choice-mode-2089bc`):
- `tests/quizbank/test_root_mcq.py` 8 통과(형식별 정답 선지·종류/근거 없는 오답 거절·둘째 회차·실패 묶음·서버용 대조).
- 서버 `-m tests main_quiz` 9 통과(새 `mcq_choices`: 판·지문 불일치면 안 붙음, 앞면에 정답·근거 없음, 풀이가 helped가 아님), `route_contract` 통과.
- 웹 `npm run typecheck`·`npm run build` 통과.
- 화면: `server/tests/serve_main_quiz_mcq_fixture.py`(격리 sqlite) + 하네스 `web/tests/root-learning.html`에서 진입 토글 → 객관식 시작 →
  단답(5선지, 1·3 키로 두 개 고름, Space로 확인, 맞게 고름/잘못 고름 표시) → 나열(다중 정답 2개) → OX(O·X 선지)를 직접 확인.
  reveal 요청 `choicesShown:false, helped:false`.
- 검사 중 고친 것: 객관식 모드 풀이가 「도움받은 풀이」로 잡혀 회상 가능·학습률에서 빠지던 것(사용자 「분리하지 말고」), 시작 카드에서 토글이 가로로 늘어나던 것, 선지가 없는 번호 키가 5(제외)를 막던 것.

## 배포 대상 버전·순서·데이터 변경
- DB 스키마·기존 데이터 변경 없음. asset 종류 `root_mcq`는 코드 목록(`ASSET_KINDS`)에만 더한다.
- 순서: master 병합 → API → 웹 자동 배포 → 러너 PC에서 만든 선지를 `python -m runner.root_mcq --all-published --subject 감염과 면역 --upload-only`로 올림.
- 러너 재설치 불필요(게시 경로 불변).

## 배포 후 확인·롤백·필요한 사람 승인
- 확인: health revision, 객관식 모드에서 asset이 있는 강의의 문항이 선지로 나오는지, asset 없는 강의는 주관식 그대로인지.
- 롤백: 병합 커밋 revert. 올린 asset을 지우면 그 강의는 객관식 모드에서도 주관식으로 나온다.
- 승인: 사용자의 2026-11-14 야간 요청(구현·배포·선지 생성·업로드까지).

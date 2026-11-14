# 선지 보기·객관식 모드 선지 합치기 — 배포 준비

## 코드 리뷰·검증 결과
2026-11-14 로컬(worktree `../Study_EZ_choices-merge`, origin/master 75643a09 기준, 기록 `runs/_development/2026-11-14-choices-merge/`):
- 표기 단서 검사 보정(현재 올라간 v1 선지 8,359개 오답에 대고 잼):
  - 1차(문자 수로 주된 언어) 963개를 뺐다 — 「독소(TSST-1)」 같은 짧은 한국어+약어가 뒤집혀 거짓 양성이 많았다. 단정 표현은 「절대혐기성」까지 잡았다.
  - 최종: 「정답이 모두 한 언어로만 쓰였는데 오답이 다른 언어로만」 115, 「정답이 모두 한글(영문) 병기인데 오답은 아님」 137, 길이 121,
    단정 표현 0(낱말로 선 것만). 합계 373(4.5%), 문항 195/2,795. 표본은 실제로 티 나는 것들(정답 「M cell」 vs 오답 「파네트세포」, 병기 누락).
  - 길이 기준(정답 평균 8자 이상에서 1/3~3배)은 시범 분포를 보고 다시 정한다.
- 족보: 공통 PDF 형식이라 코드로 읽힌다. 이 PC 27강의 족보에서 보기까지 읽힌 문항 359. 문항에 직접 연결된 족보(`jokboPages`)는 206/4,306문항.
- cloze: 게시본 `{답}` 빈칸을 세게 고쳐 823문항 중 808이 대상이 된다(전에는 0).
- 검사:
  - `pytest tests/contracts tests/quizbank tests/runner`(바로가기 설치기 기존 결함 1개 제외): 1차 2269 통과·4 실패 — 앞 단계 검사 4개가
    가짜 하위 프로세스로 새 선지 단계를 막지 않아서였다(#155가 root_choices에 했던 것과 같은 막음을 root_mcq에 추가). 고친 뒤 해당 3파일 36 통과, 전체 재실행 2273 통과·1 건너뜀(`regression-2.log`).
  - 새 검사: `tests/quizbank/test_root_mcq.py` 18(출처·이유·족보 검사, 표기 단서, cloze 빈칸, 회전, 둘째 회차, 족보 입력·읽기, v1 읽기),
    `tests/runner/test_root_mcq_publish.py` 4(족보 목록·근거 자리, 생성기 인자·v1 보존, 게시 직후 업로드·v2 표시, 실패 로그).
  - 서버(`PYTHONPATH=..`, 격리 sqlite): `mcq_choices`(v1 + v2: 같은 날 같은 선지, 앞면에 이유·출처 없음, 답면 정답·이유·족보 출처, 주관식 V는 도움받은 풀이),
    `recall_choices` 1, `main_quiz` 9, `route_contract` 통과, `root` 41/43(실패 2는 로컬 서버 venv에 pymupdf가 없어 import에서 멈춤, 이 변경과 무관).
  - 웹: `npm run typecheck`, `npm run build` 통과.
  - 화면: 고정물 `server/tests/serve_main_quiz_choices_v2_fixture.py`(격리 sqlite) + `web/tests/root-learning.html`.
    주관식 단답: 「선지 보기 V」 → 정답 + 오답 풀 7개 중 5개(6개 선지), 「하나를 고르세요.」. 족보 오답을 고르고 답 보기 → 「✕ 잘못 고른 선지」 아래
    「2022 족보 45번 …이유」, 나머지 이유는 「다른 오답이 틀린 이유」에 접힘. 객관식 모드 나열: 정답 2 + 오답 5개 중 4개, 개수 안내 없음, 고른 오답만 이유.
    콘솔 오류 2건은 검사 스크립트가 document에 보낸 가짜 키 이벤트 때문(실제 키 입력은 요소에서 온다).
- 사용자 피드백 반영(나눠 묻는 문항·성의 있는 오답): 새 검사 3개(묶음 판정·묶음 오답 검사와 고르기·생성기 묶음 입력과 검토 이름). 반대말 금지 코드 검사는 사용자 정정으로 뺐다,
  서버 `mcq_choices`·`recall_choices`·`main_quiz` 통과, 웹 typecheck·build 통과, 전체 회귀 2277 통과·1 건너뜀(`regression-3.log`).
  화면(고정물의 「항목: 값」 나열): 주관식 V에 「Epidemic typhus」「Murine typhus」 제목 아래 4개씩, 안내 「묻는 것마다 하나씩 고르세요.」,
  같은 묶음에서 다른 것을 고르면 바뀌고, 답면은 묶음마다 맞게 고름·잘못 고름(이유 한 줄)·빠뜨림. 객관식 모드도 같은 묶음으로 보인다.
- 확인하지 못한 것: 실제 모델로 만든 v2 선지의 품질·비율·시간(시범 전), 옛 UI 검사 `web/tests/root-recall-choices.test.cjs`(Playwright) 재실행.

## 배포 대상 버전·순서·데이터 변경
- DB 스키마 변경 없음. asset 종류는 그대로 `root_mcq`(파일 `<revision>.json`), 내용이 `root-mcq/2`. 서버는 v1·v2·`root_choices`를 모두 읽는다.
- 순서: 시범(따로 승인) → master 병합(API·웹 자동 배포) → 러너 재설치(게시 직후 단계가 바뀜) → 게시된 강의 재생성·업로드(따로 승인).
- 배포만 하고 재생성 전에는 지금 올라간 v1 선지가 그대로 보이고, 주관식 V는 v1 객관식 선지를 먼저 쓴다(전에는 `root_choices`만).

## 배포 후 확인·롤백·필요한 사람 승인
- 확인: API health revision, 선지 있는 강의에서 주관식 V·객관식 모드·답면 이유. 러너 `agent.lock` pid·PYTHONPATH 새 설치본.
- 롤백: 병합 커밋 revert. 재생성한 강의는 러너 PC의 `mcq/v1-<revision>.json`을 `<revision>.json`으로 되돌려 `--upload-only`.
- 승인: 구현(사용자 「I'll coordinate, then start」, state.json). 시범 모델 호출·병합·러너 재설치·재생성 업로드는 따로.

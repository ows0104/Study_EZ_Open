# Main-Quiz 중요도 필터 강의별 저장·범위 슬라이더 — 배포 준비

## 코드 리뷰·검증 결과

- server: focus 관련 7개(`test_root_focus`·`test_root_prereq_toggle`·`test_root_mix`·`test_root_generation`·`test_root_pipeline_v2`·
  `test_root_quiz_curation`·`test_root_recall_units`) 통과. 전체 `-m tests` 167/169 통과(실패 2는 아래 기존 결함).
  - 새 검사: 같은 과목 다른 강의(run_id)의 선택이 섞이지 않음, seq가 강의 안에서 셈, 처음 값 Essential~Important,
    네 중요도 모두 고르면 회차 ID가 예전과 같음.
  - 기존 검사 넷(generation·pipeline_v2·quiz_curation·recall_units)은 고정물 문항이 `tier='Optional'`이라 처음 값에서
    오늘 계획이 비었다. 중요도 필터를 검사하는 것이 아니므로 시작 전에 `widen()`(네 중요도 모두)을 부른다.
  - 기존 결함(이 작업과 무관): `test_root_map_tree`·`test_root_map_tree_v3`는 origin/master(eea91da2)에서도 실패한다.
- web: `npm run typecheck`·`npm run build` 통과. 고정물 `web/tests/root-today-prereqs.html` 18개 확인 통과(브라우저):
  선분 4·점 5, 끌기 중 저장 안 함·놓을 때 한 번 저장·늘 한 선분 이상·변화 없으면 저장 안 함·옛 비연속 선택·선분 이름 누르기·선행 문항.
  실제 마우스 끌기(끝 손잡이 → 마지막 점, 시작 손잡이 → 둘째 점 = Core~Optional)와 375px 폭(가로 넘침·이름 잘림 없음) 확인.

## 배포 대상 버전·순서·데이터 변경

- master 병합 = API(Cloud Run)·웹(Pages) 자동 배포. 서버와 웹은 따로 떠도 API 모양이 같아 순서 제약 없음.
- 데이터 변경 없음. 표·migration 없음. 기존 focus 이벤트는 그대로이며 읽는 묶음만 (사용자, 과목, 강의)가 된다.
- 사용자에게 보이는 변화: 직접 바꾼 적 없는 강의는 오늘 추천이 Essential~Important로 시작한다(Optional 빠짐).
  같은 과목 다른 강의에서 고른 값은 더 이상 따라오지 않는다.
- 배포 순간 진행 중인 「오늘 학습」 회차: 처음 값이 바뀐 강의는 오늘 흐름의 안 푼 뒷부분만 새 범위로 다시 골라진다
  (2026-11-14 이어 풀기와 같은 동작). 푼 기록은 남는다.

## 배포 후 확인·롤백·필요한 사람 승인

- 확인: 라이브 강의 하나에서 범위를 바꾸고, 같은 과목 다른 강의의 범위·카드 수가 그대로인지 본다. 모바일 폭.
- 롤백: `git revert` 후 병합(자동 배포). focus 이벤트는 그대로라 과목 단위 읽기·「모두」 처음 값으로 돌아간다.
- 승인: master 병합(배포)은 사용자 확인 뒤(plan.md 승인 범위는 Draft PR까지).

## 후속: 간격·카드 수 위치(2026-11-25, PR #261 병합 뒤)

- 사용자 스크린숏에서 「Important 29Optional」이 붙어 보임 → 카드 수를 이름 아래로, 슬라이더 폭 최대 460→600px,
  `.mq-today-text`가 남는 폭을 채움(전에는 글 길이만큼만 넓어져 폭 제한이 먹지 않았다).
- 웹 표시만. typecheck·build 통과, 고정물 18개 통과, 1280px(슬라이더 600px)·375px(가로 넘침·이름 잘림 없음) 확인.

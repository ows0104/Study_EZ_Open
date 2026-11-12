# Main-Quiz 오늘 계획: 선행 과제가 빠진 과제를 plan에 넘기지 않기 — 배포 준비

## 코드 리뷰·검증 결과

- 새 검사 `server/tests/test_root_prereq_closure.py`(격리 SQLite):
  - 고치기 전: 실패(`availability`가 선행 Q2를 제외해도 task-q4를 available로 돌려줌). 같은 설정으로 overview를 부르면
    운영과 같은 `LinkValidationError: Prepared prerequisite became unavailable: task-q2`(제외 경로·중요도 필터 경로 모두).
  - 고친 뒤: 통과.
- 회귀(worktree `server/.venv`, PyMuPDF 포함, `PYTHONPATH=..`): `-m tests root` 39/39, `main_quiz` 7/7, `route_contract` 1/1 통과.
  처음 돌린 메인 체크아웃 venv에서는 `test_root_map_tree`·`_v3` 2개가 `pymupdf` 없음으로 실패(환경 문제, tier-filter 때와 같음).
- 처음에는 build 승인 기록이 없어 `verify`가 거절했다(다른 세션의 과제문으로 시작). 사용자 승인 뒤
  `approve --phase build`를 기록하고 같은 검사를 `verify --check server`로 남겼다: root 39·main_quiz 7·route_contract 1 통과.
- 운영 DB 읽기 전용 확인(2026-11-12, 한 연결에 `SET TRANSACTION READ ONLY`, 쓰기 없음, 스크립트는 저장소 밖 scratchpad):
  사건 수 상위 학습자 5명 × 공개 판 23개 = 115쌍.
  - 옛 입력(standalone 닫힘 없음 + 거른 집합을 available로): 실패 4 — 학습자 A 261110_01·261102_05(Essential·Core·Important),
    학습자 B 261109_05·261102_05(Essential만). 모두 /4 판, 개인 제외 0, 원인은 중요도 필터.
  - 새 입력: 115쌍 모두 계획 성공. 실패하던 4쌍은 각각 고르지 않은 중요도의 선행 과제 **1개**가 「명시적 선행 문항」으로 함께 나온다.
- 리뷰: plan이 받는 available은 언제나 선행에 닫혀 있고(R1), focus는 후보만 좁힌다(R2). 모두 선택이면 `focus=None`으로 이전 호출과 같다(R3, 검사로 확인).
  catalog(#129의 영역)는 건드리지 않았다. 집계(summary·questionProgress·focus.counts)는 여전히 `available` 기준.

## 배포 대상 버전·순서·데이터 변경

- master 병합 → 일반 자동 배포(API). 웹 변경 없음. DB 스키마·migration·데이터 변경 없음.

## 배포 후 확인·롤백·필요한 사람 승인

- 확인: 운영 로그에서 `Prepared prerequisite became unavailable`가 더 나오지 않는지, 위 4쌍 학습자의 강의가 열리는지.
- 롤백: `git revert`. 남는 데이터 없음.
- 승인: 사용자 2026-11-12 「응 끌어오는 걸로 하고 병합해줘.」 — R2(필터 밖 선행을 끌어옴) 결정과 PR #130 master 병합(=배포).

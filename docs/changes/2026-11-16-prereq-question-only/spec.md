# Main-Quiz 선행: 끌어오기·막기는 문항 사이 선행만 — 설계

## 요구사항과 수용 기준

- R1 목표 사이 선행(`document.prerequisites`)은 고른 중요도 밖의 과제를 끌어오지 않는다: `order_plan`이 목표 사이 선행을
  고르지 않은 과제로 따라가지 않는다. 오늘 목록에 둘 다 있으면 앞 목표 과제를 먼저 둔다(순서).
  `planning.plan`·`plan_tasks`의 「명시적 선행 연결」(안 배운 앞 목표를 오늘 **후보**(고른 중요도 안) 중에서 당겨 옴)은 그대로 둔다.
  구현 중 확인(2026-11-16): 이것까지 지우면 기존 계획 검사 11개(`test_root_planning` 등)가 의도된 설계로 실패하고,
  261109_02 운영 사본 재현에서는 두 방식의 결과가 같았다(Essential만 52→18과제).
  사용자 확인(2026-11-16): 「아니야 어느 정도의 선행은 끌어오는게 좋긴할듯.. 지금 선행이 뭔가 과도하게 엉켜서 그렇지.」 → 유지.
- R1a 존재 목표 예외(병합 직전 master에 들어온 #190 spec R2와 맞춤): presuppose/1이 만든 존재 목표 선행
  (`relation_id` `PRE-<12 hex>`, `presuppose.is_existence_edge`)은 고른 중요도 밖이어도 `available`에서 끌어온다.
  지도 관계에서 온 목표 선행은 고른 중요도 안(후보)에서만. #190의 복습 풀어 주기(`pull`)는 둘 다 그대로.
  사용자 결정(2026-11-16): 「존재 목표만 끌어오기」.
- R2 문항 사이 선행(`questions[].prerequisites`)은 지금처럼: 아직 평가하지 않은 준비된 선행은 중요도 필터 밖이어도
  「명시적 선행 문항」으로 앞에 끌어온다. 평가한 선행은 다시 내지 않는다.
- R3 준비되지 않은 선행은 건너뛴다: `availability`가 선행 때문에 과제를 막지 않는다(`close_prerequisites` 삭제).
  `order_plan`은 준비되지 않은 선행을 내지 않고 뒤 과제는 그대로 낸다(이전에는 500 원인이던 `require`).
- R4 풀이 화면: 세션 과제의 이유가 「명시적 선행 문항」이면 응답 `task.prerequisite: true`, 화면에 「선행 문항」 태그와 설명.
  준비 단계 프레임(`/prepare`)도 같은 값을 준다.
- R5 판 작성·검증(`make_document`·`validate_document`가 쓰는 `order_plan(doc, 모든 과제, 모든 과제, ∅)`)의 결과는 바뀌지 않는다.
  모든 과제를 고르고 모두 준비된 호출에서는 끌어오기·건너뛰기가 일어나지 않기 때문이다.

수용:
- contracts: 목표 사이 선행만 있는 과제를 혼자 고르면 그 과제만 나온다. 둘 다 고르면 앞 목표가 먼저. 문항 선행은 끌려온다.
  준비 안 된 선행은 건너뛰고 오류가 없다. 문항+목표 합친 순환은 여전히 거절.
- server `test_root_prereq_closure.py`: 선행 제외 → 의존 과제는 준비되어 계획·세션에 남는다(문제 1개=제외한 과제만).
  필터 밖 문항 선행은 끌려오고 `prerequisite: true`. 학습 기록 불변.
- 운영 사본 재현(읽기 전용으로 받은 판·이벤트, 로컬 계산): Essential만 → 끌려온 과제는 문항 선행뿐, 막힌 과제 0.

## 책임·입출력 계약·오류 상태

- `studyez_contracts.roots.generation_v2`
  - `question_dependencies(doc)`(새): 과제별 문항 사이 선행 과제 목록.
  - `task_dependencies(doc)`: 그대로(문항+목표). 순환 검사·순서에 쓴다.
  - `order_plan(doc, selected, available, assessed)`: 선행 `pre`를 따라갈 때
    `pre`가 고른 과제면 먼저 낸다(순서). 아니면 문항 사이 선행이고 준비되었고 평가 안 했을 때만 끌어온다.
    준비되지 않은 선행은 건너뛴다. 고른 과제 자신이 준비되지 않았으면 여전히 오류(호출자 버그).
- `server/app/root_learning/content.availability`: 반환 `(available, problems)`. problems는 과제 자신의 이유만(개인 제외 등).
- `server/app/routes/root_learning.project_session`·`prepare`: `task.prerequisite`(bool) 추가. 라우트 경로·필드 삭제 없음.
- `web`: `RootView.task.prerequisite?`·`RootFrame.task.prerequisite?`(옛 서버는 안 보냄 → 표시 없음).

## 호환성과 데이터 보존

- 학습 기록(root_event·root_session) 쓰기·지우기 없음. DB 스키마 변경 없음.
- 이미 시작한 오늘 세션의 과제 목록은 고정이라 그대로다. 막혀 있던 과제는 배포 뒤 그 자리에서 풀린다.
- 선행을 제외한 학습자의 `preparationProblems`가 줄 수 있다(의존 과제가 다시 준비됨).
- 필터를 쓰는 학습자의 오늘 목록은 짧아진다(고른 중요도 밖에서 목표 사이 선행으로 끌려오던 과제가 빠짐).
  모두 선택이면 계획은 이전과 같다(준비 안 된 선행이 없을 때).

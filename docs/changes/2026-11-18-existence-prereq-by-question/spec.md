# Main-Quiz 존재 선행: 목표 단위 대신 문항 단위로 끌어오기 — 설계

## 요구사항과 수용 기준

- R1 문항 단위 연결(`planning.existence_links(doc, records)`): 전제 기록 하나 `{question_id: X, recalled_by: [...], point_id}`에서
  앞 문항 Y는 `recalled_by`의 문항과, `point_id`가 있으면 그 포인트의 목표(`review.points[].target_ids`)에 놓인 문항이다.
  (Y의 목표, X의 목표)가 판의 존재 간선(`is_existence_edge`)일 때만 X→Y를 남긴다. 판에 없는 간선(순환이라 뺀 것, 같은 목표)은 새로 만들지 않는다.
  반환은 `{X: [Y…]}`(정렬). 판에 놓이지 않은 문항은 무시한다.
- R2 계획(`plan(..., links=None)` → `plan_tasks`): `links`가 주어지면
  - 존재 간선은 목표 단위로 끌어오지 않는다(순서 `emit`은 그대로 간선을 따른다).
  - 오늘 고른 과제 X마다 `links[X]`의 Y를 `available`(필터 밖 포함)에서 「명시적 선행 연결」로 끌어온다.
    끌려온 Y도 다시 자기 `links`를 따른다(연쇄). 지도 관계 선행(필터 안 목표 단위)과 번갈아 더 이상 늘지 않을 때까지 돈다.
  - Y를 끌어올지(풀어 주기): 오늘 이미 푼 Y는 아니다. 평가가 없거나 마지막 평가가 `independent`가 아니면 끌어온다.
  `links`가 없으면(None) 지금 동작 그대로(11-16 R1a: 존재 간선은 앞 목표 과제 전부).
- R3 서버(`content.existence_links(db, row)`): 판 `auto-<id>`의 `root_generation.result.manifest.presuppositions`로 R1을 계산한다.
  기록이 없거나 다른 판(사진 반입 등)이면 None. 판은 바뀌지 않으므로 판별로 프로세스 메모리에 둔다.
  `routes/root_learning`의 `planning.plan` 호출 세 곳(개요·칩 바꿈 두 번)에 넘긴다.

수용:
- server 새 검사: 두 목표 판(T1: Q1·Q3·Q4 → T2: Q2, 존재 간선)에 `links={Q2: [Q1]}`이면 필터 {Q2}에서 [Q1, Q2]만.
  Q1을 쉽게 맞혔으면 [Q2]. Q3만 틀렸으면(Q3은 연결 없음) [Q2]. X가 오늘 목록에 없으면 Y도 없다. 지도 간선은 그대로.
  `existence_links`는 recalled_by·point·판에 없는 간선·놓이지 않은 문항을 맞게 다룬다.
- 기존 `test_root_prereq_release`(links 없음)는 그대로 통과한다.
- 운영 사본 재현(261110_02, 오늘 학습자의 아침 기록·필터): Q107은 없다. Q106은 Q114(Important)의 전제를 답하므로
  Q114가 목록에 있으면 남는다. 끌려온 Optional 목록과 그 전제 문항을 release.md에 적는다.

## 호환성과 데이터 보존

- DB 쓰기·스키마 변경 없음. `root_generation.result`를 읽기만 한다. 판·학습 기록·개인 수정 불변.
- 이미 시작한 오늘 흐름의 과제 목록은 고정이다. 칩을 바꾸면(refocus) 뒷부분이 새 규칙으로 다시 골라진다. 다음 학습일부터 반영.
- 필터를 쓰는 학습자의 오늘 목록이 짧아진다(존재 목표의 다른 과제가 빠짐). 필터 없이 모두 고른 학습자도 안 배운 존재 목표
  전체가 한꺼번에 당겨지던 것이 문항 단위가 된다. 빠진 과제는 자기 목표가 새 목표·복습으로 골라질 때 나온다.

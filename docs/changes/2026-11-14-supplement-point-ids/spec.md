# Main-Quiz 보충 포인트 ID 충돌 수정 — 설계

## 요구사항과 수용 기준
- `generation_v3.attach_points(points_doc, output, off_goal_ids, page_counts, reserved=())`:
  `reserved`는 다른 곳(brief)에서 이미 쓰는 포인트 ID. 새 번호는 `points_doc`과 `reserved`의 `P숫자` 최댓값+1부터.
- `generation_v4.attach_points`는 같은 인자를 넘긴다.
- 오케스트레이터 v3·v4는 `reserved=[p['point_id'] for p in brief['points']]`를 넘긴다.
- 수용: brief에 P088–P093이 있고 포인트 문서가 P087까지일 때 새 보충 포인트는 P094이고 `extend_brief`가 통과한다.

## 책임·입출력 계약·오류 상태
- `duplicate_of`가 가리킬 수 있는 기존 포인트는 지금처럼 포인트 문서의 포인트뿐이다(`reserved`는 번호만 비켜 간다).
- `check_supplement`의 상태 검사 호출은 tier·형식 검사용이라 번호와 무관하므로 그대로 둔다.
- `extend_brief`의 충돌 거부 검사는 그대로 둔다(최후 방어선).

## 호환성과 데이터 보존
- `reserved` 기본값 `()`이면 지금과 같은 결과. 이미 끝난 강의의 ID는 바뀌지 않는다.
- ledger 캐시: supplement 출력은 그대로 재사용되고, 새 ID가 들어간 supplement-normalize 입력만 해시가 달라져 다시 호출된다.
- 프롬프트·DB·서버·웹 변경 없음.

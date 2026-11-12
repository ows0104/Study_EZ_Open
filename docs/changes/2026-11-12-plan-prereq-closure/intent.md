# Main-Quiz 오늘 계획: 선행 과제가 빠진 과제를 plan에 넘기지 않기

## 문제와 사용자 효과

운영 2026-11-12: `GET /api/root-learning`이 05:40Z~06:11Z에 9번,
`/api/root-learning/lectures/감염과 면역/261102_05/focus`가 04:35Z 무렵 500을 돌려줬다.
traceback은 `planning.plan_tasks` → `studyez_contracts/roots/generation_v2.py` `order_plan` → `emit` →
`require(tid in available, 'Prepared prerequisite became unavailable: task-…')`.
운영 DB 읽기 전용 재현(사건 수 상위 학습자 두 명, 공개 강의 23편)에서 학습자마다 2~3편이 같은 오류로 실패했다.

영향을 받은 학습자는 그 강의의 오늘 학습(overview)·진입(entry)·중요도 선택(focus) 모두 500이라 열 수 없다.
강의 목록은 PR #129(claude/review-bar-ux)가 실패한 강의만 빼도록 막았지만 원인은 남아 있다.

원인 둘(같은 증상):

1. **개인 제외(#120)**: Main-Quiz 판은 `bank_source == 'standalone'`인데, `content.availability`가 standalone에서
   /2·/4 선행 규칙(선행이 준비되지 않은 과제도 준비 안 됨)보다 먼저 return했다. 선행 문항을 제외하면 그 문항에
   기대는 과제가 available에 남고, order_plan이 선행을 내려다 실패한다.
2. **오늘 학습 중요도 필터(#119)**: `overview_data`가 고른 중요도로 거른 집합을 `plan`의 available로 넘겼다.
   거른 집합은 선행 규칙을 지키지 않는다. 고른 중요도의 과제가 고르지 않은 중요도의 아직 평가 안 한 선행에 기대면 실패한다.

## 범위와 성공 기준

- `plan`은 선행 과제가 준비되지 않은 과제를 받지 않는다. 위 두 경로 모두에서 overview·entry·catalog가 200.
- 학습 기록(root_event·root_session)은 바뀌지 않는다. DB 스키마 변경 없음.
- 격리 SQLite 검사: 고치기 전 실패, 고친 뒤 통과. `-m tests root` 통과.

## 근거·미정 사항

- 작업 요청: 복습바·속도 세션(PR #129)에서 분기한 세션의 과제문(2026-11-12). 사용자 발언 원문은 이 세션에 없다.
- 결정(이 세션): 필터 밖이지만 준비된 선행은 끌어온다(order_plan의 기존 규칙 「명시적 선행 문항」). 대안은 그 과제를
  오늘 계획에서 빼는 것인데, Essential 과제가 Optional 선행 하나 때문에 오늘 목록에서 사라지게 된다.
  사용자 확정(2026-11-12): 「응 끌어오는 걸로 하고 병합해줘.」
- 운영 확인(읽기 전용, release.md): 실패 4건 모두 원인 2(중요도 필터)였다. 개인 제외는 아직 운영에서 실패를 만들지 않았지만
  같은 구멍이라 함께 막는다.

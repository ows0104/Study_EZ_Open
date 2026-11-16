# plan — 존재·역방향 문항 이름표

브랜치 `fix/existence-review-label` (worktree `../Study_EZ_existence-label`), origin/master d62d1bc2에서.

## 1. `studyez_contracts/roots/presuppose.py` — `mark_review`

```
def mark_review(ctx, brief, presuppositions, bank, exclude=()):
```

- `exclude`의 문항은 건너뛴다(R1).
- 포인트를 고를 때, 그 포인트의 연결을 **자기 발문이 전제로 준** 문항이면 그 포인트를 뺀다(R2).
  `by_point[point_id]`에 그 문항 ID가 들어 있으면 그 목표는 이 문항의 것이 아니다.
- 남은 포인트가 없으면 행을 만들지 않는다. 결과가 비면 `existence` 칸을 넣지 않는다(지금과 같다).

## 2. `studyez_contracts/roots/discriminate.py` — `mark_review`

같은 모양. R2의 기준은 `forward_by`·`asked_by` — 정방향으로 그 연결을 이미 묻는 문항은
역방향 문항이 아니다.

## 3. 호출부 여덟 줄

| 파일 | 자리 | 넘기는 것 |
|---|---|---|
| `quizbank/connection_generate_v4.py` | 검토 입력 421·423 · 고치기 입력 540·542 | `exclude=intake_ids` |
| `quizbank/connection_presuppose.py` | 검토 입력 211·212 · 고치기 입력 239·241 | `exclude=published` |

`intake_ids`는 279줄에, `published`는 90줄에 이미 있다.
**검토 입력만 고치면 안 된다** — 고치기 입력도 같은 이름표를 받는다. 처음에 여섯 줄로 세고
`grep mark_review`로 여덟 줄임을 확인했다.

## 4. 검사

`tests/quizbank/test_presuppose.py`·`test_discriminate.py`에 재현 검사를 더한다.

- 받아온 은행의 세부 문항에 그 목표의 포인트가 붙어 있어도 이름표를 받지 않는다(`exclude`).
- 자기 발문이 그 연결을 전제로 준 문항은 `exclude` 없이도 이름표를 받지 않는다(R2).
- 이번 실행이 쓴 존재 문항은 **여전히** 받는다(기존 검사가 보증).
- `exclude`를 안 넘기면 R2만 걸리고 나머지는 지금과 같다.

그 뒤 contracts·quizbank 전체를 돌린다.

## 5. 올리기

PR은 Draft로 하나만 올린다([[pr-habits-save-actions-minutes]] — Actions 분을 아낀다).
병합은 사용자가 직접. 병합 뒤 러너 재설치는 `finish-today-backfill` 세션과 맞춘다.

복구(세부 23개)는 이 PR에 넣지 않는다. 고침이 올라간 뒤 별개로 한다.

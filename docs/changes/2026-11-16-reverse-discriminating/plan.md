# Implementation Plan — discriminate/1 (사람 승인 대기)

승인 전에는 코드를 고치지 않는다. 아래는 고칠 자리와 순서다.

## 1. 계약 — 새 모듈 `studyez_contracts/roots/discriminate.py`

`presuppose.py`를 본으로 한다. 순수 함수만 두고 모델·DB·서버에 의존하지 않는다.

| 함수 | 하는 일 |
|---|---|
| `stage_input(brief, bank, concept_ids, page_counts)` | 판정할 범주·원소와, 참조용 은행 전체 발문·정답 |
| `OUTPUT` / `check(value, ctx)` | R2의 출력 형식과 검사. 원소마다 한 줄, `asked_by`가 비면 `point` 필수 |
| `records(outputs, bank, points_doc, reserved)` | 판별 연결 기록과 새 포인트(`origin: 'discrimination'`). (균, 원소) 하나에 포인트 하나 |
| `mark_add(ctx, brief, records, bank)` | add 입력의 목표에 `discrimination` 표시(단서·소속·형제) |
| `mark_review(ctx, ...)` | 검토·수정 입력에 같은 표시. 없으면 검토가 「조건을 붙여 변별하라」로 되돌린다 |
| `written_for(bank, brief, records)` | 목표 하나에 문항 하나 가드 |
| `gaps(rows, brief, records)` | 소속·원소 둘 다 답이어야 covered |
| `order_edges(...)` | R7. 정방향 목표 → 역방향 목표 |
| `counts(...)` | R9의 숫자 |

`mark_review`를 처음부터 넣는 이유: 존재 문항에서 이것을 빼먹어 검토가 「쉬워 보인다」며
조건을 덧붙였고 #202에서 고쳐야 했다.

## 2. 프롬프트 — `content/prompts/learning-links/v4/`

- 새 `discriminate.md`. R1~R3의 판정 규칙. 균을 주지 않는 단서를 쓰게 하고,
  형제와 갈라지지 않으면 `point`를 만들지 말고 이유를 남기게 한다.
- `add.md`에 `discrimination` 표시를 받는 절을 더한다(R4). 기존 「양방향으로 확인할 수 있다」
  권고 줄은 이 절을 가리키게 고친다. 권고만으로는 안 지켜진다는 것이 이번 근거다.
- `coverage.md`는 고치지 않는다. 방향이 다르면 중복이 아니라는 줄이 이미 있다.

## 3. 파이프라인 — `quizbank/`

- `connection_generate_v4.py`: 존재 목표 단계(2p) 다음에 역방향 단계를 둔다.
  범위 점검·add·검토·수정에 표시와 가드를 건다.
- `connection_presuppose.py`: 보강 경로에도 같은 단계를 넣는다(R8).
  보강 한 번에 존재 목표와 역방향 목표가 같이 생긴다.
- `runner/root_native_json.py`: 새 단계 이름과 스키마·검사를 등록한다.

## 4. 검사

- 계약 단위 검사: 판정 형식, (균, 원소) 중복 합치기, 소속 없는 답은 미달, 선행 방향.
- 파이프라인 검사: 표시가 add·검토 입력에 실리는지, 가드가 두 번째 라운드를 막는지.
- 루트 Python 전체(약 3045개)와 서버 smoke.
- 실데이터 재현: 콜레라 편 공개판 입력으로 단계만 돌려 R9의 숫자를 센다.

## 5. 시범

러너를 새 판으로 재설치한 뒤 한 편을 돌려 R9를 센다.
문항 증가가 어림(15~20)과 크게 다르면 사용자에게 먼저 알린다.

## 6. 그 뒤

- 25편 보강을 한 번에(R8).
- 콜레라 편 재보강 여부는 사용자 결정.

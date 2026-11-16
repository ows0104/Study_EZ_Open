# Implementation Plan — discriminate/1 (사람 승인 대기)

승인 전에는 코드를 고치지 않는다. 아래는 고칠 자리와 순서다.

## 1. 계약 — 새 모듈 `studyez_contracts/roots/discriminate.py`

`presuppose.py`를 본으로 한다. 순수 함수만 두고 모델·DB·서버에 의존하지 않는다.

| 함수 | 하는 일 |
|---|---|
| `goals(brief)` / `stage_input(brief, bank, direction_ids, page_counts)` | 판정할 목표와, 참조용으로 그 강의의 모든 목표·은행 전체 발문·정답 |
| `OUTPUT` / `check(value, ctx)` | R2의 출력 형식과 검사. 목표마다 한 줄, `reversible`이면 `competitors` 필수, `asked_by`가 비면 `point` 필수 |
| `records(outputs, bank, points_doc, brief, reserved)` | 역방향 기록과 새 포인트(`origin: 'discrimination'`). (답, 단서) 하나에 포인트 하나 |
| `mark_add(ctx, brief, records, bank)` | add 입력의 목표에 `discrimination` 표시(단서·답·경쟁자·정방향 문항) |
| `mark_review(ctx, ...)` | 검토·수정 입력에 같은 표시. 없으면 검토가 「조건을 붙여 변별하라」로 되돌린다 |
| `written_for(bank, brief, records)` | 목표 하나에 문항 하나 가드 |
| `gaps(brief, records, bank)` | 역방향 목표의 빈자리 = 그 목표로 쓴 문항이 아직 없는 것(범위 점검에 맡기지 않는다) |
| `report(records, doc, bank)` | R9의 숫자와 `answerInStem`(발문이 답을 흘린 문항) |
| `order_edges(...)` | R7. 판정된 목표·정방향 문항의 목표 → 역방향 목표 |

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

## 구현하며 바뀐 것 (2026-11-16)

- 소속 강제를 뺐다(사용자 「답에 소속은 꼭 강제 안해도 될듯? 그냥 예시였어」). 목표 component는 원소 하나.
  강제하는 것은 「발문에 주체를 주지 않는 것」뿐이고, 그것은 프롬프트·검토가 지키고 `report.ownerInStem`이 센다.
  막지 않는 이유: 한 문항 때문에 강의 하나를 보류시키지 않는다([결함 카드는 막지 않고 올린다]의 결).
- 새 역방향 목표에 add 전 범위 점검을 부르지 않는다(spec R4 끝 문단). 파이프라인 검사가 잡았다.
- 주체(owner)는 모델 출력이 아니라 지도에서 읽는다(`records(..., brief)`). 발문이 말하면 안 되는 이름을
  모델이 다시 적게 두면 틀린 이름으로 재게 된다.
- `owners()`는 루트의 자식을 주체로 본다. 처음 구현은 루트가 먼저 칠해 모든 개념이 루트 소속이 됐다.
- 이름 정규식은 영문·숫자·ASCII 하이픈만. en dash는 이름과 설명을 가르는 기호라 이름에 넣지 않는다
  (「LasB–zinc metalloprotease」→ LasB, zinc, metalloprotease).
- 이름 있는 원소를 가진 범주가 없는 지도는 판정 호출을 하지 않는다. `chunks([])`가 빈 묶음 하나를 돌려줘서
  범주 없는 강의마다 빈 호출이 생길 뻔했다.
- 새 역방향 관계 ID는 `RQD`로 시작한다. `presuppose.relation_ids`에 `prefix`를 더했다(기본값 그대로 `RQP`).
- 학습 순서 간선은 `REV-`로 시작하고, 존재 간선(`PRE-`)과 달리 오늘 고른 층 밖으로 당겨 오지 않는다.
  역방향은 정방향이 이미 묻는 내용을 다른 끝에서 한 번 더 묻는 것이라 차례를 기다린다.

## 6. 그 뒤

- 25편 보강을 한 번에(R8).
- 콜레라 편 재보강 여부는 사용자 결정.

## 두 번째 판 (2026-11-16, 사용자 지적 뒤)

- 판정 단위를 범주 → **목표**로 바꿨다(spec R1). `categories`·`owners`·`named`는 지웠다.
- 치료제·검사 소견을 범위에 넣었다(사용자 「치료·검사도 넣기」).
- 문항 수를 지키는 것은 구조 조건이 아니라 `competitors`(헷갈릴 후보가 있나)다.
- 「주체(owner)」라는 칸을 없앴다. 대신 `answer`(회상할 것)와 `cue`(단서)만 둔다. 과목마다 주체의
  뜻이 달라 칸으로 두면 또 한 과목에 맞춰진다.
- 측정도 `ownerInStem` → `answerInStem`으로 바꿨다. 발문이 답 쪽을 흘렸는지를 한국어 단어까지 본다.

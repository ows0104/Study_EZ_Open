# Main-Quiz 문항을 지도 관계에 바로 배치 — 구현 계획

PR #92(`evidence`)와 #93(`PLACEMENTS`)을 병합한 master 위에서 PR 하나로 낸다.

사용자 2026-11-11 「지도 직접 배치도 짜줘」. spec의 「결정할 것」은 권한 기본값으로 진행하고, release에 적어 사용자에게 다시 보인다.
1. 실측을 기다리지 않는다.
2. 후보 순서는 whole → component 수 → 지도 순서다.
3. `readiness`는 지금 규칙(커버 판정)을 유지한다. 일부만 묻는 과제만 있는 목표는 「덜 물어짐」이다.

## 변경 범위·대상 파일·순서

### 1. 계약 `studyez_contracts/roots/generation_v4.py`
- 새 규칙 `PLACEMENTS = ('evidence', 'answered', 'review')`와 정책 `REVIEW_PLACEMENT = 'review-relations/1'`
- **검토 출력**
  - `review_schema(ctx)`가 입력에 `map_relations`가 있으면 행에 `relations: [{relation_id, part: whole|partial, reason}]`을 더한다. `evidence_source`(#92)와 함께 있을 수 있다.
  - `check_review_input`: 관계는 입력 목록에 있어야 하고 한 행 안에서 겹치지 않아야 한다.
- **`assessment_raw(placement='review')`**
  - 문항의 관계 주장을 검토 `relations`에서 만든다. 대상 목표는 `relation_ids`에 그 관계가 있는 목표 전부다.
  - 커버 판정의 근거 행은 `direction_evidence`(누락 점검·보고)로만 남는다.
- **`compile_assessment`/`_compile(placement='review')`**
  - 배치 키(`asks`)를 근거 행이 아니라 관계 주장의 목표에서 만든다.
  - 회상 단위가 있으면(R5) 관계 주장을 그 문항이 답한 단위로 좁힌다. 같은 부모의 어느 단위도 답하지 않으면 모든 단위를 남긴다.
  - `recall.summarize`는 문항이 답한 단위만 확인됨으로 센다. 새 인자를 받으며, 기존 규칙에서는 기본값이라 결과가 바뀌지 않는다.
- **`place(..., parts)`**: 후보 순서는 whole 관계가 있는 목표 → 답한 component 수 → 지도 순서다. 관계가 없으면 `no-relation` 이유로 남긴다.
- **`make_document`·`assemble`**: `placement` 인자를 받는다.
- **결과 검증**
  - `_placement4`는 manifest `placement`가 `review-relations/1`이면 반드시 `review` 규칙이어야 한다. 표시가 없으면 `review` 규칙을 받지 않는다.
  - 표시가 있으면 모든 `itemReviews` 행에 `relations`가 있고, 그 행은 판정 기록(`verdictLedger`)의 값이어야 한다.

### 2. 생성기 `quizbank/connection_generate_v4.py`
- 새 ledger에 `placement: {'policy': 'review-relations/1'}`을 적는다(`Stages(fresh=…)`, #92의 `reviewEvidence` 옆).
- 문항 검토 입력에 `map_relations`를 넣는다. 지도 확인에서 supported인 관계만 넣고, 양 끝 개념 이름과 condition을 붙인다.
- 조립에 `placement='review'`를 넘기고, manifest에 표시를 싣는다.

### 3. 지시문 `content/prompts/learning-links/v4/item-review.md`
- `relations` 줄을 더한다.
  - 일부, 반대 방향, 추론도 그 관계로 적는다.
  - 발문에 이미 주어진 사실은 적지 않는다.
  - 없으면 `[]`이다.
- `PROVENANCE.md`에 한 줄을 더한다.
- 커버 지시문은 바꾸지 않는다. 옛 규칙으로 이어 하는 실행도 같은 지시문을 쓰기 때문이며, 새 규칙에서는 그 문장이 배치에 쓰이지 않는다(spec 표와 다른 점으로 release에 적는다).

### 4. 러너 `runner/root_native_json.py`
- `schema_for`가 이미 `v4.review_schema(ctx)`를 쓴다(#92). 이번에는 바꾸지 않고 검사만 더한다.

### 5. 문서
- `quizbank/CLAUDE.md` 한 줄, `docs/map.md` 행 갱신

## 검사 명령과 성공 조건

worktree 루트에서 `PYTHONPATH=.`으로 돌린다.

| 체크 | 명령 | 성공 조건 |
|---|---|---|
| 새 검사 | `python -m pytest tests/quizbank/test_place_by_review.py -q` | 수정 전 master에서 실패, 수정 뒤 통과 |
| 회귀 | `python scripts/development.py verify … -- python -m pytest tests -q` | 기존 결함 `test_desktop_control` 한글 바로가기 하나 말고 통과 |
| 서버 | `server/`에서 `-m tests root` (`PYTHONPATH=..`) | 이전과 같음(로컬 PyMuPDF 2개 제외) |
| 실데이터 | 공개 판 재검증 스크립트 | 1c484a7b·fa71412a·26110803 통과 그대로 |

새 검사(모델 호출 0, 합성 /4 고정물)
- 일부만 묻는 문항(component missing)이 검토 관계로 과제가 된다(Q001 모양).
- 반대 방향 문항, 추론형 문항이 관계로 과제가 된다(Q022·Q030 모양).
- 관계가 없으면 `no-relation`으로 남는다.
- whole 관계가 partial보다 앞선다.
- 회상 단위
  - env만 답하는 문항은 env 단위에 붙는다.
  - 답하지 않은 단위는 확인됨으로 세지 않는다.
  - 아무 단위도 답하지 않으면 모든 단위가 후보다.
- 커버 판정이 같으면 빈 목표 추가 입력이 같다.
- 계약 위변조 거절
  - 과제를 다른 목표로 옮김
  - 검토 관계를 고침(판정 기록과 다름)
  - 표시 없이 review 규칙을 씀
  - 표시가 있는데 다른 규칙을 씀
- 모르는 relation_id는 그 검토 단계를 멈춘다.

## 위험·복원·승인할 범위

**위험**
- **검토 입력이 길어진다.** 관계 목록이 리케차 108개, 묶음마다 약 1만 자다. 검토 시간이 조금 늘 수 있으므로 첫 실행에서 묶음 단계 시간을 비교해 적는다.
- **검토가 관계를 너무 넓게 적으면 엉뚱한 목표에 붙는다.**
  - 원본 대조·설계 판정과 같은 검토라 문항을 읽고 적는다.
  - 첫 실행에서 새로 붙은 문항을 표본으로 확인한다.
- **`readiness` 숫자와 과제 수가 달라 보일 수 있다.** 일부만 묻는 과제가 있어도 「덜 물어짐」이다. 보고 문구로 구별한다.

**복원**
- git revert와 이전 Cloud Run revision·Pages로 되돌리고, 러너는 이전 설치본으로 다시 띄운다.
- 새 규칙으로 만든 판은 되돌린 서버에 다시 반입할 수 없다. 이미 게시된 판은 그대로 읽힌다.

**승인할 범위**
- 작업 요청 「지도 직접 배치도 짜줘」가 구현·검사·PR·병합·배포 승인이다(개발 루프).
- 실제 강의 실행(자료 전송·공개)은 관리자 화면 요청으로 따로 한다.

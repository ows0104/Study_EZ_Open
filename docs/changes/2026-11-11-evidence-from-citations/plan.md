# 근거 지면을 출제 인용으로 바로 연결 — 구현 계획

## 변경 범위·대상 파일·순서

PR 하나로 낸다. 단계마다 검사를 먼저 쓰고, 수정 전에 실패하는 것을 확인한다.

### 0. 읽기 전용 기준선
- 공개된 판 4개의 `validate_result`·`validate_all` 재검증 결과를 기록한다: `runs/_e2e/26110803`, `26110901`, `_root-generation/1c484a7b…`, `fa71412a…`. 이후 모든 단계의 회귀 기준이다.
- 리케차 `result.json`의 최종 리뷰·인용을 고정물로 뽑는다(`tests/fixtures/evidence_261110_03/`, 문항 텍스트 없이 ID·인용 쪽·선택 쪽만).

### 1. 검토 출력에 근거 쪽 (R1)
- `studyez_contracts/roots/generation_v4.py`
  - `ITEM_REVIEW_OUTPUT`의 행에 `evidence {mode, reason, slides[{page, evidence}]}`를 더한다.
  - 새 정책 `'review-evidence/1'`이 `runPolicies`에 있을 때만 필수다.
  - `check_review_input`이 확인하는 것:
    - 쪽 범위: material의 S1 쪽 수
    - single은 1장, linked는 2장 이상, unresolved는 0장
    - 근거 문장이 비어 있지 않음
  - v3로 넘기는 행에서는 `evidence`를 뺀다(`importance_note`와 같은 처리).
- `content/prompts/learning-links/v4/item-review.md`: `evidence` 줄 하나를 더한다.
  - 정답을 직접 증명하는 최소 쪽을 S1 물리쪽으로 적는다.
  - 인용 쪽이 아니어도 S1.md에서 찾은 쪽이면 된다.
  - 슬라이드·요약 쪽을 구별하지 않는다(결정 1).
  - `PROVENANCE.md`에 출처 줄을 더한다.
- `quizbank/connection_generate_v4.py`: 새 ledger의 `runPolicies`에 `'review-evidence/1'`을 더한다. 옛 ledger 이어 하기는 정책을 바꾸지 않는다.
- 판정 재사용(`v3.reusable`): 재사용된 검토 행에도 `evidence`가 있어야 한다. 새 정책 실행 안에서만 재사용하므로 따로 처리할 것은 없고, 검사로 확인만 한다.

### 2. 인용 맞추기 (R2)
- `studyez_contracts/roots/generation_v4.py`: 순수 함수 `align_citations(bank, reviews) -> (bank, alignments)`
  - S1 `source_refs`의 쪽 집합이 마지막 검토의 `evidence.slides` 쪽 집합과 다르면 S1 ref를 근거 쪽으로 바꾼다.
  - 형식은 기존 locator 형식을 따른다: `PDF 물리 N쪽`, linked는 쪽마다 한 ref.
  - unresolved는 바꾸지 않는다.
- `quizbank/connection_generate_v4.py`: 묶음 합치기(`review_phase` 뒤, `stale_coverage` 처리 뒤) 다음, context 앞에서 한 번 호출한다.
  - ledger에 `citationAlignments`를 쓰고, manifest에 싣는다.
  - 바뀐 문항의 시각 자극·기초 문항 연결은 건드리지 않는다.
- `studyez_contracts/roots/generation_v4.py`(결과 검증): 최종 bank 문항과 마지막 검토 입력의 문항이 다를 때 허용하는 경우는 하나뿐이다. 차이가 `citationAlignments`에 적힌 S1 locator 교체와 정확히 같아야 한다.
  - 이 대조가 지금 어디서 일어나는지(`item_hash`·`verdictLedger` 대조 위치)는 이 단계 시작에 확인해 적는다.

### 3. 게시 뒤 근거가 검토 근거를 쓴다 (R3)
- `runner/root_evidence.publish`: `payload['sourceAudit']['question_checks']['reviews']`를 `build`에 넘긴다.
- `quizbank/root_evidence.py`
  - `--reviews <json>` 인자를 받는다.
  - `evidence`가 있는 행을 `authored` 형식(`authoredHash=authored_hash(q)`, `slides[].source_id='self'`)으로 바꿔 `slide_focus.select(..., authored=…)`에 넘긴다.
  - 리뷰가 없는 옛 판은 지금 경로 그대로다.
- `slide_focus.select`는 그대로 쓴다. `authored` 재사용과 남은 대상만 재선택하는 것은 이미 구현되어 있다.

### 4. 재선택 묶음 병렬 (R4)
- `quizbank/slide_focus.py`
  - 남은 대상이 `REVIEW_BATCH`(40)를 넘으면 대상 목록을 나눈다.
  - 묶음마다 `targets.json`을 따로 쓰고 `_call`을 최대 3개 동시에 돌린다.
  - 결과 `selections`를 대상 순서로 합친 뒤 `shape`를 한 번 한다.
- 묶음 폴더: `slide-focus/batch-<n>/`. 캐시 서명(`inputHash`)은 지금 그대로라 재실행 시 캐시가 유지된다.
- 묶음 하나라도 실패하면 전체를 실패로 둔다(부분 결과를 쓰지 않는다).

### 5. 문서
- `runner/CLAUDE.md`, `quizbank/CLAUDE.md`: 한 줄씩 적는다.
  - 게시 뒤 근거는 검토 근거를 쓰고, 남은 것만 재선택한다.
  - `citationAlignments`
- `docs/map.md`: 「뿌리 생성」 행에 근거 연결 위치를 적는다.

## 검사 명령과 성공 조건

worktree 루트에서 `PYTHONPATH=.`으로 돌린다(메인 체크아웃 계약이 섞이지 않게).

| 체크 | 명령 | 성공 조건 |
|---|---|---|
| contracts | `python -m pytest tests/contracts -q` | 새 검사 포함 통과. 공개 판 4개 재검증 통과 |
| generation | `python -m pytest tests/quizbank -q` | 통과. 새 검사(검토 근거 형식·정책 필수·인용 맞추기·결과 대조 위변조·재선택 묶음)는 수정 전 실패 기록 |
| runner | `python -m pytest tests/runner -q` | 통과. 기존 결함 `test_desktop_control` 한글 바로가기는 따로 표시 |
| 전체 | `python -m pytest tests` | 위와 같음 |
| 구조 | `python scripts/map_numbers.py --check` | 통과 |

새 검사 목록(모델 호출 0):
- 검토 근거
  - 새 정책에서 `evidence`가 없으면 거절
  - 옛 정책에서는 없어도 통과
  - 쪽 범위 밖·single 2장은 거절
- 인용 맞추기
  - 리케차 고정물 Q108(23→22)·Q075(3→2)가 맞춰짐
  - 같은 쪽은 그대로
  - unresolved는 그대로
  - S2 인용은 그대로
- 결과 검증
  - 기록과 같은 인용 교체는 통과
  - 기록 밖 인용 교체·본문 교체는 거절
- 근거 넘기기
  - 검토 근거가 있으면 `select`가 모델을 부르지 않음(`selectionOrigin: authored`)
  - 일부만 있으면 남은 것만 `targets.json`에 들어감
- 재선택 묶음
  - 대상 85개면 3묶음
  - 합친 결과가 같은 `shape`를 통과함
  - 한 묶음 실패면 전체 실패

## 위험·복원·승인할 범위

**위험**
- **검토가 인용 밖 쪽을 이미지 없이 글로만 고르면, 그림 쪽을 틀릴 수 있다.**
  - 리케차의 어긋난 8문항은 모두 글로 판별 가능했다(Q097 39쪽만 글 없음).
  - 첫 실제 실행에서 `citationAlignments`와 원본을 대조해 release에 적는다.
- **검토 출력이 길어진다.** 문항당 수십 토큰이다. 묶음 시간이 조금 늘 수 있으며, 첫 실행에서 묶음 단계 시간을 리케차(21분)와 비교해 적는다.
- **결과 검증에 예외를 하나 만든다.** 인용 교체만 정확히 허용하도록 위변조 검사로 막는다.

**복원**
- 코드는 git revert와 이전 Cloud Run revision·Pages로 되돌린다. DB 스키마·데이터 변경은 없다.
- 러너는 이전 설치본으로 다시 띄운다.
- 새 정책으로 생성된 판은 계약상 옛 코드에서도 읽힌다. 추가 필드는 manifest·ledger 안에만 있다.

**승인할 범위**
- 사용자 요청 「스펙 써 줘」 → 결정 1(구별 없음)·2(「함께 해」). 개발 루프에 따라 작업 요청이 구현·검사·PR·병합·배포 승인이다.
  - 병합은 API·웹을 자동 배포하지만 서버·웹 코드 변경은 없다.
- 이 계획이 하지 않는 것
  - 실제 강의 자료로 모델 실행. 다음 Main-Quiz 관리자 요청 때 처음 돈다.
  - 공개된 판(리케차 포함)의 근거 재생성
  - 러너 재설치. 병합 뒤 별도로 하며, 다른 세션의 실행 중 작업이 없는지 대시보드로 확인한다.

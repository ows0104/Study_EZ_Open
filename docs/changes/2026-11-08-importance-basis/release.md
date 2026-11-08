# 중요도 근거 통합 — 배포 준비

## 코드 리뷰·검증 결과
- `studyez_contracts/bank/importance.py`(새 파일, 서버 별칭 `server/app/bank_validation/importance.py`)
  - 근거 kind·점수·판정을 둔다: 예고는 Must-Know, 제외는 Optional, 하이라이트는 Important 바닥값, 필기강조형은 +1.
  - 포인트표, 문항 판정(포인트별 최대), 목표 3축(unreviewed 없음), Must-Know 비율 경고(34%), 예고 원문 번짐 보고를 한다.
- 은행 3.3
  - 문항에 `point_ids` 선택 칸을 더했다.
  - importance는 5/4/3/2다.
  - `validate_bank`가 버전별 표로 확인한다. 3.2 이하는 그대로다.
- `exam-point-extract/3`: `point-output-v3.schema.json`·`point-extract-v3.md`. v2와 병렬 경로는 그대로다.
- `generation_v2`
  - 새로 넣은 것: `importance_table`·`target_importance`·`point_id_reasons`·`project_importance`/`restore_importance`
  - `make_document(importance=…)`: snapshot이 tier·importance만 다른 경우를 허용한다.
  - `validate_result`가 투영을 다시 계산하고, 포인트 /3이면 투영을 반드시 요구한다.
  - `quality_reasons`를 `without_retired` 은행으로 잰다(cloze 오탐 수정).
- `connection_generate_v2`
  - 중요도표를 입력에 넣는다(`importanceTable`, 원본 대조에는 `targetImportance`도).
  - point_ids 누락을 보완 사유로 만든다.
  - 조립 때 투영하고 manifest에 `importanceProjection`을 남긴다.
- 지시문
  - author-v2: point_ids, 표 값 옮기기, 제외 포인트는 채점 문항으로 만들지 않기
  - source-v2: target_checks로 근거 확인
- 실행 스크립트 `run.py`·`run-all.sh`(26110803, Map은 26110802의 완료본을 복사).

검사
- 새 검사: 배점 26(관리자 판정 그대로)·투영 파이프라인 3(계산·변조 거절·point_ids 보완과 대체·옛 형식 유지)
- 루트 `pytest tests` 2,169 통과(제외 1: `test_desktop_control` 바로가기, master 동일)
- `map_numbers --check` 정상
- 서버(격리 sqlite, `.env` 없음): bank 33 · root_ 25 · route_contract · retention 통과

## 배포 대상 버전·순서·데이터 변경
- master 병합 → 검사 → API → Pages 자동 배포. server/에는 별칭 파일 하나뿐이고 web/ 변경은 없다.
- API는 3.3 은행을 받을 수 있게 된다. 3.2 이하 은행·운영 Quiz Bank·학습 기록·DB 스키마는 바뀌지 않는다.
- Study Engine 정책표는 이미 importance 1–5를 가진다.

## 배포 후 확인·롤백·필요한 사람 승인
- 배포 영수증과 API health SHA를 확인한다. 롤백은 병합 되돌리기다.
- 감염병리1 재실행은 사용자 「고친 뒤 다시」 요청 범위다(S1·S2를 Codex gpt-6.1-sol로).
- 운영 등록·학생 공개·기존 98문항 판 교체는 별도 승인이다.

## 2026-11-08 첫 실행(26110803)에서 나온 수정 (claude/importance-placeholder)

- 포인트 단계는 성공했다(포인트 70 → 대조 지적 6 → 보완 75 → 재대조 지적 6, 기록만).
- 정규화 모델이 입력의 `importanceTable`을 보고 근거를 목표 3축에 옮겨 적었다(126건).
  - 그중 임상 근거 3건을 시험축에 넣어 `wrong exam basis`가 났다.
  - 초기 지도 오류로 보완 1/3을 썼다.
  - generate가 TP032를 고치지 못해 거절됐다.
- 수정
  - 정규화 입력에서 `importanceTable`을 뺀다.
  - 정규화 결과의 목표 3축을 코드가 자리표시(`unreviewed`, 「조립 때 계산」)로 바꾼다. 3축 값은 조립 때 다시 계산한다.
  - `validate_result`는 포인트 /3 실행의 `initialBrief`가 자리표시인지 확인한다.
  - extract-v2·author-v2에 「3축은 손대지 않는다」를 넣었다.
- 검사: 이번 실패를 재현하는 파이프라인 검사 1개. 루트 2,170 통과, 서버 root_ 26 통과.
- 26110803의 포인트·packet은 그대로 쓰고, 생성만 새 폴더(`generation-2`)에서 다시 돈다. 실패한 `generation/`은 보존한다.
- 다시 돌린 generation-2도 generate에서 거절됐다(`roots: title required`).
  - 정규화 모델이 brief `scope.label`에 범위 설명문 전체(612자)를 넣었다. 앞의 두 실행은 강의 제목을 넣었다.
  - 이후 단계는 scope를 바꿀 수 없어 고칠 길이 없었다.
  - 수정: 정규화 직후 `scope.label`을 packet의 강의 제목으로 정한다. extract-v2에도 적었다. 실패 재현 검사 1개를 더했다.
  - 생성은 `generation-3`에서 다시 돈다. 실패한 `generation-2/`는 보존한다.
- generation-3 진행 기록
  - 첫 저작이 지도 구조 오류(recall units)로 거절됐다. 기존 `connection_authoring_recovery --mode brief-repair`로 기록하고 보완 1회로 교정했다(보완 2/3 사용).
  - 보완 3/3 뒤 마지막 source-2가 Q026에 R026을 tested·provided 두 번 적어 거절됐다(`relation_id: duplicate`).
  - 수정(claude/source-duplicate-claims): `merge_duplicate_claims`를 넣었다. 하나라도 provided·explanation이면 그 역할로, 방향 없이, 시험 점수 없이 합친다.
  - `normalize_source_review`(필수 누락 분할 + 중복 합치기)를 `root_source_gap_recovery`가 쓴다. 증명에 `merges`를 남긴다.
  - brief-repair의 과거 failed generate를 허용한다. 저작 복구의 런타임은 source 복구 직전 것으로 이어 본다.
  - 사본 시험: 거절 재현 → Q026/R026만 합침 → (정답 검수를 가짜로 넣고) 3.3·79문항·과제 58개로 조립, validate_result 통과.
  - 루트 2,172 통과, 서버 root_ 26 통과.
- **17:38 generation-3 조립 성공**(`result.json`, validate_result 통과)
  - 79문항·과제 57·은행 3.3, 정답 검수 ok 75·doubt 4·wrong 0, 원본 대조 ok 64·doubt 15
  - 목표 consistent 75·conflict 7
  - 등급: Must-Know 10%·Core 30%·Important 43%·Optional 16%(운영 Quiz Bank 13·31·41·14%)
  - 미공개다.

## 형식 검사 되돌려주기 (claude/format-retry)
- 오늘 형식 거절 5건 모두, 모델에게 준 `check_result.py`가 잡을 수 있는 오류였다. 모델이 이를 돌리지 않거나 무시했다.
- 이제 어댑터(`runner/root_native_json.NativeJson.file`)가 호출 뒤 같은 검사를 직접 돌린다. 실패하면 오류 문구를 **같은 Codex 세션**에 한 번 되돌려주고(`resume`), 고친 `result.json`을 받는다.
- 판정은 여전히 생성기의 수용 단계가 한다. 어댑터는 거절하지 않아서, 영수증·원문이 남고 기존 복구 도구가 그대로 쓰인다.
- 기록: `check-failure.json`, `provider-followup.json`, 영수증 `proof.followup`. 사용량은 두 호출을 합친다. `validate_stage`가 후속 영수증·세션·합산을 다시 확인한다.
- 내용 수정 상한은 쓰지 않는다. 대신 실패한 단계에 한해 호출이 한 번 는다.
- runner만 바뀐다. 코드 지문 대상과 서버 계약은 그대로다.

## 운영 반입 (claude/root-generation-import)
- 사용자 「남은 거 둘 다 실행해줘」(2026-11-08)를 운영 등록 승인으로 받았다. 공개 범위는 그대로 둔다(지금 판도 `allowed_users=['runner']` 관리자 시범). 학생 공개는 별도 결정이다.
- `server/app/root_learning/generation_import.py`(새 파일)
  - `validate_result`를 다시 확인하고 원본 스냅숏을 묶는다(`lectures/root-reviewed-import/<sha>/<id>`).
  - preflight 때의 control 해시가 같을 때만 진행한다.
  - 새 RootContent를 넣고 활성 revision만 바꾼다. enabled·allowed_users는 그대로다.
  - publication 이벤트 1건과 RootGeneration·PrequizJob(done)을 남긴다.
  - 이전 판·이벤트·세션은 보존한다.
- `reviewed_import.source_records`가 새 정책을 받아 참고 PDF 링크를 낸다.
- 서버 검사: 새 1개(계약 재검증·낡은 preflight 거절·revision 전환·옛 판과 이벤트 보존·공개 범위 유지) + root_ 27·route_contract·retention 통과.
- `publication.py`: preflight(읽기만) → 배포 확인(health revision) → 스냅숏(없을 때만, 다른 바이트면 중단) → 등록 → 전후 대조.
  - preflight 실행 결과: 활성 `main-quiz-reviewed-6143c8c89ad64d9c`, 관리자 시범, 판 2·이벤트 42·세션 2.

# 설계

- **켜는 조건:** 새 ledger를 만들 때 packet `speedStages: true`이면 `contextStages: true`를 기록한다. 이후 회차는 이 표시를 따른다.
- **`context-n`** (native 파일 실행, 지시문 `automation/context-v2.md`)
  - 입력: title·scope·lecture_id·sources·bank·clinical_conflicts
  - 출력: `{clinical_context_status, clinical_context_reason}`(`generation_v2.CONTEXT`)
  - 「일치」가 아니면 그 회차의 정답 검수는 기존처럼 blocked로 남고 모델을 부르지 않는다. conflict이면 보완 사유가 된다.
- **동시 실행:** 「일치」이면 source-n과 medical-n을 동시에 실행한다. 두 단계가 같은 ledger를 쓰므로 쓰기에 RLock을 둔다.
- **정답 검수 재사용**
  - 문항 지문 `medical_question_hash`는 정답 검수 모델이 보는 문항 필드, 그림 sha, 임상 정리 전체로 만든다.
  - 직전 완료 medical 단계와 지문이 같은 문항의 판정을 재사용하고, 나머지만 같은 형식(`clinicalInput`)으로 모델에 보낸 뒤 합친다.
  - 단계 입력(`title·bank·clinicalInput`)은 그대로라서 기존 `medicalInputHash` 검사가 유지된다.
  - 재사용 근거 `medicalReuse`(이전 단계·출력 해시·문항 지문·판정)를 manifest에 남긴다.
- **계약(`validate_result`)**
  - `contextStages` 결과는 회차마다 context 단계를 요구한다.
  - 마지막 `clinicalContext`가 「일치」이고 그 단계의 출력·임상 정리 해시와 맞아야 한다.
  - 마지막 정답 검수의 재사용 판정은 현재 문항 지문·실제 판정과 같아야 한다.

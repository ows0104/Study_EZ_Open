# Main-Quiz /4 옛 배치 규칙 결과의 재검증 호환 — 설계

## 요구사항과 수용 기준
`studyez_contracts/roots/generation_v4.py`(/4 전용)
- `PLACEMENTS = ('evidence', 'answered')`. `evidence`는 2026-11-11-place-by-evidence 규칙, `answered`는 그 이전 규칙.
- `assessment_raw(..., placement='evidence')`: `answered`이면 근거 행이 부분 하나 이상을 답으로 물을 때만 관계를 주장한다(3b17af44와 같다).
- `compile_assessment(brief, bank, raw, placement='evidence')`·`_compile`: `answered`이면 답한 부분이 있는 (문항, 목표/단위)만 배치 인정한다.
  recall 단위로 나뉜 목표에서는 같은 관계 주장이라도 두 규칙의 배치가 달라진다(리케차 U054_1/U054_2).
- `validate_audit`: 두 규칙 중 하나의 compile과 같으면 통과(원자료 assessment만으로는 규칙을 알 수 없다).
- `_judgments4` → `_placement4`: 저장된 판정을 두 규칙으로 조립해 `sourceAssessment`와 같은 규칙을 찾고, 그 규칙의 compile이 `sourceAudit`과 같아야 한다.
  이후 문서·배치·readiness 검사는 그대로 이 audit에서 다시 만든다.
- 수용(고정 입력, `tests/contracts/test_generation_v4.py`):
  - recall 단위 목표에서 옛 규칙으로 만든 결과가 통과하고, 과제가 옛 배치(Q3 → D1_env)다.
  - 관계 주장이 같아도(모든 행이 부분을 답함) 옛 compile 결과가 통과한다.
  - 새 규칙 assessment + 옛 규칙 audit은 `audit is not the compile`로 거절된다.
  - 옛 규칙에서 답한 부분 없는 근거 행 문항은 unplaced로 남은 채 통과한다. 알 수 없는 규칙 이름은 거절된다.
  - `answered` 조립·compile이 3b17af44 코드와 동일하다(6개 고정 입력, 일회성 대조).

## 책임·입출력 계약·오류 상태
- 결과 형식·manifest 키·생성기 출력은 그대로다. 오류 문구도 그대로다.
- 새 규칙 결과의 검사는 이전과 같다. 옛 규칙은 그날 아침까지 받아들이던 결정적 조립 하나만 추가로 인정한다.

## 호환성과 데이터 보존
- /3 이하 경로 불변. runs/·운영 DB·게시된 판을 건드리지 않는다.
- PR #92(evidence-from-citations)와 같은 파일이지만 다른 함수다(#92는 `_unalign4`·`FLAVOR`).

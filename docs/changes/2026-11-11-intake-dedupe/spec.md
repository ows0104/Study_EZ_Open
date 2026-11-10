# 생성기 시작 단계의 반복 값 자동 정리 — 설계

## 요구사항과 수용 기준
`studyez_contracts/roots/generation_v3.intake_projection`(/3·/4 공통, 생성기와 결과 검증이 같은 함수를 쓴다)이 다음을 정리한다. 모두 "첫 번째를 남기고 뒤의 같은 값을 뺀다".

| 대상 | 은행 검사 오류 | 지금 | 바뀐 뒤 |
|---|---|---|---|
| `retrieval_plan[].directions` | `<개념> directions: ID/값 중복` | 실행 멈춤 | 반복 제거 |
| 내용이 완전히 같은 `retrieval_plan` 항목 | `retrieval_plan: ID/값 중복` | 실행 멈춤 | 하나만 남김 |
| 내용이 완전히 같은 `source_summary` 항목 | `source_summary: ID/값 중복` | 실행 멈춤 | 하나만 남김 |
| 문항 `prerequisites` | `<문항> prerequisites: ID/값 중복` | 문항 탈락 | 반복 제거 |
| 문항 `correct_option_ids` | `<문항> answers: ID/값 중복` | 문항 탈락 | 반복 제거 |

- 같은 개념의 회상 계획이 둘인데 내용이 다르면(예산·숙련 목표가 다름) 고르지 않고 지금처럼 멈춘다. 출처 요약도 같다.
- 정리 하나마다 `{'field': '<위치>', 'from': <원래 값>, 'to': <정리한 값>}`을 changes에 남긴다(기존 schema_version·importance 기록과 같은 목록).
- 반복이 없는 은행은 value와 changes가 지금과 같다.
- 수용: 고정 입력 테스트로 다섯 경우가 정리되고 `validate_bank`가 그 오류를 더 내지 않는 것, 내용이 다른 중복 계획은 그대로 오류인 것, 반복 없는 은행은 그대로인 것을 확인한다.

## 책임·입출력 계약·오류 상태
- 정리는 결정적이며 모델을 부르지 않는다. 결과 검증(/3 `check_result`)은 `intake_projection(packet['intakeBank']['bank'])[1] == meta['intakeProjection']`로 같은 정리를 다시 계산한다.
- 남은 오류는 지금처럼 문항 탈락(문항에 속한 오류) 또는 실행 보류(속하지 않는 오류)다.

## 호환성과 데이터 보존
- 이미 끝난 /3 결과의 intakeProjection은 그 결과의 intake 은행에 반복이 없었다면 그대로 맞는다. 운영 반입된 261102_02 /3 결과로 확인한다.
- 은행 스키마·문항 내용·ID는 바꾸지 않는다. 정리 대상은 순서·개수에 의미가 없는 목록뿐이다.

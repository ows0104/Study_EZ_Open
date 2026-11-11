# Main-Quiz /4 옛 배치 규칙 결과의 재검증 호환 — 구현 계획

## 변경 범위·대상 파일·순서
1. `studyez_contracts/roots/generation_v4.py`: `PLACEMENTS`, `assessment_raw`·`compile_assessment`·`_compile`의 placement 인자, `validate_audit`, `_placement4`.
2. `tests/contracts/test_generation_v4.py`: recall 단위 고정 입력과 수용 항목.
3. 로컬 실데이터 읽기 전용 재검증: `runs/_root-generation/*/generation/result.json` 전부(리케차 /4, 261102_02 /3).

## 검사 명령과 성공 조건
- `python -m pytest tests -q -p no:cacheprovider`: 전부 통과(기존 결함 제외, 수를 기록).
- 리케차 결과 `validate_result` 통과.

## 위험·복원·승인할 범위
- 위험: 새 실행이 옛 규칙으로 조립돼도 통과한다. 옛 규칙은 PR #90 직전까지의 정식 규칙이고 같은 판정의 결정적 조립이라 판정을 꾸밀 여지는 없다.
- 복원: 커밋 되돌림. 데이터 변경 없음.
- 병합 = API 배포. 옛 결과 호환 여부는 사용자 결정 대상이며 PR #92와 순서를 맞춘다.

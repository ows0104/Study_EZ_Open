# Main-Quiz /4 문항 배치를 커버 판정에서 분리 — 구현 계획

## 변경 범위·대상 파일·순서
1. `studyez_contracts/roots/generation_v4.py`: `assessment_raw`, `_compile`, `check_coverage`(중복 묶음 조건)
2. `content/prompts/learning-links/v4/coverage.md`: tested_relation_ids 기록, 중복 묶음 조건
3. `tests/contracts/test_generation_v4.py`, `tests/quizbank/test_root_generation_v4.py`: 위 수용 항목
4. 시범 폴더 사본에서 생성기를 --resume으로 다시 돌려 조립만 다시 한다. 모델 호출이 없는지 로그로 확인한다.

## 검사 명령과 성공 조건
- `python -m pytest tests/contracts tests/quizbank -q`: 전부 통과.
- `bank-prompt.json`이 바뀌었으면 `git restore`.

## 위험·복원·승인할 범위
- 승인 범위: 위 파일 구현, 로컬 검사, 시범 재조립(모델 호출 없음), PR 생성. 병합·러너 재설치는 따로 묻는다.
- 위험: 일부만 묻는 문항이 과제로 늘어 학생 분량이 는다. 시범 수치로 보고한다.
- 복원: 커밋 되돌림. 데이터 변경 없음.

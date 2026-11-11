# Main-Quiz 호출 시간 단축 — 구현 계획

## 변경 범위·대상 파일·순서
1. `runner/root_native_json.py` 첫 메시지 인라인(R1), `runner/root_front.py` 프롬프트 뒤 입력 붙이기(R2).
2. `quizbank/connection_generate_v3.py` early-call/1 장치(R3).
3. `quizbank/connection_generate_v4.py` `normalize_input`, 검토 첫 호출·임상 정리 미리 시작(R5·R6).
4. `studyez_contracts/roots/map_tree.py` `provisional_packet`, `runner/root_front.py` `early_normalize`,
   `runner/connection_generation.py` `--generation`(R4).
5. 검사: `tests/quizbank/test_pipeline_overlap.py`, `tests/runner/test_front_overlap.py`,
   `tests/runner/test_root_front.py`(시범 재현 검사: 지시문 파일은 그대로, 프롬프트는 그 지시문으로 시작).
6. 안내: `runner/CLAUDE.md`, `quizbank/CLAUDE.md`.

## 검사 명령과 성공 조건
- `python -m pytest tests/quizbank/test_pipeline_overlap.py tests/runner/test_front_overlap.py -q`
- `python -m pytest tests/quizbank tests/contracts tests/runner tests/studyez_llm tests/quizgen tests/development -q`
- `python -m ruff check --select F821,F841 quizbank runner studyez_llm studyez_contracts`
- `python scripts/map_numbers.py --check`
성공: 새 검사 전부 통과, 기존 검사는 이 변경 전과 같은 결과.

## 위험·복원·승인할 범위
- 인라인해도 모델이 파일을 다시 읽으면 효과가 없다(손해는 입력 토큰뿐). 실측으로만 안다.
- 큰 입력이 매 요청 문맥에 실린다 → 240,000바이트 상한. 넘으면 지금 방식.
- 미리 부른 답의 입력이 차례에 달라지면 헛호출 1번 → 지문이 같을 때만 쓴다(검사).
  검토 첫 호출은 추가 회차가 기존 문항·충돌을 바꾸지 않는다는 계약(`merge_added`)에 기댄다.
- 동시 호출이 늘어난다(추가 회차 1 + 검토 최대 6) → 기계 전체 8 한도(#115) 안.
- 앞 단계가 normalize 끝을 기다린다 → 이전에도 그 뒤에 순서대로 돌던 호출이라 늦어지지 않는다.
- 러너 상태 창: `generation/.early/`·`.native/*.early`는 구간 판정에 들지 않는다(`status_phases.phase_of` 확인).
- 복원: 병합 되돌리기 + 러너 이전 설치본. `.early/`가 남아도 이전 코드는 읽지 않는다(단, `.native/normalize` 자리가 남아 있으면
  이전 코드의 normalize 호출이 자리 충돌로 멈추므로, 되돌릴 때는 진행 중 실행의 `generation/.native/normalize`를 `.early`로 옮긴다).
- 승인 범위(「겹치기까지 같이」): 브랜치 코드·검사·문서, 로컬 검사, PR. 실제 모델 재생은 하지 않는다. 러너 재설치는 #115와 함께.

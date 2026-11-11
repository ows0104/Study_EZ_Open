# Main-Quiz 파이프라인 안정화·시간 단축 — 구현 계획

## 변경 범위·대상 파일·순서
1. `studyez_llm/execution.py` `slot`·`slot_limit`, `studyez_llm/codex.py` `network_failure`·`wait_for_network`, `run`이 자리를 잡음(R3·R5).
2. `quizbank/connection_generate_v3.py` `Stages._call`(R3), `intake_rejections(quiet)`(R2).
3. `quizbank/connection_batches.py` 동시 6(R5), `quizbank/connection_generate_v4.py` 추가 회차 커버 확인 동시(R6).
4. `runner/root_front.py` `checked`·`_session`·`_receipt`·`audits`, 문제은행 접수 검사, 동시 줄(R1·R2·R3·R4).
5. 검사: `tests/runner/test_front_resilience.py`, `tests/quizbank/test_pipeline_resilience.py`,
   `tests/studyez_llm/test_execution.py`(추가), `tests/runner/test_root_front_v3.py`(호출 순서 단정 한 줄).
6. 안내: `runner/CLAUDE.md`, `quizbank/CLAUDE.md`.

## 검사 명령과 성공 조건
- `python -m pytest tests/runner/test_front_resilience.py tests/quizbank/test_pipeline_resilience.py tests/studyez_llm -q`
- `python -m pytest tests/quizbank tests/contracts tests/runner tests/studyez_llm tests/quizgen tests/development -q`
- `python -m ruff check --select F821,F841 quizbank runner studyez_llm`
성공: 새 검사 전부 통과, 기존 검사는 이 변경 전과 같은 결과.

## 위험·복원·승인할 범위
- 동시 6이 계정 한도에 닿을 수 있다 → 합성 검사로는 알 수 없다. `STUDYEZ_ROOT_WORKERS=3`으로 코드 변경 없이 되돌린다.
- 동시 실행이 늘어 노트북 부하가 커진다 → 기계 전체 8로 묶음(`STUDYEZ_CODEX_SLOTS`).
- transport-retry가 끊긴 호출의 일부 사용량을 한 번 더 쓴다 → 단계당 한 번, 네트워크 오류에만.
- 앞 단계 후속 호출이 형식을 고치며 내용을 건드릴 수 있다 → 생성 단계와 같은 문구(「이 오류가 요구하는 것만」), 같은 검사를 다시 통과해야 함,
  거절된 원문 보존.
- 러너 상태 창(다른 세션 작업 중)은 앞 단계 로그 줄 순서가 바뀐 것을 본다(형식은 그대로).
- 복원: 병합 되돌리기와 러너 이전 설치본. 새로 생긴 파일은 읽는 곳이 없어 남아도 무해하다.
- 승인 범위(사용자 요청): 브랜치 코드·검사·문서, 로컬 검사, PR·병합. 러너 재설치는 돌고 있는 두 강의(261104_03·261111_02)가
  끝난 뒤 한다. 실제 모델 재생(자료 전송)은 하지 않는다 — 다음 관리자 버튼 요청이 첫 실측이다.

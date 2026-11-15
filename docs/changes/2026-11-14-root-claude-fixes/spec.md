# Claude 출제 경로 보완 — 설계

## 요구사항과 수용 기준
1. `claude.answered_models`: 결과의 `modelUsage`에서 출력 토큰이 있는 모델을 읽는다. 요청 모델 외의 모델이 있으면
   `[CLAUDE_MODEL_FALLBACK]` SessionError. `models`는 실제 모델의 출력 토큰. `modelUsage`가 없으면 이전처럼 요청 모델.
2. `claude.run`: 첫 메시지를 임시 파일에 쓰고 `run_process(stdin=파일)`로 넘긴다. 제한 시간 = `timeout × factor`(기본 3, 1 미만이면 1).
3. `execution.run_process(stdin=…)`: input과 함께 주면 거절. 없으면 지금과 같다(Codex 경로 불변).
4. `connection_generate_v3.Stages`: 재개 때 완료 단계의 영수증 proof `model`이 지금 모델과 다르면 `_archive`(기존 재개 보관 규칙)로 옮기고 다시 돈다. 영수증이 없는 단계·같은 모델은 그대로.

## 책임·입출력 계약·오류 상태
`studyez_llm/claude.py`, `studyez_llm/execution.py`, `quizbank/connection_generate_v3.py`. 새 오류 상태 없음(모델 전환은 단계 실패, 시간 초과는 기존 model_timeout).

## 호환성과 데이터 보존
지정 없는 Codex 실행은 바뀌지 않는다(같은 모델이라 보관할 단계가 없다). 보관된 단계 기록은 지우지 않는다.

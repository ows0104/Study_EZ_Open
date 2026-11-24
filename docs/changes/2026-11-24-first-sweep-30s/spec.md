# 러너 첫 쓸기 켠 뒤 30초 — 설계

## 요구사항과 수용 기준
- R1 `Agent.sweep_loop`의 첫 대기는 `min(FIRST_SWEEP_SECONDS=30, sweep_seconds)`, 이후는 `sweep_seconds`.
- R2 첫 쓸기 뒤 두 번째 쓸기는 원래 간격을 기다린다.

## 책임·입출력 계약·오류 상태
- `runner/agent.py`만. 쓸기 안에서 하는 일(`publish`, 창의 일시정지 확인)과 실패 처리는 그대로다.

## 호환성과 데이터 보존
- 데이터 변경 없음. `sweep_seconds=0`(`--no-sweep`)이면 지금처럼 쓸기 실을 띄우지 않는다.

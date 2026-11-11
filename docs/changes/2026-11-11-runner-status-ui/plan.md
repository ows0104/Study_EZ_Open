# 러너 상태 창 개편 — 구현 계획

## 변경 범위·대상 파일
1. `runner/status_phases.py`(신규): root-generation 폴더의 단계 파일을 6구간으로 분류, 지난 실행의 구간별 소요 시간 중앙값,
   실행 중 작업의 현재 구간·구간 경과·예상 남은 시간. 구간은 앞으로만 간다(먼저 시작된 구간 중 가장 뒤 것).
2. `runner/status.py`: `JobStatus.generation`(명령의 `--root-generation` 값, 16진 32자만).
3. `runner/status_window.py`: 카드를 고정 높이 캔버스 없이 쌓기, 카드 = 강의명·경과 / 시간 비례 바 / 남은 시간·완료 시각 / 구간 줄.
   개수 요약 한 줄 + 「목록」 펼치기, 상세 기록 펼치기. 단계 이름 기반 7칸 바 제거(텍스트로만 남김).
4. `runner/desktop.py`: 카드 높이 130 고정 제거.
5. 테스트: `tests/runner/test_status_phases.py`(신규), `test_status_window.py` 갱신, desktop 테스트 유지.
6. `runner/CLAUDE.md` 상태 창 문단 갱신.

## 검사
- `python -m pytest tests/runner -q` 통과
- 실제 `runs/`로 창을 띄워 두 강의 카드·구간·예상 시간 확인(스크린샷)

## 위험·복원
표시만 바뀐다. 실행 중인 러너에는 재설치 전까지 영향 없음. 재설치는 실행 중 강의가 끝난 뒤 사용자 확인 후. 되돌리기는 revert.

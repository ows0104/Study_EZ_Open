# Main-Quiz 생성→선지 시간 단축 1차(선지 묶음) — 구현 계획

## 변경 범위·대상 파일·순서
1. `quizbank/root_mcq.py`: `BATCH` 40 → 12, `WORKERS` 3 → 8, 작성 스키마의 `jokbo`를 객체 또는 null로.
2. `content/prompts/learning-links/mcq/write.md`: 「source가 jokbo가 아니면 jokbo 칸은 null」 한 줄.
3. `runner/connection_generation.py`: 게시·근거 뒤 선지와 순서 맞추기 판정을 나란히. `runner/root_order.py`는 머리말 한 줄.
4. `tests/quizbank/test_root_mcq.py`: 묶음 크기·null `jokbo` 검사. `tests/runner/test_connection_generation.py`: 두 단계가 다 불리는지.
5. 실제 묶음 재생 한 번(문항 30개, 올리지 않음)으로 시간과 스키마 확인.

## 검사 명령과 성공 조건
- `python -m pytest tests/quizbank tests/runner -q` — 새 검사 통과, 회귀 없음.
- 재생: 저장된 261123_03 판의 문항 30개를 15문항 두 묶음으로 한 회차. 두 묶음 모두 300초 안, 다시 받기 0번, 검사 통과 오답이 나온다.

## 위험·복원·승인할 범위
- 위험: 문항 180개 강의의 묶음이 5 → 15개로 늘어 Codex 자리 8을 선지가 다 쓰는 동안 같은 PC의 다른 강의 단계가 자리를 기다린다(총 호출 시간은 같다).
  묶음이 작아져 같은 강의 오답끼리 덜 겹치게 보는 범위가 준다(문항마다 `same_lecture`는 그대로 받는다).
- 복원: 상수 둘과 스키마·지시문 한 줄을 되돌리고 러너 재설치. 올라간 선지는 그대로 남는다.
- 승인 범위: 위 파일과 이 폴더, 로컬 검사·재생·Draft PR. 병합 뒤 러너 `.runtime` 재설치와 /4 단계 삭제·재배치는 따로.

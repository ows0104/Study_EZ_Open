# Main-Quiz 앞 단계 'Different title' 보류 수정 — 구현 계획

## 변경 범위·대상 파일·순서
1. `runner/root_front.py`: `failed`(실패 기록 공용), `accept`(title 맞춤+검사+실패 기록), extract·repair가 accept 사용.
2. `tests/runner/test_root_front.py`: 다른 title(Map·points·repair) 수용·원문 보존·modelTitle, 검사 실패가 failed로 남는지.

## 검사 명령과 성공 조건
- `python -m pytest tests/runner/test_root_front.py tests/runner/test_root_front_v3.py -q`: 전부 통과
- `python -m pytest tests/runner tests/contracts -q`: tkinter 없는 환경의 GUI 테스트 외 통과

## 위험·복원·승인할 범위
- 승인 근거: 사용자 제보 2026-11-11 「작업 중지·실패 · Quiz Bank 를 못 만들었다: Main-Quiz 앞 단계 보류: Different title」(수정 요청).
- 러너 코드만. 운영 데이터·DB 변경 없음. 되돌릴 때는 revert 후 러너 재설치.

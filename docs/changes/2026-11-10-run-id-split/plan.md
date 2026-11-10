# 띄어쓴 필기자 이름으로 생긴 중복 run 수정 — 구현 계획

## 변경 범위·대상 파일·순서
1. `runner/filenames.py`: 작성자 정규식에 글자 사이 띄어쓰기 허용, 저장 시 공백 제거.
2. `tests/runner/test_timetable_identity.py`: 실제 파일명 3개 파싱, 콜레라·렙토스피라 run ID 회귀 검사.

## 검사 명령과 성공 조건
- `python -m pytest tests/runner/test_timetable_identity.py -q` 통과, 수정 전 코드에서는 새 검사 2개 실패.
- `python -m pytest tests/runner -q` 통과(로컬 `.venv`가 필요한 바로가기 검사 1개는 환경 사유).
- 실제 SynologyDrive 필기 전체 전후 run ID 대조: 바뀌는 것은 의도한 2개뿐.

## 위험·복원·승인할 범위
코드 변경은 git revert로 되돌린다. 운영 DB 중복 행 정리는 별도 승인 후 진행한다.

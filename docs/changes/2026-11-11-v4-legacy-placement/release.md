# Main-Quiz /4 옛 배치 규칙 결과의 재검증 호환 — 배포 준비

## 코드 리뷰·검증 결과
- 사람 build 승인 미기록: 이 작업은 다른 세션의 지시로 시작했고 사용자 발언이 없다. 그래서 `development.py verify`가 거절한다.
  사용자가 호환 여부를 정하면 그 발언으로 `approve` 후 `verify`를 다시 기록한다.
- 로컬 검사(기록 도구 밖, 2026-11-11):
  - `python -m pytest tests -q -p no:cacheprovider`: 2728 통과 · 3 건너뜀 · 1 실패.
    실패 1은 `tests/runner/test_desktop_control.py::test_shortcut_installer_supports_korean_filename_in_windows_powershell`
    (PowerShell PathNotFound, 바로가기 설치기). 이번 변경과 무관한 기존 결함이며 PR #92 기록에도 같은 1건이 있다.
  - `tests/contracts/test_generation_v4.py`: 38 통과(새 4개 포함).
  - 3b17af44의 `assessment_raw`·`compile_assessment`와 새 `placement='answered'`가 6개 고정 입력에서 동일(일회성 대조 스크립트).
  - 실데이터 읽기 전용 재검증: 리케차 261110_03 /4 `fa71412a…` master 거절 → 이 브랜치 통과. 261102_02 /3 `1c484a7b…` 통과.

## 배포 대상 버전·순서·데이터 변경
- 공용 계약만 바뀐다. 병합 = API(Cloud Run) 배포. 러너는 새 실행을 계속 현재 규칙으로 만들므로 러너 재설치는 필요 없다.
- DB·runs/·게시된 판 변경 없음.
- PR #92와 같은 파일의 다른 함수. 나중에 병합하는 쪽이 rebase한다.

## 배포 후 확인·롤백·필요한 사람 승인
- 확인: 리케차 결과를 다시 가져오기·재게시할 수 있는지(사용자가 필요할 때).
- 롤백: 커밋 되돌림, 이전 Cloud Run revision.
- 필요한 결정: 옛 /4 결과를 계속 검증할지(사용자). 정해지기 전에는 병합하지 않는다.

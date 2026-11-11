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
- 필요한 결정: 옛 /4 결과를 계속 검증할지(사용자).

## 실제 경과 (2026-11-11 사후 기록)
- PR #93은 사용자 결정 전에 `ows0104` 계정으로 병합됐다(02:56Z, 939e51a4). 이 작업 세션이 병합한 것은 아니다.
  같은 시각 #92가 병합됐고, 뒤이은 PR #94(place-by-review, `review` 배치)가 이 `PLACEMENTS` 위에 만들어졌다.
  API는 76c3e87a에서 배포됐고(#94 실행은 더 새 커밋에 밀려 배포를 건너뜀), 러너는 76c3e87a로 다시 설치됐다.
- 사용자 결정(이 세션 채팅): 「아니오로 할게. 그냥 새로 다시 만들게.」 옛 /4 결과의 호환은 필요 없고,
  리케차 261110_03은 새 러너(`review` 배치)로 다시 만든다.
- 코드는 되돌리지 않는다. #94의 `_placement4`·`PLACEMENTS`가 이 변경에 기대고, 표시 없는 원장으로 이어 가는 실행은
  `evidence` 규칙을 쓴다(`connection_generate_v4`). 옛 규칙 경로는 남지만 새 실행은 쓰지 않는다.
- 회상 단위 배치 문제(아래 부수 발견)는 #94의 `review` 규칙(`_answered_units`, `summarize(answered)`)이 고쳤다.
  검사: `tests/contracts/test_review_placement.py`의 recall 단위 3개(master 972df190, 66개 관련 검사 통과).
- build 승인·`verify` 기록은 없다. 위 사용자 발언은 이 변경의 승인이 아니라 호환이 필요 없다는 결정이다.

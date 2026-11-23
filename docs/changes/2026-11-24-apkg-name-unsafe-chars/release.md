# 예습 덱 파일 이름에서 Windows 금지 글자를 뺀다 — 배포 준비

## 코드 리뷰·검증 결과
- `tests/runner/test_apkg_name_unsafe.py`: 고치기 전(origin/master의 `deck.py`) 2 실패·2 통과, 고친 뒤 4 통과.
  - 실패 둘은 R1(새 덱)과 R4(`:`가 든 마디가 이미 나간 덱)다. 이름 그대로 `[261125_07] 암면역((분반) A: 김태민 (분반) B: 김범석) 예습`이 나왔다.
  - 고친 뒤 이름은 `[261125_07] 암면역((분반) A 김태민 (분반) B 김범석) 예습`이고, 그 이름으로 실제 파일을 만든다.
- `tests/runner tests/quizgen`: 1424 통과·1 건너뜀·1 실패.
  - 실패는 `test_desktop_control.py::test_shortcut_installer_supports_korean_filename_in_windows_powershell` 하나다.
  - 새 worktree에 `.venv\pyvenv.cfg`가 없어서 실패했다(설치 스크립트가 저장소의 .venv를 읽는다). 이 변경과 관계없다.
- 경계: 덱 이름·guid·재개 판정 입력(`lecture`)은 바뀌지 않는다(R2).

## 배포 대상 버전·순서·데이터 변경
- 대상은 이 PR의 병합 커밋이다. 러너 코드만 바뀐다. API·웹은 병합 때 자동 배포되지만 이 변경과 관계없다.
- 러너는 `.runtime/main-quiz-<sha12>`로 새로 설치한다.
- 데이터 변경은 251126_15의 덱 빌드 하나다. `--resume …/prequiz/261123-1826`이 모델 단계를 건너뛰고 덱 빌드부터 잇는다.

## 배포 후 확인·롤백·필요한 사람 승인
- 확인: `runs/251126_15/prequiz/261123-1826/`에 `.apkg`가 생기고, `pre_run.meta.json`의 `deck_name`이 `:`가 든 원래 덱 이름 그대로인지 본다.
- 롤백: git revert. 이미 만든 덱 파일은 그대로 둔다.
- 병합(자동 배포)은 사용자 승인이 따로 필요하다.

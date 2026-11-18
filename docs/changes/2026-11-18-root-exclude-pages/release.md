# Main-Quiz 운영자 제외 쪽(page-withhold/1)과 261109_02 재출제 — 배포 준비

## 코드 리뷰·검증 결과
- 2026-11-18 로컬(Windows, anaconda3 python) 결과:
  - `tests/runner tests/quizbank tests/contracts`: 2401 통과·1 건너뜀·1 실패.
    실패는 `test_desktop_control::test_shortcut_installer_supports_korean_filename_in_windows_powershell`(PowerShell PathNotFound)이다.
    배포 커밋 96bdfb4b에서도 같은 검사가 같은 모양으로 실패한다. 이 PC 환경 탓이고 이 변경과 무관하다.
  - `tests/quizbank tests/contracts` 단독: 1525 통과.
  - `tests/development tests/studyez_llm`: 126 통과.
  - `scripts/map_numbers.py --check`: 통과.
  - `development.py verify --check regression`: 새 검사와 앞 단계·생성기 검사 묶음, 종료 0.
- 리뷰에서 본 경계:
  - 모델 입력을 만드는 곳 셋(앞 단계·생성기·근거 보강)만 가린 사본을 쓴다. 지문 검사와 학생 crop은 원본을 쓴다.
  - quizbank는 runner를 import하지 않는다.
  - 기록이 없는 자료는 `pages()`가 빈 값이라 지금과 같은 입력이다.

## 배포 대상 버전·순서·데이터 변경
- 대상: PR #221 병합 커밋. 서버·웹 코드 변경은 없다. 병합하면 자동 배포는 돌지만 API·웹 동작은 같다.
- DB·스키마 변경 없음.
- 러너는 병합 커밋으로 `.runtime/main-quiz-<sha12>`를 새로 설치하고 바꿔 띄운다(install_runtime.py).
- 그 뒤 운영 데이터 순서:
  1. `runs/page-exclusions.json`에 261109_02 행을 쓴다.
  2. restart+replacePublished 요청 하나를 넣는다(`C:\sez\req_261109_02.py --apply`).
  3. 영수증은 `runs/_development/2026-11-18-root-exclude-pages/receipt.jsonl`에 남긴다.

## 배포 후 확인·롤백·필요한 사람 승인
- 확인:
  - 새 러너 에이전트의 PYTHONPATH가 새 설치본이다.
  - 새 generation 폴더에 `source-0.pdf.withheld-pages.json`이 있다.
  - `front/material/S1.md`의 36~48쪽이 안내 문구이고 전체가 76쪽이다.
  - 게시 뒤 root_control.revision이 새 판이다.
- 롤백:
  - 코드는 git revert와 옛 runtime 바로가기 백업.
  - 기록 파일 행을 지우면 이후 요청은 원본 전체로 돈다.
- 승인: 운영 DB 쓰기는 위 요청 하나다(사용자 「교체한다」, intent.md). 모델 지정 파일은 쓰지 않는다.

# Main-Quiz 공개 판 중복 재판정·선지 병렬 — 배포 준비

## 코드 리뷰·검증 결과
2026-11-12 로컬(worktree `../Study_EZ_dedupe-published`, origin/master ceff852d 기준):
- 회귀: `pytest tests/contracts tests/quizbank tests/runner` — 2220 통과·1 건너뜀·1 실패. 실패는 `test_desktop_control.py::test_shortcut_installer_supports_korean_filename_in_windows_powershell`(바로가기 설치기, 기존 결함, 이 변경이 건드리지 않음). 기록 `runs/_development/2026-11-12-dedupe-published/*-regression.log`
- 새 검사: `tests/quizbank/test_dedupe_published.py` 4, `tests/runner/test_dedupe_published_runner.py` 4, 선지 묶음·강의 병렬 3(기존 18에 더해) 통과.
- 서버: `-m tests root_restart` 통과(duplicatesOnly 422 규칙·packet 표시·공개 판 유지). `-m tests root` 38 중 36 통과 —
  실패 2(`test_root_map_tree`, `test_root_map_tree_v3`)는 로컬 서버 venv에 PyMuPDF가 없어 import에서 실패(이 변경과 무관, CI에서 돈다).
- 실제 5편 무모델 재생(A4): 이 PC의 게시 결과에 이전 판정을 그대로 돌려주는 가짜 판정으로 duplicates-only를 돌렸다.
  모두 과제·커버 행이 이전과 같고 `generation_v4.validate_result`를 통과했다. 재판정 호출 수: 진단 1·치료원칙 1·병인론 2·병리2 2·피코르나 1.
  치료원칙 결과는 러너의 `completed_result`(영수증 `validate_all` 포함)도 통과했다.
- 선지 병렬: 병합 전 worktree 코드로 2026-11-12 13:3x부터 수정 대상 밖 18강의를 3강의씩 작성·업로드 시작(서버 선지 경로는 #118로 이미 배포).
- 확인하지 못한 것: 실제 모델이 묶는 중복의 양과 타당성. 운영 실행의 manifest `duplicatesOnly.changedGroups`로 본다.

## 배포 대상 버전·순서·데이터 변경
- PR 병합 → master 검사 → API → 웹 자동 배포. DB 스키마·결과 형식·서버 검증 변경 없음(RequestIn 선택 필드 하나).
- 러너: 병합 커밋으로 `.runtime/main-quiz-<sha12>` 설치 → 도는 작업이 없을 때 에이전트 교체.
- 운영: 5편(261102_02·03·05, 261104_03, 261111_02)에 「중복만 다시 판정」 요청 → 러너가 게시하면 학생은 새 판을 본다(학습 기록 미승계, 사용자 확인).
  선지는 새 판 게시 뒤 그 5편까지 포함해 공개된 감염과 면역 전부에 붙인다.

## 배포 후 확인·롤백·필요한 사람 승인
- `/api/health` revision, 러너 `agent.lock` pid와 PYTHONPATH.
- 5편마다: 새 실행 폴더의 `generation/result.json` manifest `duplicatesOnly`(판정 목표·바뀐 묶음·과제 전후), 서버 control이 새 판, 근거 asset이 새 판 이름.
- 선지: 강의마다 `choices/<revision>.json` 요약(작성·건너뜀·실패 묶음), 업로드 성공 로그.
- 롤백: `git revert` PR. 판은 옛 판이 DB에 남아 있어 control을 되돌릴 수 있다(별도 조치). 선지 asset을 지우면 그 강의의 선지가 꺼진다.
- 승인: 사용자 2026-11-12 요청과 질문 답(intent.md). 위장관·피부연조직 중복 재판정·다른 과목은 범위 밖.

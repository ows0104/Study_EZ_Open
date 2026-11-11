# Main-Quiz 단답·나열 선지 보기 — 배포 준비

## 코드 리뷰·검증 결과
2026-11-12 로컬 검사(worktree `.worktrees/recall-choices`):
- `python -m pytest tests/contracts tests/quizbank`: 1379 통과.
- 파이프라인에서 떼어 낸 뒤 `tests/runner`의 선지·게시 경로 검사 43 통과. 그 전 전체 실행: 831 통과, 1 실패 — `test_desktop_control.py::test_shortcut_installer_supports_korean_filename_in_windows_powershell`.
  바로가기 설치기 검사이며 이 변경이 건드리지 않는 기존 결함이다(대시보드 완료 기록의 「바로가기 설치기 1 기존 결함」).
- 서버 `-m tests recall_choices` 1 통과, `main_quiz` 7 통과, `route_contract` 통과, `root` 36 중 34 통과.
  실패 2(`test_root_map_tree`, `test_root_map_tree_v3`)는 로컬 서버 venv에 PyMuPDF가 없어서다(`No module named 'fitz'`). 이 변경과 무관하다.
- 웹 `npm run typecheck` 통과.
- 화면: `web/tests/root-recall-choices.test.cjs` 2 통과(검사용 API `server/tests/serve_main_quiz_recall_fixture.py`), 기존 `root-learning.test.cjs` 8 통과.
  화면 검사 중 찾아 고친 결함: 다음 문항이 그려지는 첫 순간에 앞 문항의 「폈음」 값으로 선지가 비쳤다(`RootSolve`의 폈음 상태를 문항 키에 묶음).
- 실제 모델로 선지를 써 본 적은 없다(시범 미실행). 오답 품질은 아직 확인되지 않았다.

## 배포 대상 버전·순서·데이터 변경
- DB 스키마·기존 데이터 변경 없음. 새 asset 종류 `root_choices`는 코드 목록(`ASSET_KINDS`)에만 더한다.
- 순서: master 병합 → API → 웹 자동 배포. 러너 재설치는 필요 없다 — 게시 경로(`runner/connection_generation.py`)는 master와 같다.
- 누군가 `python -m runner.root_choices`를 돌려 올리기 전에는 아무 판에도 선지가 없으므로 화면·API는 지금과 같다.

## 배포 후 확인·롤백·필요한 사람 승인
- 확인: API health의 revision, 선지 asset이 없는 강의의 풀이 화면이 그대로인지.
- 롤백: 병합 커밋 revert. 올린 asset을 지우면 그 강의의 선지가 꺼진다.
- 따로 승인: 리케치아 한 강의 시범(약 3회 호출), 이번 블록 공개 판 보강, 학생에게 처음 보이는 시점.

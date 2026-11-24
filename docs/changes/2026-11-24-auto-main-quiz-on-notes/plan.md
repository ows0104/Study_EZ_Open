# 필기 업로드 시 Main-Quiz 자동 요청 · 러너 자동 시작 15초 — 구현 계획

## 변경 범위·대상 파일·순서
1. 자동 시작 15초(R7)
   - `runner/desktop_control.py` `AutoStart` 기본값 60 → 15, `tests/runner/test_desktop_control.py` 경계값.
   - 문구: `runner/CLAUDE.md`, `scripts/install-runner-desktop.ps1`(바로가기 설명), `scripts/runner_desktop_jobs.py`(일감 단계 「프로그램 자동 시작」).
2. 자동 요청(R1–R6)
   - `server/app/routes/root_generation.py`: `request` → `submit(…, auto=None)` 분리, `auto_request`, `owns`(runner 소유 요청은 관리자 누구나).
   - `server/app/routes/admin.py`: `complete_uploads`가 commit 뒤 `_auto_main_job(db, lecture, fresh, user)`.
   - `server/app/routes/prequiz_jobs.py` `claimed_job`: origin `auto`도 요청에 묶는다.
   - 검사: 새 `server/tests/test_root_auto_request.py`, `server/tests/test_smoke.py`의 「필기 업로드만으로 출제하지 않는다」 3줄을 새 동작으로.
3. 문서: `docs/development/README.md` 「사람에게 묻는 것」, `runner/CLAUDE.md`, `docs/architecture.md`.
   - `README.md` 「현재 흐름」·`docs/pipeline.md`는 파이프라인 문서 세션(docs/pipeline-current)이 고치는 중이라 건드리지 않고 그 세션에 알린다.

## 검사 명령과 성공 조건
- 러너: `python -m pytest tests/runner/test_desktop_control.py -q`.
  - 바로가기 설치 검사 1개는 worktree에 `.venv`가 없어 실패한다(환경). 메인 체크아웃 `.venv`가 있는 곳에서 통과하는지 따로 본다.
- 서버(`server/`, 메인 체크아웃 venv, `PYTHONPATH=..`): `-m tests root_auto_request`, `smoke`, `bank_auto`, `root_`, `jobs`.

## 위험·복원·승인할 범위
- 위험
  - 필기가 올라온 강의는 사람이 누르지 않아도 Codex로 자료가 가고, 통과하면 학생에게 공개된다(사용자 결정).
    잘못 들어간 편은 러너 창이나 관리자 화면에서 그 일감만 취소한다.
  - TBL·블럭 첫 수업도 자동으로 만들어진다(사용자 「일단 만들기 시작하자」).
  - 족보가 필기보다 늦게 등록되는 강의는 족보 없이 출제된다.
  - 예습 자동 일감과 하루 상한 12편을 같이 쓴다. 하루에 예습과 복습 합이 12를 넘으면 뒤의 것이 보류된다.
  - `uploads/complete`가 원본을 읽어 출제용 사본을 만드는 동안 길어진다(버튼 요청과 같은 일, 러너 시한 600초).
- 복원: git revert → 자동 배포. 이미 선 요청·일감은 남으며 관리자 화면에서 취소한다.
- 승인: 사용자 2026-11-24 요청과 세 질문의 답(공개 범위·제외·대상 시점). 로컬 구현·검사·Draft PR까지.
  - master 병합은 자동 배포이며, 이번에는 「학생에게 새로 공개되는 범위」가 바뀌므로 병합 전에 묻는다.
  - 러너 재설치(15초 반영)는 지금 러너를 맡은 세션과 겹치지 않게 사용자 확인 뒤 한다.

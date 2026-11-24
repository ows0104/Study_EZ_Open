# 필기 업로드 시 Main-Quiz 자동 요청 · 러너 자동 시작 15초 — 배포 준비

## 코드 리뷰·검증 결과
- 서버 `complete_uploads`
  - 자료를 먼저 commit하고 `_auto_main_job(db, lecture, fresh, user)`을 부른다.
  - `fresh`에 `notes_current`가 있을 때만 `root_generation.auto_request`로 간다. 같은 파일 재확인은 `fresh`가 비어 요청하지 않는다.
- `root_generation.auto_request`
  - 건너뛰는 강의: 실습·CBL·PBL, 공개된 판이 있는 강의, 요청이 한 번이라도 있었던 강의.
  - 버튼 요청이 거절하는 경우(PDF 아님 등)는 예외를 삼키고 이유를 로그에 남긴다. 업로드 응답은 200이다.
  - 요청 전에 `db.expire_all()`. 이 저장소의 세션은 `expire_on_commit=False`라, 방금 만든 자산의 업로드 시각이 메모리 값으로
    지문에 들어가면 관리자가 나중에 같은 입력으로 요청할 때 다른 요청으로 갈린다. 검사에서 실제로 걸려 고쳤다.
- `root_generation.submit(…, auto=…)`: 일감 origin `auto`, 요청자 빈칸, 하루 자동 상한을 넘으면 `held`.
- `owns`: `runner` 소유 요청은 관리자 누구나 이어 하기·새로 출제. 다른 관리자의 요청 거절은 그대로다.
- `claimed_job`: origin `auto` 일감은 서버의 자동 요청(requestId `auto-…`)일 때만 자기 `RootGeneration`에 묶는다.
  그 밖의 자동 일감은 지금처럼 묶이지 않는다(`test_root_job_claim`).
- 러너: `AutoStart` 기본값 15초. 러너의 claim·출제 코드는 바뀌지 않았다.

## 검사(2026-11-24 실행)
- 서버(`server/`, 메인 체크아웃 venv, `PYTHONPATH=..`)
  - 새 `test_root_auto_request`: 통과. 첫 업로드 요청·재확인·필기 교체·claim 연결·CBL·공개판·PDF 아님·상한 보류·관리자 이어 하기·새로 출제.
  - `test_smoke`: 통과. 「필기 업로드만으로 출제 작업을 만들지 않는다」 3줄을 새 동작으로 바꿨다.
  - `test_bank_auto`·`test_bank_auto_exclusions`·`test_root_restart`·`test_root_generation`: 통과.
  - dev 기록 `verify --check server`(위 6개와 `test_root_job_claim`): exit 0.
  - `-m tests root_`(59개): 57 통과, 2 실패. `prequiz`(4개): 통과.
    - 실패 2개는 `test_root_map_tree`·`test_root_map_tree_v3`다. venv에 `pymupdf`가 없는 환경 문제이고 이번 변경과 무관하다.
    - 첫 실행에서는 `test_root_job_claim`도 실패했다. 「자동 일감은 요청에 묶이지 않는다」는 기존 보호였다.
      그래서 자동 일감은 **서버가 스스로 넣은 요청**(requestId가 `auto-`로 시작)일 때만 묶이게 좁혔고, 그 검사는 고치지 않고 통과한다.
  - `test_job_board`·`test_runner_desktop`·`test_route_contract`·`test_lecture_notes`·`test_main_migration`·`test_notes`·`test_deck_watch`·
    `test_root_web_generation`·`test_root_parallel_generation`·`test_root_one_click`: 통과.
- 러너
  - `python -m pytest tests/runner/test_desktop_control.py -q`: 12 통과, 1 실패.
    - 실패 1개는 바로가기 설치 검사다. worktree에 `.venv/pyvenv.cfg`가 없어서 나는 환경 문제이고 이번 변경과 무관하다.
  - dev 기록 `verify --check runner`(그 1개 제외): exit 0.
- 실행하지 않은 것: 운영 서버·실제 러너에서의 자동 요청. 병합 뒤 첫 필기 업로드에서 확인한다.

## 배포 대상 버전·순서·데이터 변경
- master 병합 → 자동 검사 → Cloud Run(API) → Pages(웹, 변경 없음).
- DB 스키마 변경 없음. 배포 뒤 새로 올라오는 올해 필기부터 `root_generation`·`prequiz_job` 행이 자동으로 생긴다.
- 러너: 자동 요청은 지금 설치본으로도 돈다. 15초는 `.runtime` 설치본을 새로 깔고 러너를 다시 띄워야 반영된다.

## 배포 후 확인·롤백·필요한 사람 승인
- 확인: 병합 뒤 처음 올라오는 올해 필기에서
  - `uploads/complete` 응답의 `queued`에 bank·auto 일감이 실려 오는지(러너 로그),
  - 관리자 러너 화면에 「올해 필기가 올라왔다 — Main-Quiz 앞 단계…」 줄이 「· 자동」으로 서는지,
  - 러너가 그 일감을 `--root-generation`으로 도는지 본다.
- 롤백: git revert → 자동 배포. 이미 선 요청은 관리자 화면에서 취소한다.
- 사람 승인이 필요한 것
  - master 병합: 자동 배포이고 「학생에게 새로 공개되는 범위」가 바뀐다(필기만 올라오면 공개까지 간다).
  - 러너 재설치(15초 반영): 러너를 맡은 세션 하나가 한다.
- 알릴 것: `README.md` 「현재 흐름」·`docs/pipeline.md`는 파이프라인 문서 세션(docs/pipeline-current)이 고치는 중이라 건드리지 않았다.
  그 문서에 「올해 필기 첫 업로드 → Main-Quiz 자동 요청」을 넣어야 한다.

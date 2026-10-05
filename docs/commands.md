# 명령 안내

저장소 루트에서 실행한다. Python이 PATH에 없으면 아래 `python`을
`.venv/Scripts/python.exe` 또는 설치된 Python의 절대 경로로 바꾼다.
PowerShell에서 한글 출력이 깨지면 먼저 `$env:PYTHONIOENCODING = "utf-8"`을 설정한다.

옵션의 정본은 `python -m runner --help`다. 생성·업로드 명령은 로컬 산출물이나
운영 서버를 변경하므로 단순 코드 점검에는 아래 검사 명령을 사용한다.

## 검사

| 대상 | 명령 |
|---|---|
| 루트 Python 전체 | `python -m pytest tests` |
| 컴포넌트 하나 | `python -m pytest tests/runner` (또는 `quizgen`·`quizbank`·`spotter`·`bridge`) |
| 서버 | `server/`에서 `.venv/Scripts/python.exe -m tests` |
| 서버 검사 선택 | `server/`에서 `.venv/Scripts/python.exe -m tests bank` |
| 웹 타입 | `npm --prefix web run typecheck` |
| 웹 빌드 | `npm --prefix web run build` |
| 코드 경계·문서 구조 | `python scripts/map_numbers.py --check` |
| 땡시 세션 동기화 | `python spotter/scripts/sync_shared.py --check` |
| 땡시 배포본 일치 | `python spotter/scripts/deploy_pages.py --check spotter-dist` |

서버 검사는 파일별로 독립 프로세스를 띄운다. `pytest server/tests`로 대신하지 않는다.
로컬 서버 실행은 [서버 README](../server/README.md), 웹은 [웹 README](../web/README.md)를 본다.

## 자료 준비

```powershell
python -m runner jokbo 병리학
python -m runner match 병리학
python -m runner match --all
```

족보 컷은 `runs/_materials/<과목>/<판>/`에 저장된다.
확인한 연도별 매칭은 `runs/_pairs/<과목>.json`, 시간표 원본은 `data/timetable/`에 있다.
족보의 옛 판은 `jokbo --older`, 실습 원본은 `--practical`로 지정한다.

## 덱 만들기

| 할 일 | 명령 |
|---|---|
| 복습 대상 확인 | `python -m runner watch` |
| 복습 생성 | `python -m runner watch --build` |
| 올해 강의 한 편 생성 | `python -m runner watch 병리학 --run-id 261005_01 --build` |
| 같은 편 전체 재생성 | 위 명령에 `--force` |
| 수정 슬라이드 지정 | 위 명령에 `--slides 37,41` |
| 기간을 직접 선택 | `watch --since 2026-10-01 --until 2026-10-06` |
| 블럭 제한 해제 | `watch --all-dates` |
| 예습 링크 대상만 확인 | `python -m runner prequeue --dry-run` |
| 예습 대화 동기화·생성 | `python -m runner prequeue --build` |
| 공유 링크 직접 연결 | `python -m runner preview 251005_01 --url <공유주소>` |

`watch`의 `--run-id`는 올해 강의를 지정한다.
예습은 올해 강의와 매칭한 작년 자료를 사용한다.
`--force`와 증분 수정의 차이, PDF를 직접 처리하는 명령은 [quizgen 안내](quizgen.md)를 본다.

## Quiz Bank

```powershell
python -m runner bank 병리학 --run-id 261005_01
```

웹에서 저장한 ChatGPT 답을 정리·검토하고 바로 업로드한다.
덱의 `publish` 흐름과 별도다. 최초 답 생성과 학생 공개는 캘린더의 Quiz Bank 패널에서 한다.

## 선택·재빌드·업로드

| 할 일 | 명령 |
|---|---|
| 시도 비교 | `python scripts/attempts.py 261005_01` |
| 현재 시도 선택 기록 | `python -m runner chosen 261005_01 --keep --why "선택 이유"` |
| 다른 시도 선택 | `python -m runner chosen 261005_01 --pick <시도폴더> --why "선택 이유"` |
| 선택한 시도를 배포 위치로 승격 | `python -m runner promote 261005_01` |
| 기존 카드로 덱만 다시 빌드 | `python -m runner rebuild` |
| 표시 규칙도 다시 계산 | `python -m runner rebuild --reflag` |
| 다른 작업 폴더 가져오기 | `python -m runner import --from <작업폴더> --dry-run` |
| 가져온 덱의 보류 해제 | `python -m runner release 261005_01` |
| 업로드 대상만 확인 | `python -m runner publish --all --dry-run` |
| 한 편 업로드 | `python -m runner publish --run-id 261005_01` |
| 전체 업로드 | `python -m runner publish --all` |
| 완료 표시 후 업로드 | `python -m runner done 261005_01` |

`publish`는 먼저 서버의 예습 링크를 동기화한다. 서버가 링크의 원본이다.
`--no-prequeue`는 이 단계를 생략하므로 오래된 로컬 링크를 올릴 수 있다.
`--notes-only`는 강의록만, `--no-gate`는 배포 보류 검사를 건너뛴다.
산출물 구조·보존 대상은 [runs 구조](runs-layout.md)를 따른다.

## 상시 러너

```powershell
python -m runner agent
python -m runner agent --once
powershell -ExecutionPolicy Bypass -File scripts/install-agent-task.ps1
```

`agent --once`도 실제 서버 작업을 처리할 수 있다. 연결만 확인하는 명령은 아니다.
Windows 예약 작업은 `StudyEZ Agent`, 로그는 `runs/agent.log`다.
러너 동시성·대기·재시도 정책은 [runner 안내](../runner/CLAUDE.md)를 본다.

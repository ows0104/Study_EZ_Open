# Study_EZ 서버

FastAPI API다. 인증·자료 배급·학습 기록·관리 기능·생성 작업 큐를 담당한다.
실제 생성은 로컬 러너가 수행한다. 수정 위치와 계약은 [CLAUDE.md](CLAUDE.md)에 있다.

## 로컬 실행 (PowerShell)

`server/` 폴더에서 실행한다. 기존 `.env`가 운영 DB를 가리킬 수 있으므로
로컬 DB를 환경 변수로 먼저 지정한다.

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
$env:ENVIRONMENT = "local-test"
$env:DATABASE_URL = "sqlite:///./local_test.db"
$env:RUNNER_TOKEN = "local-runner-token"
.venv/Scripts/python.exe -m app.cli init-db
.venv/Scripts/python.exe -m app.cli seed-timetable
.venv/Scripts/python.exe -m uvicorn app.main:app --reload
```

`local-test`는 파일을 로컬 디스크에 저장하고 `local-test-token`으로 인증한다.
이 모드는 로컬 확인용이다. 웹 연결은 [웹 README](../web/README.md)를 따른다.

## 검사

```powershell
.venv/Scripts/python.exe -m tests
.venv/Scripts/python.exe -m tests bank
.venv/Scripts/python.exe -m tests.test_route_contract
```

검사는 자체 로컬 DB를 사용하며 파일별 새 프로세스에서 돈다.
`pytest server/tests`는 지원하지 않는다. 검사 파일 목록은 `tests/test_*.py`가 기준이다.

## 구조

| 경로 | 역할 |
|---|---|
| `app/main.py` | FastAPI 앱·라우터 연결 |
| `app/routes/` | 학생·관리자·러너·땡시 API |
| `app/models/` | 기능별 SQLAlchemy 모델과 공유 계약 |
| `app/jobs/` | 생성 작업 정책 |
| `app/srs.py` | 기존 퀴즈 복습 간격 |
| `app/study_engine/` | Quiz Bank 문항 선택·숙련도 |
| `app/cli.py` | DB 초기화·시간표 입력·운영 명령 |
| `app/config.py` | 환경 설정 |
| `app/storage.py` | R2·로컬 파일 저장 |

## 업로드와 배포

러너는 `RUNNER_TOKEN`으로 관리자 업로드 API를 호출한다.
서버에서 서명 URL을 받은 뒤 파일을 R2에 직접 PUT하고 업로드 완료를 알린다.
문항·메타데이터는 별도 API로 저장한다. 종류·파일 이름·반영 규칙은
[산출물 계약](../docs/artifact-contract.md)을 따른다.

운영 환경 값은 [.env.example](.env.example), 배포는
[배포 안내](../docs/deployment.md)를 참고한다.
`deploy.ps1` 실행은 운영 변경이며 Git push와 별도다.

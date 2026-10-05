# server 작업 안내

두 앱의 인증·DB·파일 배급·작업 상태를 담당하는 FastAPI 서버다.
`runner`·`quizgen`·`quizbank`를 import하지 않는다.

## 수정 위치

| 책임 | 파일 |
|---|---|
| API | `app/routes/` |
| DB 모델 | `app/models/` — 기존 `from app.models import ...` 유지 |
| 생성 작업 정책 | `app/jobs/`, `app/routes/prequiz_jobs.py` |
| 기존 퀴즈 복습 간격 | `app/srs.py` |
| Quiz Bank 다음 문항 | `app/study_engine/` |
| 설정·인증·저장소 | `app/config.py`, `auth.py`, `storage.py` |
| DB 초기화·호환 칼럼 추가 | `app/cli.py` |

## 검사와 로컬 환경

`server/`에서 `.venv/Scripts/python.exe -m tests`를 실행한다.
파일마다 import 시점에 DB를 설정하므로 독립 프로세스가 필요하다.
하나만 고를 때는 `-m tests bank`처럼 이름 일부를 준다. pytest로 대신하지 않는다.

`server/.env`는 운영 DB를 가리킬 수 있다.
직접 실행할 때는 [README](README.md)의 로컬 DB 환경을 먼저 명시한다.

## 계약

- 새 표·칼럼은 DB 초기화/호환 변경과 코드 배포 순서를 함께 검토한다. 운영 변경 시 DB 준비가 먼저다.
- 라우트 변경 시 `tests/test_route_contract.py`와 호출하는 웹·러너·확장을 확인한다.
- 학생 응답과 관리자 응답을 구분한다. 화면에서 숨기는 것만으로 개인정보가 제거되지는 않는다.
- 기존 퀴즈 간격은 `srs.py`가 계산한다. 웹에 같은 정책을 복제하지 않는다.
- Quiz Bank 정책은 Study Engine이 담당하며 학생 공개는 `open_to_students`를 따른다.
- 카드 전체 교체 시 관리자의 `card_edit` 판정을 다시 반영한다.
- 파일 본문은 R2 서명 URL로 직접 전송하며 계약의 kind와 Content-Type을 유지한다.

push는 API를 배포하지 않는다. 배포 절차는 [배포 안내](../docs/deployment.md)에 있다.
과거 변경 이유는 [원문 기록](../docs/archive/2026-10-06-originals/server/CLAUDE.md)에 보관했다.

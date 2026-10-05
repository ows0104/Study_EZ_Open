# Study_EZ

강의 자료로 예습·복습 덱과 Quiz Bank를 만들고 학생에게 제공하는 프로젝트입니다.
자료 생성은 로컬 PC에서, 로그인·작업 상태·학습 기록·파일 배급은 서버에서 처리합니다.
같은 저장소의 Spotter는 사진을 보고 푸는 별도 땡시 앱입니다.

## 어디부터 읽나요?

| 할 일 | 읽을 문서 |
|---|---|
| 코드 수정 위치 찾기 | [작업 지도](docs/map.md) |
| 실행·검사 명령 확인 | [명령 안내](docs/commands.md) |
| 데이터 흐름 이해 | [현재 구조](docs/architecture.md) |
| 산출물·작업 폴더 확인 | [산출물 계약](docs/artifact-contract.md), [runs 구조](docs/runs-layout.md) |
| 배포·운영 | [배포 안내](docs/deployment.md) |
| 이전 결정의 이유 찾기 | [기록 보관함](docs/archive/README.md) |

## 현재 흐름

```text
올해 필기 PDF ───────────────→ quizgen ──→ Main-Quiz · Anki 덱
작년 필기 PDF + 예습 대화 ───→ quizgen ──→ Pre-Quiz · Anki 덱
필기 PDF + 족보 → ChatGPT 답 ─→ quizbank ─→ Quiz Bank · 근거 슬라이드
                                  ↑
                         runner가 작업을 실행
                                  ↓
                  server: 작업 상태 · DB · R2 파일
                                  ↓
                       web: 캘린더 · 문제 풀이
```

관리자는 웹에서 자료·예습 링크를 연결하고 생성 작업을 요청합니다.
`runner agent`가 서버의 작업을 받아 로컬에서 실행한 뒤 결과를 업로드합니다.
Quiz Bank는 관리자가 학생에게 연 강의만 공개됩니다. 로컬 PC가 자거나 러너가
꺼져 있으면 생성 작업은 진행되지 않습니다.

## 폴더

| 폴더 | 책임 |
|---|---|
| `web/` | Study_EZ 화면 — React·TypeScript |
| `server/` | 두 앱의 API — FastAPI·Postgres·R2 |
| `runner/` | 자료 탐색, 작업 실행, 검증 후 업로드 |
| `quizgen/` | PDF → 예습·복습 카드와 Anki 덱 |
| `quizbank/` | ChatGPT 답 → 구조화·검증·검토 |
| `studyez_llm/` | 생성기 공용 Codex CLI·GPT 실행과 PDF 렌더링 |
| `bridge/` | PDF를 AI 대화에 붙이고 링크·답을 회수하는 Chrome 확장 |
| `spotter/` | 땡시 원본 코드와 수동 관리 데이터 |
| `platform/` | 앱 공용 세션 코드 |
| `data/timetable/` | 학기 시간표 원본 JSON |
| `tests/` | 컴포넌트별 Python 검사 |
| `scripts/` | 운영·점검 도구 |
| `docs/` | 현재 안내. 과거 기록은 `docs/archive/` |

`runs/`·`out/`는 로컬 실행 데이터, `spotter-dist/`는 배포 산출물입니다.
`runs/`에는 사람이 고른 짝·메모·예습 대화도 있으므로 통째로 지우지 않습니다.

## 개발 시작

Python 의존성은 루트 [requirements.txt](requirements.txt), 서버 의존성은
[server/requirements.txt](server/requirements.txt), 웹 의존성은
[web/package.json](web/package.json)에 있습니다.

```powershell
python -m pip install -r requirements.txt
python -m pip install pytest  # 검사 도구
python -m runner --help
python -m pytest tests/runner tests/quizbank
```

서버와 웹은 별도로 실행합니다. 환경 설정과 로컬 실행 명령은
[서버 README](server/README.md)와 [웹 README](web/README.md)를 따릅니다.
덱을 생성하려면 원본 PDF와 ChatGPT 계정으로 로그인된 `codex` CLI도 필요합니다.
모델 선택과 실행 파일 설정은 [GPT 실행 설정](docs/quizgen.md#gpt-실행-설정)을 봅니다.

컴포넌트를 고칠 때는 해당 폴더의 `CLAUDE.md`와 관련 파일부터 읽습니다.
문서의 고정 줄 수·검사 수 대신 코드와 실행 결과를 기준으로 판단합니다.

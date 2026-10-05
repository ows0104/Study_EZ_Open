# 폴더 안내

현재 컴포넌트 책임은 [README](../README.md#폴더), 수정할 파일은 [작업 지도](map.md)에 있다.
이 문서는 옛 경로를 만났을 때와 생성 데이터를 구별할 때 사용한다.

## 소스와 데이터

| 종류 | 경로 | 수정 방법 |
|---|---|---|
| 앱 코드 | `web/`, `server/`, `runner/`, `quizgen/`, `quizbank/`, `bridge/`, `spotter/` | 해당 컴포넌트에서 수정 |
| 공용 코드 | `platform/session/` | 원본 수정 후 Spotter 사본 동기화 |
| 시간표 원본 | `data/timetable/` | 학기별 JSON 수정 |
| 로컬 실행 데이터 | `runs/`, `out/` | [runs 구조](runs-layout.md)를 먼저 확인 |
| 땡시 배포본 | `spotter-dist/` | `spotter/scripts/deploy_pages.py`로 생성 |
| 문서 | `docs/` | 현재 안내 |
| 과거 기록 | `docs/archive/` | 특정 결정의 배경이 필요할 때 읽기 |

`web/`와 `server/`는 배포 설정에서도 참조한다.
폴더를 이동할 때는 빌드·배포 경로와 외부 설정까지 함께 검토한다.

## 옛 이름 찾기

2026-09-14에 저장소를 합치면서 다음 이름을 바꿨다.

| 과거 | 현재 |
|---|---|
| `pdf2anki/` | `quizgen/` |
| `studyez/` | `runner/` |
| `studyez/runner.py` | `runner/cycle.py` |
| `chrome-extension/` | `bridge/` |
| `packages/session/` | `platform/session/` |
| `Spotter_Quiz_source` 저장소 | `spotter/` |
| `Spotter_Quiz` 배포 저장소 | `spotter-dist/` |

2026-10-06에는 큰 파일 내부의 책임을 나눴다. 공개 실행 명령과 서버 모델 import는 유지한다.

| 진입점 | 구현 위치 |
|---|---|
| `python -m runner` | `runner/cli/` |
| `app.models` | `server/app/models/` |
| 서버 작업 정책 | `server/app/jobs/` |
| Anki 카드 모델·스타일 | `quizgen/anki_models.py` |
| 웹 API 타입 | `web/src/types/` |
| Quiz Bank 화면 | `web/src/bank/BankStart.tsx`, `BankSolve.tsx`, `BankQuestion.tsx` |

과거 로그·커밋·보관 문서의 옛 이름은 당시 상태다.
현재 동작은 코드와 현재 안내를 확인한다. 배포는 [deployment.md](deployment.md)를 따른다.

# Study_EZ 작업 안내

이 문서는 공통 작업 규칙만 담는다. [README](README.md)는 프로젝트 입구,
[작업 지도](docs/map.md)는 수정 위치를 찾는 곳이다.

## 읽는 범위

일감과 관계있는 컴포넌트의 `CLAUDE.md`와 코드부터 읽는다.
생성 데이터와 과거 기록을 처음부터 모두 읽을 필요는 없다.

| 작업 | 안내 | 기본 검사 |
|---|---|---|
| 퀴즈·프롬프트 | [quizgen](quizgen/CLAUDE.md) | `python -m pytest tests/quizgen` |
| 러너·업로드 | [runner](runner/CLAUDE.md) | `python -m pytest tests/runner` |
| Quiz Bank 정리 | [quizbank](quizbank/CLAUDE.md) | `python -m pytest tests/quizbank` |
| 웹 화면 | [web](web/CLAUDE.md) | `npm --prefix web run typecheck` |
| API·DB | [server](server/CLAUDE.md) | 서버 폴더에서 `.venv/Scripts/python.exe -m tests` |
| 땡시 | [spotter](spotter/CLAUDE.md) | `python -m pytest tests/spotter` |
| Chrome 확장 | [bridge](bridge/CLAUDE.md) | `python -m pytest tests/bridge` |

## 경계와 원본

- 서버는 로컬 생성기를 import하지 않는다. 클라이언트는 HTTP로 서버에 연결된다.
- 러너의 quizgen 접점은 `runner/deck.py`, quizbank 실행 접점은 `runner/bank.py`다.
- `runs/` 계약은 [산출물 계약](docs/artifact-contract.md)과 [폴더 구조](docs/runs-layout.md)를 따른다.
- 공용 세션 원본은 `platform/session/session.js`다.
- 프롬프트는 실행 입력이다. 문서 정리를 이유로 출제 규칙을 바꾸지 않는다.
- `spotter-dist/`와 생성 JSON은 원본을 수정한 뒤 다시 만든다.

## 작업 원칙

현재 사용자 요청의 범위 안에서 진행한다. 기존 관리자 지시(2026-09-14)는
커밋·push·배포·force-push·파일 삭제를 허용했다. 해당 작업을 할 때는 대상과 영향을
먼저 확인하고, 다른 세션의 미커밋 변경을 섞지 않는다. 커밋할 파일은 경로로 지정한다.

`server/.env`는 운영 DB를 가리킬 수 있다. 테스트는 명시적인 로컬 DB로 실행한다.
`runs/`에는 재생성할 수 없는 사용자 기록도 있다. 삭제·이동 전에는 보존 대상을 확인한다.

산출물 존재와 이번 실행 성공을 구별한다. 실패·대기·입력 없음은 별도 상태로 보고하고,
부분 성공 뒤의 요약 출력도 실패할 수 있음을 고려한다.

새 규칙은 확인된 실패나 사용자의 명시적 결정에 근거한다. 허용을 의무로 바꾸거나
불확실한 추측을 고정 정책으로 적지 않는다. 임시 규칙은 해제 조건을 함께 적는다.

문서는 현재 사용법·계약 중심으로 짧게 유지한다. 실패 사례·실측·결정 이력은
[archive](docs/archive/README.md)에 두고 필요할 때만 연결한다.

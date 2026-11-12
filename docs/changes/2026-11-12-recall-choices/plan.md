# Main-Quiz 단답·나열 선지 보기 — 구현 계획

intent의 D1~D4는 2026-11-12에 정해졌다. 구현은 사용자가 요청한 뒤에 시작한다.

## 변경 범위·대상 파일·순서

| 순서 | 영역 | 파일 | 내용 |
|---|---|---|---|
| 1 | 계약 | 새 `studyez_contracts/roots/choices.py`, `tests/contracts/` | `root-choices/1` 형식과 문항별 검사 |
| 2 | 출제 | 새 `quizbank/root_choices.py`, 새 `content/prompts/learning-links/choices/write.md`, `tests/quizbank/` | 판 문서 → 40문항 묶음 호출 → 검사 → asset JSON |
| 3 | 연결 | 새 `runner/root_choices.py`(수동 명령), `tests/runner/` | 게시된 실행 찾기·하위 프로세스 실행·asset 업로드. `connection_generation.py`는 건드리지 않는다 |
| 4 | 서버 | `server/app/models/lectures.py`(ASSET_KINDS), 새 `server/app/root_learning/choices.py`, `server/app/routes/root_learning.py`(앞면·답면·`prior_exposure`), `server/tests/` | asset 읽기·대조·붙이기, 「선지 봄」 기록 |
| 5 | 화면 | `web/src/bank/RootSolve.tsx`, `BankQuestion.tsx`, 타입, `main-quiz.css`, `web/src/notices/GuidePage.tsx`, `web/tests/` | 버튼·`V` 키·고르기·결과 표시 |
| 6 | 문서 | `docs/map.md`, `quizbank/CLAUDE.md`, `docs/artifact-contract.md` | 게시 뒤 단계가 하나 늘어난 것을 반영. README 「현재 흐름」은 Main-Quiz 게시 뒤 단계를 그리지 않아 고치지 않았다 |
| 7 | 시범 | 리케치아(261110_03, 126문항) | `python -m runner.root_choices --run-id 261110_03 --no-upload` 약 3회 호출. 통과율·건너뜀 비율을 세고 오답 품질을 사람이 읽는다 |
| 8 | 배포 | master 병합 → API → 웹 자동 배포 | 러너 재설치 불필요(게시 경로 불변). 명령은 저장소 사본에서 직접 돌린다 |
| 9 | 보강(D3) | 이미 공개된 이번 블록 판 | 강의마다 선지 asset만 올린다. 따로 승인받는다 |

건드리지 않는 파일: `content/prompts/learning-links/v4/`, `quizbank/connection_generate_v4.py`,
`studyez_contracts/roots/generation_v4.py`, `server/app/root_learning/planning.py`(goal-dedupe 영역), `web/src/bank/BankSolve.tsx`.

## 검사 명령과 성공 조건
- `python -m pytest tests/contracts tests/quizbank tests/runner` 통과. 새 검사: 형식별 선지 규칙, 정답 누락·중복·질문에 답이 들어간 경우 거절,
  묶음 실패 시 부분 asset, 게시 결과 불변.
- `server/`에서 `.venv/Scripts/python.exe -m tests root`(`PYTHONPATH=..`로 worktree의 계약을 읽게 한다). 새 검사: asset 없음·판 불일치·지문 불일치에서
  선지 없음, 앞면에 정답 ID 없음, `choicesShown` → `helped`.
- `web/`에서 `npm run typecheck`, `npm run build`, 기존 Main-Quiz 화면 검사와 새 검사(숨김 → 펴기 → 고르기 → 결과 표시, 스페이스바는 답 보기).
- 로컬 미리보기로 단답·나열·선지 없는 문항을 직접 눌러 확인한다. 격리된 로컬 DB와 저장소만 쓴다.
- 시범(7번)의 성공 조건: 검사 통과 문항의 오답을 20문항 이상 읽어 「정답으로도 성립하는 오답」이 없어야 한다. 있으면 지시문·검사를 고치고 같은 사본으로 다시 잰다.

## 위험·복원·승인할 범위

위험:
- **오답이 사실은 정답인 경우.** 코드 검사로는 못 잡는다. 오답 이유 한 줄을 받게 하고, 좋은 오답이 없으면 건너뛰게 하며, 시범에서 사람이 읽는다.
  게시 뒤에는 기존 「문제 수정·제보」로 들어온다. 제보된 문항의 선지를 끄는 길(관리자)은 1차 범위 밖이다 — asset을 다시 올려야 한다.
- **선지가 답을 너무 쉽게 드러내는 경우.** 오답을 같은 강의의 실제 개념에서 고르게 해 줄인다.
- **스스로 떠올리는 연습이 줄어드는 것.** D1 결정(스페이스바는 답 보기, 선지는 `V`)이 이 위험을 줄인다.
- **자동으로 붙지 않는다.** 새로 출제된 강의에는 명령을 돌려야 선지가 생긴다. 강의를 다시 출제해 판이 바뀌면 그 판에 다시 돌려야 한다.
- **동시 실행 자리.** 명령의 호출(강의당 약 3회)은 기계 전체 Codex 한도(8)를 출제와 나눠 쓴다. 자리가 없으면 기다린다.

복원:
- 화면·서버는 커밋을 되돌리면 된다. DB 스키마 변경이 없다.
- 러너 단계를 끄거나 asset을 지우면 기능이 꺼진다. 판·문항·학습 기록은 그대로다.

대시보드 겹침(2026-11-12 확인):
- goal-dedupe(v4 지시문·`connection_generate_v4.py`·`generation_v4.py`·`planning.py`): 이 계획은 그 파일을 건드리지 않는다.
- 야간 일괄 출제: 러너 재설치·중지 금지 중이다. 이 변경은 러너 재설치가 필요 없다.
- 구현을 시작할 때 대시보드 행을 「문서만」에서 실제 파일 범위로 고치고 겹침을 다시 확인한다.

승인할 범위:
- 사용자의 구현 요청으로 진행하는 것: 1~6번 코드·문서, 로컬 검사, PR(Draft), master 병합과 자동 배포.
- 따로 묻는 것:
  - 7번 시범 — 문항 글을 Codex CLI로 보내는 약 3회 호출.
  - 9번 보강 — 이번 블록 공개 판 전체에 대한 모델 호출(강의당 약 3회, 20강의면 약 60회 어림).
  - 학생에게 처음 보이는 시점 — 관리자 계정에서 먼저 확인한 뒤 전체 공개할지.

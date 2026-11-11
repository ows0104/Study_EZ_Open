# GitHub Actions 분 줄이기 2 — 필요한 검사만, PR 습관

## 의도

사용자 2026-11-11: 「우리가 PR을 너무 남발하나? 벌써 3000의 90%나 썼다고 메일이 왔어」 → 원인 설명 뒤
「어 해줘. 그리고 작업습관도 살짝 바꾸자.」

근거(2026-11-11 측정, 11월 실행 227회의 작업 시작·끝 시각으로 어림. Billing API는 이 세션 권한으로 못 읽음):
- 11-01 이후 차감 어림 약 3,240분. 하루 400–900분. 11-07–11 5일 동안 실행 약 200회.
- 작업별: Tests and build 2,305 · Windows runner checks 768(2배 계산) · Deploy 165.
- 계기별: pull_request 1,807 · master push 1,431. PR 하나가 PR 검사 + 병합 뒤 master 검사로 두 번 돈다.
- [이전 정리](../2026-11-08-ci-linux-runner/README.md)는 Linux 이전과 같은 PR 이전 실행 취소까지였다.

## 바꾼 것

1. **`Decide checks` 작업(`scripts/ci_scope.py`)**: 다른 작업 전에 범위를 정한다. 판단 실패·수동 실행·
   새 브랜치·파일 300개(PR 3000개) 이상이면 전부 돈다.
   - 문서·기록만 바뀌면 `tests=false`: `docs/`·`runs/`·`etc/`·루트 `*.md`·각 폴더 `CLAUDE.md`/`README.md`/`AGENTS.md`.
     검사가 읽는 문서(`docs/samples/`·`docs/prompt-architecture.md`·`docs/development/templates/`)는 코드다.
     `web/src/bank/bankPrompt.md` 같은 폴더 안 프롬프트 `.md`도 코드다.
   - 사이트 전용 경로(`web/`·`server/app/`·`server/tests/`·`spotter/`·`spotter-dist/`)만 바뀌면 `windows=false`.
   - master push가 병합 커밋이고 그 트리가 PR 머리 트리와 같으며 PR 머리에 `Tests and build`(·`Windows
     runner checks`) 성공이 있으면 그 검사를 다시 하지 않는다. 같은 트리를 이미 검사했다는 뜻이다.
     PR 뒤 master가 전진해 트리가 다르면 예전처럼 다시 검사한다(이전 기록이 재검사를 남긴 이유).
2. **`Tests and build`**: 검사 단계만 `tests` 조건. `map_numbers --check`와 배포 후보 준비·업로드는 늘 돈다.
3. **`Windows runner checks`**: `windows` 조건.
4. **배포**: `checks` 성공 + Windows 성공 또는 건너뜀일 때. master에서는 문서만 바뀌어도 배포가 돈다
   (Pages가 같은 SHA의 health를 기다린다). 후보는 여전히 같은 실행에서 만들고 봉인한다.
5. **PR 습관**(`docs/development/collaboration.md` 「PR 습관」, `CLAUDE.md`·`AGENTS.md` 한 줄):
   Draft로 열고 로컬 검사 뒤 Ready 한 번, Ready PR에는 커밋을 모아 push, 잇단 작은 수정·문서 PR은 묶는다.

## 바꾸지 않은 것

서버·웹·출제 코드, DB, 운영 설정, 배포 후보 봉인·SHA 확인. 브랜치 보호는 원래 없다(필수 검사 이름 영향 없음).

## 검사

- `tests/development/test_ci_scope.py` 7개(분류·실패 시 전부·같은 트리 건너뜀/다른 트리 재검사), `test_ci_deploy.py` 통과.
- 실제 저장소 API로 최근 master 병합 6개 모의 판정: #94·#93·#90은 같은 트리라 재검사 생략, #91은 웹만이라
  Windows 생략, #92·#89는 master 전진으로 전부. PR #93은 전부.
- 워크플로 YAML 파싱 확인. 실제 Actions 동작은 이 PR 실행과 병합 뒤 master 실행이 첫 확인이다.

## 되돌리기

이 PR revert. 데이터·운영 상태 변경 없음.

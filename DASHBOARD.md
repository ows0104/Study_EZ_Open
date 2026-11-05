# StudyEZ 작업 대시보드

> 이 파일은 `dashboard` 브랜치에만 있다. master에 merge하지 않는다.
> 작업 전에 반드시 `git pull`로 최신 상태를 받고, 확인 → 내 작업 작성 → push 후 작업을 시작한다.
> 규칙 전문: master의 `docs/development/collaboration.md` "작업 시작 대원칙".

우선순위: **P0** 긴급(운영 장애·데이터 위험) · **P1** 이번 주 · **P2** 다음 · **P3** 언젠가

---

## 1. 지금 하고 있는 작업

같은 영역·파일이 다른 행과 겹치면 시작하기 전에 상대와 조정한다.

| 우선순위 | 작업 | 작업자 / 세션 | 브랜치 | 건드리는 영역·파일 | 시작일 | 상태·메모 |
|---|---|---|---|---|---|---|

| P1 | Map·독립 출제포인트 추출 프롬프트 정리 | ows0104 / Codex Map 세션 | codex/map-point-prompts | content/prompts/learning-links/map-extract.md, point-extract.md, *-output.schema.json, *-output.example.json, README.md, docs/changes/2026-11-06-map-point-prompts, .worktrees/map-point-prompts/runs/_map-point-pilot | 2026-11-06 | 사용자 승인 범위의 두 원본 전용 지시문·JSON 스키마·예시·로컬 형식 검증. 현재 사용자 예시 추출 승인: 심내막염·중추신경계감염 Map/포인트 각 1회 로컬 실추출. 운영 요청 재개/문항/게시/배포 없음 |

## 2. 앞으로 하기로 약속된 일

| 우선순위 | 작업 | 예정 작업자 | 예상 영역·파일 | 선행 조건·메모 |
|---|---|---|---|---|
| | | | | |

## 3. 제안된 아이디어 (논의 필요)

합의되면 2번으로 옮긴다. 합의 전에는 구현을 시작하지 않는다.

| 아이디어 | 제안자 | 제안일 | 논의 내용·결정 |
|---|---|---|---|
| | | | |

---

## 완료 기록 (최근 것만)

merge가 끝나면 1번에서 지우고 여기에 한 줄 남긴다. 오래된 줄은 지워도 된다.

| 완료일 | 작업 | 작업자 | PR |
|---|---|---|---|
| 2026-11-05 | 순수 JSON 수신·검증·결정적 변환과 프롬프트 1.82 API·웹 a3f67d13 배포 완료. 전체 검사/health SHA/401/운영 프롬프트 확인. 로컬 러너 코드 갱신·기존 매칭 보존. 브리지 1.3.23 사용자 업데이트 필요 — [배포 기록](https://github.com/ows0104/Study_EZ_Open/blob/codex/bank-json-delivery/docs/changes/2026-11-05-bank-json-delivery/deployment.md) | ows0104 / Codex JSON 전환 세션 | [#6](https://github.com/ows0104/Study_EZ_Open/pull/6) |
| 2026-11-05 | 교수별 예습·CBL 매핑과 적용 기록 master 반영 및 API·웹 `5c56d462` 배포 완료. 양쪽 전체 검사/health/401/Pages success/CBL 세 첨부 유지 확인 — [배포 기록](https://github.com/ows0104/Study_EZ_Open/blob/04e60a2df003dcb7688e3678457754a13d506577/docs/changes/2026-11-05-cbl-prev-notes/repository-deployment.md) | ows0104 / Codex 교수별 예습 세션 | [#5](https://github.com/ows0104/Study_EZ_Open/pull/5) |
| 2026-11-05 | 미정 CBL 3개에 주제와 관련 CBL 기출을 확인한 2025년 필기 연결 완료. 세 PDF 실제 해시/학습 기록 보존/운영 화면 확인 및 러너 복원. 코드 재배포 없음 — [운영 기록](https://github.com/ows0104/Study_EZ_Open/blob/2d420b1f78f670f0dfa205bd0b86917bc7b0f675/docs/changes/2026-11-05-cbl-prev-notes/deployment.md) | ows0104 / Codex 교수별 예습 세션 | 승인된 자료 연결, 기록 codex/cbl-prev-notes |
| 2026-11-05 | 교수 변경·신규 교수 표시 및 최근 5년 동일 교수 최신 필기 우선, 없으면 작년 대체 운영 반영 (`c86e15fb`). 84개 강의·기록 보존, PDF 72개 실제 검증, 러너 복원 완료 — [배포 기록](https://github.com/ows0104/Study_EZ_Open/blob/a757ce86c548519b1c1c714298f530f1e9eb86c3/docs/changes/2026-11-05-professor-aware-preview/deployment.md) | ows0104 / Codex 교수별 예습 세션 | [#3](https://github.com/ows0104/Study_EZ_Open/pull/3) |
| 2026-11-05 | master 검사 실패 수정 및 API·웹 배포 완료 (`d5e30590`) — [검사·배포 기록](https://github.com/ows0104/Study_EZ_Open/blob/9f57d3d607335204193441c1358a95fe85b363c7/docs/changes/2026-11-05-ci-regression-fix/deployment.md) | ows0104 / Codex 세션 | [#4](https://github.com/ows0104/Study_EZ_Open/pull/4) |
| 2026-11-05 | 협업 대시보드와 작업 시작 대원칙 도입 | HungryPotato01 / Claude 세션 | [#2](https://github.com/ows0104/Study_EZ_Open/pull/2) |

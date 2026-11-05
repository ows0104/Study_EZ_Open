# 교수 변경 표시와 최근 5년 동일 교수 예습 필기 선택 — 구현 계획

## 변경 범위·대상 파일·순서
상태: 2026-11-05 사용자 구현 승인 기록 및 build gate 통과. 승인 범위 안에서 로컬 구현/격리 검사 중. 후속 보완은 동일 교수 미발견 시 작년 필기를 기본 사용한다는 사용자 발언을 반영했다. 계약 테스트 파일명은 pytest 모듈 이름 충돌을 피하여 `test_preview_source_contract.py`로 정리했다.

1. `studyez_contracts/preview_sources.py`(신규), `tests/contracts/test_preview_source_contract.py`: 연도/교수/출처/일치/검색 상태/보존 지문 계약. 표준 라이브러리만 사용.
2. `runner/preview_sources.py`(신규), `runner/matching.py`, `ahead.py`, `readiness.py`, `publish.py`, `prequeue.py`, `runner/cli/materials.py`, 필요한 `scripts/runner_desktop_jobs.py` 소비부: 5년 스캔·공통 선택·직전 연도 비교 분리·자료 없는 시간표 강의 메타데이터. 기존 점수 기준을 무작정 낮추지 않고 수동/합본 대응을 보존.
3. `server/app/models/lectures.py`, `server/app/cli.py`, `server/app/routes/admin.py`, `timetable.py`, `lectures.py`: nullable JSON, 이전 입력 호환, 서버 검증 및 학생 요약 제공. 스키마 변경은 격리 로컬 DB에서만 검증.
4. `web/src/types/lectures.ts`, `web/src/calendar/entries.ts`, `EventChip.tsx`, `EventPanel.tsx`, 관련 calendar 스타일, `web/src/lecture/LecturePage.tsx`, `previewPrompt.ts`, `web/src/notices/GuidePage.tsx`: 태그·근거·실제 연도 자료명·기존 예습 흐름. 새로운 학습 완료 행동은 만들지 않음.
5. 아래 회귀/브라우저 검사 및 코드 리뷰. `docs/artifact-contract.md`, `docs/commands.md`, 관련 컴포넌트 안내, 이 작업 `release.md`에 실제 결과와 운영 후보/보존/복원 기록. 기존 결과의 강제 재생성은 하지 않음.

## 검사 명령과 성공 조건
프로젝트 `.venv/Scripts/python.exe`를 사용하고 서버는 파일별 독립 검사 실행을 유지한다. 여러 명령 묶음은 모든 결과를 보존하는 실행기로 연결한다.

| 체크 | 실제 구현 후 실행할 검사 |
|---|---|
| professor-selection | `-m pytest tests/runner/test_preview_sources.py -q`: 2025 다른 교수+2023 동일 교수, 2024 우선, 2021 경계/2020 제외, 최신 판, 제목/순번/모호함, 신규/일부 일치/미상, 실패/미보유, 낡은 지문, 수동/합본 보존 |
| contracts | `-m pytest tests/contracts -q`: 생산자/소비자 계약, 학생 비노출 필드, 구형 호환 |
| runner | `-m pytest tests/runner -q`: publish/readiness/prequeue 일치, 시간표 ID·범위·중지·보류·출처 변경 보존 |
| server | `server/`에서 격리 DB/저장소 명시 후 `.venv/Scripts/python.exe -m tests preview_sources`, `matching`, `route_contract`, `immunity_timetable` 각각 실행. 새 필드 생략·권한·경로 비노출·스키마 호환 |
| web | `npm.cmd --prefix web run typecheck`, `npm.cmd --prefix web run build`, `node --test web/tests/calendar-loading.test.cjs`, 신규 태그/연도 회귀 |
| browser | 계정/운영 API 없는 격리 자료로 동일/변경/신규/확인 필요/일부 일치·모바일/키보드·상세/툴팁/첨부 흐름 확인 |

`development.py verify <id> --check <name> -- .venv/Scripts/python.exe scripts/verify_professor_preview.py <name>`으로 실제 결과를 기록한다. 명령 묶음은 위 검사에 smoke/shared_preview_prompt/study_retention 및 기존 캘린더 브라우저 회귀를 포함한다. area=contracts는 runner/server/web을 함께 지문화한다. 검사 파일명 정리·보존 검증의 구체화는 승인 기능 범위를 바꾸지 않는다.

## 위험·복원·승인할 범위
요청할 승인 범위는 위 기능의 로컬 구현·문서·격리 검사와 운영 적용 후보 준비다. 운영 DB/첨부 교체·기존 예습 재생성은 이 단계에 포함하지 않는다.

위험은 같은 교수의 다른 강의 연결, 미보유 연도를 무이력으로 오인, 합본 범위 손실, 원본 변경 후 옛 대화/덱의 부적절한 재사용이다. 전체 제목/순번/근거·커버리지·해시 및 보존 회귀로 검증한다.

후속 중요 운영 승인에는 실제 DB 호환 변경·강의별 파일 교체 목록·이전 자료 보존·배포 순서·사후 관측·복원을 제시한다. 이전 코드가 새 nullable JSON을 무시하고 동작하도록 한다. 복원 시 이전 자료 연결은 보존본으로 돌릴 수 있게 하고 학습 기록/예습 대화는 삭제하지 않는다.

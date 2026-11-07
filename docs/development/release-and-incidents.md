# 배포 후보·사후 확인·사건 종료

2026-11-05 승인된 일반 코드 master 자동 경로는 [협업·자동 배포](collaboration.md)를 따른다.
아래는 수동 고정 후보 경로다. 콘텐츠/DB/학습 기록/권한 변경 등 [사람에게 묻는 것](README.md#사람에게-묻는-것)은 개별 승인을 받는다.

이 절차의 구현 완료와 실제 운영 배포는 다르다. 현재 workflow-hardening 작업은 운영 배포 승인이 없다.
기존 명령으로 직접 master를 push하거나 클라우드에 배포해 이 절차를 우회하지 않는다.
도구는 로컬 증거를 확인하며 원격 계정/브랜치의 권한 통제를 대신하지 않는다.

## 1. 검사와 리뷰

작업을 new로 만들고 intent/spec/plan과 required_checks를 정한 뒤 사용자의 작업 요청 원문을 구현 근거로 기록한다.
검사와 리뷰는 evidence_version 2의 영역 입력·코드 지문·계획 지문에 묶인다.
설계를 바꾸면 구현 근거 재기록뿐 아니라 새 설계에 맞는 검사와 리뷰가 필요하다.
구형 state의 기록은 보존하고 자동 승격하지 않는다. 현재 작업으로 계속할 때 실제 승인 범위와 재검증을 기록한다.

scripts/workflow_scope.py가 실제 읽는 입력 목록의 정본이다. scripts/개발 검사/requirements/pyproject/uv.lock은
공통이고, 사이트·출제·연결·Spotter의 소스/검사는 나뉜다. 공용 계약과 operations는 모든 영역을 포함한다.
Spotter 코드/웹/데이터와 시간표도 포함한다. 생성 runs·원본 PDF·대용량 사진·환경 설치는 기본 소스 범위가 아니다.
그 자료를 바꾸는 작업은 spec에 정확한 입력과 별도 자료 해시/검사를 추가해야 한다. 관련 없는 원문을 전부 읽지 않는다.

실제 검사 예:

```powershell
python scripts/development.py verify <id> --check server -- <서버 검사 명령과 인수>
python scripts/development.py verify <id> --check contracts -- python -m pytest tests/contracts -q
python scripts/development.py verify <id> --check web -- npm.cmd --prefix web run build
python scripts/development.py review <id> --summary "실제 검토 범위와 결과"
```

서버 후보에는 server/contracts, 웹 후보에는 web/contracts라는 검사 이름이 필요하다.
이름은 검사 품질을 보장하지 않는다. 리뷰에서 실제 명령·출력·테스트 수·영향 범위까지 확인한다.
보관 검사만 통과한 작업을 사이트 배포 근거로 재사용할 수 없다.

## 2. 파일이 고정된 후보 준비

서버는 `server/prepare-build.ps1 -Destination <새폴더>`로 로컬 패키지만 만든다.
웹은 위 web 검사에서 생성한 web/dist를 사용한다. 웹 산출물 및 빌드 환경 지문을 검사 기록에 보관한다.
후보 준비는 검사 코드와 서버 패키지를 대조하거나 웹 산출물의 검사 기록을 대조한 뒤
runs/_development/<id>/candidates/<해시>/로 복사한다. 이후 원래 작업 폴더에서 다시 빌드해 배포하지 않는다.

작업 폴더에 release-config.json을 작성한다. 실제 대상과 이전 버전 복원 방법, 건강 상태 URL,
배포된 버전에서 수행할 **읽기 전용 핵심 학습 동작 검사**를 지정한다. smoke_command는 실제 검사 프로그램의
인수 배열이며 `{revision}`에 배포 버전, `{artifact}`에 고정 산출물 경로가 들어간다.
빈 명령이나 단순 종료 0을 운영 검사로 승인하지 않는다. 인증정보는 명령 인수/로그에 넣지 않는다.

서버 설정 필드:

```json
{
  "target": "server",
  "destination": "meddeck-503318/asia-northeast3/studyez-api",
  "health_url": "https://studyez-api-97999573571.asia-northeast3.run.app/api/health",
  "smoke_command": ["python", "검토한_실제_사후검사.py", "--revision", "{revision}"],
  "rollback": "실제 이전 revision, 트래픽 복원 방법 및 데이터 영향"
}
```

예시의 검사 파일은 자리표시자다. 배포 전에 실제 존재하는 검사와 필요한 계정/읽기 범위를 확정한다.
웹은 target=web, destination=실제 프로젝트, health_url=사이트 주소로 지정하고
deploy_command(고정 `{artifact}`를 사용하는 업로드 인수 배열), revision_command(실제 배포 ID만 출력하는
읽기 전용 명령 배열)를 추가한다. 환경별 CLI 선택은 그 후보 설정과 사람 승인에 포함한다.
Git push로 별도의 소스를 다시 빌드하는 경로는 고정 산출물 배포를 대신하지 않는다.

```powershell
python scripts/release_evidence.py prepare <id> --artifact <패키지 또는 web/dist> --config <release-config.json>
python scripts/development.py approve <id> --phase deploy --evidence "사용자의 배포 요청·승인 발언 원문" --scope "실제 대상·후보·변경 범위"
python scripts/development.py check <id> --phase deploy
```

후보·소스·설계·배포 문서·환경 파일이 바뀌면 다시 준비/검사/승인을 판단한다.
환경 파일은 해시만 비교하고 값은 후보에 복사하지 않는다. 쉘 밖에서 바뀌는 환경 변수/원격 비밀 버전도
릴리스 리뷰에서 명시해야 한다. 모든 외부 설정 변경을 자동 탐지하는 장치는 아니다.

## 3. 실제 배포와 결과

deploy 근거가 기록된 뒤에만 서버 `server/deploy.ps1 -ChangeId <id>` 또는
웹 `python scripts/release_evidence.py publish-web <id>`를 실행한다.
서버는 기존 설정 경로를 유지하면서 승인된 서버 후보만 업로드한다. 실제 revision과 100% 트래픽을 확인한다.
서버 revision은 release-<attempt>로 고정하며 --no-traffic으로 생성한다. 해당 revision의 Ready·ContainerReady와
서비스의 latestCreated를 확인한 뒤 명시적으로 100% 전환한다. latestCreated·latestReady·실제 트래픽이
모두 기대 revision과 일치해야 성공 영수증을 기록한다. 검사·전환 실패는 실패 기록으로 남기며 자동 재배포하지 않는다.
웹은 승인된 명령에 고정 artifact를 넘기고 실제 배포 ID를 조회한다.
두 경로 모두 시작/성공/실패 영수증과 health+smoke 결과를 state.json에 보존한다.
업로드 후 버전 확인이 실패하면 성공으로 처리하지 않는다. 자동 롤백이나 자동 재배포는 하지 않는다.

사후 확인 재실행은 `python scripts/release_evidence.py postcheck <id> --attempt <실제 attempt ID>`다.
가장 최근 실패가 예전 성공을 가리지 않는다. 승인된 smoke가 운영 데이터를 바꾸지 않는지 반드시 검토한다.
PC/명령 중단으로 running이 남으면 실제 클라우드 상태를 먼저 확인하고 `record`로 실제 결과를 남긴다.
기록은 이미 끝난 배포를 증언하는 것이며 새 배포를 실행하지 않는다.

## 4. Maintain에서 조사/종료로

관측 이상은 incident와 intent를 만들고 조사 시작 사건을 기록한다. 복구하면 같은 사건에 recovered를
영속 기록한다. intent/spec/수동 조사 내용을 덮어쓰지 않는다. recovered만으로 해결을 선언하지 않는다.

```powershell
python scripts/workflow_lifecycle.py link <incident> --related-id <fix-change>
python scripts/workflow_lifecycle.py link <change> --feedback-id site:12 --fingerprint <현재 ledger fingerprint>
python scripts/workflow_lifecycle.py transition <id> --status awaiting_approval --evidence "제안한 계획과 승인 필요 범위"
python scripts/workflow_lifecycle.py transition <id> --status completed_local --evidence "로컬 구현/검증 완료. 배포 없음"
python scripts/workflow_lifecycle.py transition <incident> --status resolved --fix-change <fix-change> --evidence "실제 배포 버전·학습 동작 검사·원인 해결 근거"
```

deployed fix로 종료하려면 연결한 수정 작업의 최신 배포와 최신 사후 검사가 모두 성공해야 한다.
일시적 관측 실패만 복구된 사건은 --fix-change 없이 근거를 적어 종료할 수 있고 observation_only로 표시한다.
코드 수정/배포 완료와 혼동하지 않는다. feedback link는 원문·서버 상태·승인을 변경하지 않는다.
ledger에도 change ID를 note로 연결하고 실제 반영 검증 후 기존 feedback record/pull 절차를 따른다.

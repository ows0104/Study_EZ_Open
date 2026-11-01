# 사용 현황 행동 구분 — Implementation Plan

## 변경 범위·순서
1. AssetGrab 모델/cli.ensure_columns에 request_stats JSON(default {}) 호환 칼럼 추가. 파일 목적 파싱/기존 미분류 잔여/시각을 공용 helper로 관리하고 record_grabs에서 기존 기록을 보존한다. 동시 요청은 DB upsert+row lock으로 누락을 막는다.
2. lectures 파일 API에 검증된 purpose 추가. PreviewAction/ReviewAction/BankPanel/QuizCreateButton 자동 첨부, EventPanel/LecturePage/BankCardReview 열기·받기와 bundles/catalog 내보내기에 목적 전달.
3. usage API에 기간 내 개인 예습 저장 강의 수, 웹 풀이 갈래별 수, 목적별 파일 요청 강의 수를 추가한다. 전체 기간 상세에는 저장/클릭/평가 시각과 파일 종류·목적별 요청 수를 추가한다. 기존 필드는 보존한다.
4. account 타입/UsageTab/관련 스타일에서 네 행동을 분리해 명시적 한국어와 단위, 실제 시각, 기록 없음/목적 미상을 표시한다. GuidePage에서 필요한 설명을 확인한다.
5. 관련 격리 테스트, 웹 검사, UI 표시 확인 후 release.md에 리뷰/실제 결과/스키마 선행/롤백을 기록한다.

## 검사 명령과 성공 조건
- usage-regression: server/.venv/Scripts/python.exe -m tests usage (server cwd). 기존 기간·학습 보존/저장만 있는 활동/상세 시각/과거 목적 미상 검증.
- file-purpose: 같은 런타임 -m tests file_request (server cwd). 기존 DB 칼럼 추가 두 번/과거 count 보존/예습·복습 자동 첨부와 직접 받기·열기 분리/구버전 unknown/잘못된 목적 거부/파일 오류 시 기록 없음/다른 계정 격리 검증.
- server: 같은 런타임 -m tests route_contract, -m tests bundles, -m tests bank_anki, -m tests smoke.
- web-typecheck: web cwd npm run typecheck.
- web: web cwd npm run build.
- ui-review: 로컬 UI fixture를 사용한 화면 확인. 실제 계정·인증정보/대화 URL은 fixture에 넣지 않는다.
검사는 scripts/development.py verify로 기록하며 운영 .env를 테스트에 쓰지 않는다.

## 위험·복원·승인
2026-11-01 사용자의 후속 명시적 수정 요청을 현재 로컬 구현 범위 승인으로 적용한다. 같은 범위 승인을 다시 요청하지 않는다. 실제 운영 스키마 변경과 배포는 별도 고정 후보/중요 승인 대상이다. 호환 칼럼은 API 배포 전에 추가하고 API 다음 웹 순서로 배포한다. 과거 요청의 목적은 추정하지 않는다. 문제 발생 시 이전 API/웹으로 복원하고 추가 칼럼/수집 기록은 삭제하지 않는다. 다른 production-update 작업은 변경/커밋/배포에 섞지 않는다.

- contracts: server/.venv/Scripts/python.exe -m pytest tests/contracts -q.

## 최종 검사 사본
다른 채팅의 족보/교수 프롬프트 변경이 동시에 발생해 검증 중 source_hash가 달라졌다. 해당 실행은 테스트 자체 통과와 별개로 증거 코드 2로 보존한다. base revision 35663e610ed003182e05fddfd828e871336fc389와 이번 작업의 명시된 20개 파일만 runs/_development/2026-11-01-usage-action-clarity/isolated에 복사해 최종 검사한다. isolation.json에 포함/제외 목록을 보관한다. 최종 검증/후보는 이 사본 기준이며 다른 작업의 변경을 포함하지 않는다. 이 분리는 승인된 기능 범위를 바꾸지 않는다.

## 승인된 후속 보강과 운영 적용
위 사용자 최신 발언에 따라, 기존 후보를 그대로 배포하기 전에 행동 정의를 공통화한다. models/previews.py의 허용 행동, common.py 기록 helper, lectures.py와 PreviewAction의 create 기록을 추가한다. usage_actions.py 공통 카탈로그/수집 helper와 usage.py 행동 응답, account.ts와 UsageTab의 동적 표를 연결한다. tests/test_usage_actions.py에서 새 카탈로그 항목 전파·기존 share/mine 분리·생성 시도/저장 구분·등록 누락·계정별 기록을 검사한다. docs/development/usage-actions.md와 컴포넌트 안내에 신규 행동 작업 절차를 연결한다. 기존 로컬 사본에서 작업하고 다른 채팅 변경은 제외한다. 최종 재검증/리뷰/고정 후보 준비 후 현재 실제 사용자 승인 발언을 후보별 배포 근거로 기록해 DB 단일 칼럼→API→웹 순서로 운영 반영한다.
- usage-actions: server .venv/Scripts/python.exe -m tests usage_actions.
중요 운영 변경 승인 범위는 request_stats 단일 칼럼과 위 이용현황 기능 API/웹이다. 권한/강의 내용/기존 학습 이력 변경은 포함하지 않는다.

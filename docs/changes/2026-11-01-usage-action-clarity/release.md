# 이용현황 행동 분류 — 운영 반영

## 승인 및 구현 범위
2026-11-01 최신 사용자는 기록용 DB 항목 추가와 API·웹 운영 반영을 명시 승인하고 공용 링크 열기/개인 링크 만들기/예습·복습 퀴즈/미상 및 향후 행동 추가의 반영을 요구했다. 해당 승인 범위를 이번 최종 후보에 적용하며 반복 확인하지 않는다.

서버 공통 행동 카탈로그가 코드·한국어 이름·그룹·단위·수집 경로를 관리한다. API 요약/상세의 activities와 카탈로그를 웹이 순회하므로 새 행동 등록 시 별도 웹 목록을 고치지 않는다. 링크·파일 목적의 등록 누락 검사와 개발 안내를 추가했다. 개인 링크 만들기 시도(create)는 기존 PreviewOpen에 새 종류로 저장하며 share/mine 열기와 UserPreview 주소 저장과 구분한다. 기존 강의 상세의 공용 링크 클릭도 공통 기록 helper로 연결했다. 만들기 시도와 링크 클릭의 동시 요청을 DB upsert/row lock으로 보존한다.

공용 링크 열기/개인 링크 열기/개인 링크 만들기 시도/개인 예습 링크 저장/예습 퀴즈 풀이/기존 복습·복습 카드 풀이/직접 다운로드·브라우저 열기·세 자동 첨부 요청/미상을 명시한다. 외부 AI 생성·열람·첨부·파일 전송 완료는 주장하지 않는다. 과거 기록 목적은 추정하지 않는다. 학습 내용·평가·대화 URL은 보존하며 URL/본문을 관리자 이용현황에 추가 노출하지 않는다.

## 고정 검증본과 리뷰
base revision 35663e610ed003182e05fddfd828e871336fc389 + 이번 이용현황 작업만 포함. 다른 채팅의 족보/교수 프롬프트 변경은 제외한다. 검증 사본은 runs/_development/2026-11-01-usage-action-clarity/isolated이며 공유 작업 폴더에서 직접 배포하지 않는다.
- source fingerprint: 5928e1f2201aa0c679410b17ce921780b85d09410a4aaaac8ef7b4cec554f33e
- usage-regression 54 PASS, usage-actions 16 PASS, file-purpose 22 PASS. 서버 route_contract/bundles/bank_anki/smoke 통과. 공용 계약 6 passed. 웹 타입 검사와 production build 통과.
- 실제 브라우저 가상 계정 검사 5개 통과: 정확한 행동 이름, 별도 만들기 시도, 새 정의의 UI 자동 표시(웹 수정 없이 테스트 행동 추가), 과거 미상, 저장만 있는 18강의. 운영 계정에 가짜 활동을 생성하지 않는다.
- 웹 artifact hash: a5574632b4441abf9f1ffaee0b6a2fa52ab78c497dd4d4aaf48013770f2ed7e8. 카탈로그·수집·자동 렌더·시각/기간/단위·동시성·기존 응답 호환·계정 분리·개인정보를 직접 리뷰했다.
- 신규 행동 안내: docs/development/usage-actions.md, server/CLAUDE.md, web/CLAUDE.md.

## 운영 순서
1. 승인된 단일 스키마 변경: public.asset_grab.request_stats JSON NOT NULL DEFAULT '{}' 추가(IF NOT EXISTS). 기존 count/시각은 갱신하지 않으며 접속 기록표/권한 변경은 없다. create는 기존 VARCHAR(8) 종류에 들어가 추가 DB 변경이 없다.
2. server-candidate.json의 고정 후보를 meddeck-503318/asia-northeast3/studyez-api에 배포. 새 revision 생성/Ready/100% 트래픽/health/auth smoke를 실제 확인한다.
3. web-candidate.json의 고정 산출물을 Cloudflare Pages study-ez-open (studyez.kr 및 study-ez-open.pages.dev)에 배포. 정확한 배포 ID/health/auth smoke를 확인한다. 활성 후보는 서버→웹 순으로 전환하고 동일 사용자 운영 승인 발언을 각각 기록한다.
4. 실제 관리자 화면과 읽기 전용 이용현황 응답에서 카탈로그/행동/18강의 저장 및 미상/기존 학습 수 보존을 확인한다. 새 시도 기록은 앞으로만 수집한다.

## 복원
직전 API Ready는 studyez-api-release-1793518641518323800, 웹 production은 791d763d-8f4e-4d35-84f6-76fbbd7cf822다. 배포 직전의 실제 트래픽/최신 버전이 이와 일치하는지 다시 확인한다. 회귀 시 이전 API 트래픽과 Pages 버전으로 복원하고 추가 칼럼/수집 기록은 삭제하지 않는다.

사후 검증과 운영 영수증은 state.json/deployments와 post-deploy.md에 추가한다. 이 release.md는 고정 후보 승인 지문을 보존하기 위해 배포 중 덮어쓰지 않는다.

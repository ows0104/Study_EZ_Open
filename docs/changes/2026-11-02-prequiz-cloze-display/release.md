# 예습 cloze 표시를 복습 Quiz Bank 방식에 맞추기 — 배포 준비

## 코드 리뷰·검증 결과
구현·로컬 검증·서버 및 웹 운영 배포·사후 확인 완료(2026-11-02).

사용자 확정 범위: 답을 펼친 뒤 문장 속 빈칸 정답 강조 및 어려웠던 문제 적용. 풀이 전 빈칸 번호 추가는 제외했다.

- web-cloze: 7개 통과. 기존 앞면 HTML 동일, 여러 빈칸의 답 위치, 줄바꿈·강조·HTML 이스케이프, 즉시/재방문 어려웠던 문제 표시를 확인했다.
- web-typecheck: 통과.
- web-build: 통과.
- server-cloze: test_prequiz_cloze 1개 실제 실행·통과. 초기 목록/슬라이드 정답 비노출, reveal/undo/missed/extraMissed, 원문 없음/불일치/문법 오류 fallback, basic/OX/mainquiz 호환을 검증했다.
- server-quiz-regression: prequiz_once, quiz_kinds, route_contract를 각각 별도 프로세스로 실행·통과. API 경로 143개 유지.
- git diff --check: 통과.
- Chrome 메모리 API 화면: 공개 전 [____]/[대조 기준] 유지 → 답 공개 시 두 정답 위치와 강조 → 다음 문항의 답 숨김 → 되돌리기 시 공개 상태 복원 → completed 재방문에서 저장된 어려웠던 문제 강조를 실제 확인했다. 운영 서비스 검사는 아니다.

코드 리뷰: reveal와 기존 본인별 답 응답에만 clozeParts가 추가되는지 확인했다. 원문을 가린 결과가 현재 stem과 정확히 일치할 때만 위치 정보를 제공하며, 별도 answer를 분리해 추측하지 않는다. 현재 itemId에 대응하는 공개 결과만 풀이에 사용한다. 데이터 쓰기·학습 일정 변경·생성기 import는 없다. 정답 색은 기존 bank-answer-point 스타일을 재사용하여 CSS 변경을 생략했다.

초기 실행 실패/중단은 성공과 구분한다. 서로 다른 Python 환경을 중첩한 최초 실행은 표준 라이브러리 충돌로 실패했고, server 환경으로 통일했다. 제한된 임시 경로의 SQLite 열기 실패와 로컬 통신 제한에 따른 중단은 프로젝트 내부 임시 폴더 및 허용된 로컬 검사 실행으로 해결했다. 최종 성공 로그는 state.json의 각 체크 마지막 항목에 연결되어 있다.

## 배포 대상 버전·순서·데이터 변경
기준 HEAD: 138f32dc432bbc54ed2e71604363782d28dd1014.
검사 대상은 이 HEAD 위의 미커밋 구현이며, site 영역 지문은 fe39b4480d65e01eac8c63c50f62a2e276c618200a577dc29ced938d6d49f8ca이다. 동일 소스로 서버 패키지 및 web/dist 고정 후보를 순서대로 준비한다.

대상: server/app/quiz_cloze.py, server/app/routes/prequiz.py, server/tests/test_prequiz_cloze.py,
web/src/lecture/PreQuizCloze.tsx, PreQuiz.tsx, PreQuizDifficult.tsx, web/src/types/quiz.ts,
web/src/notices/GuidePage.tsx, web/tests/prequiz-cloze.test.cjs, web/tests/prequiz.tsx 및 이 변경 기록.
다른 작업의 기존 미커밋 문서들은 이 변경 범위에서 제외한다.

DB 스키마·운영 데이터·문항 원문·학습 기록 변경 없음. 이후 배포 시 API 먼저, 웹 다음 순서다. 선택적 필드이므로 구버전 조합은 기존 표시로 동작한다. 유효한 source_stem이 없는 과거 카드는 기존 질문·답 표시를 유지한다.

## 배포 후 확인·롤백·필요한 사람 승인
사용자 2026-11-02 현재 채팅: “운영 사이트에도 배포해줘.” 이 발언을 동일 기능 범위의 서버 및 웹 운영 배포 승인으로 적용한다. 고정 후보를 만든 뒤 각각 해당 후보의 중요 승인 근거를 기록하고 배포 검사를 통과한 후 실행한다.
배포 후에는 실제 예습 cloze의 공개 전 답 비노출, 문장 속 강조, 어려웠던 문제 재방문, 이해 확인·되돌리기를 확인한다. 새 오류나 표시 불일치가 있으면 이 change ID와 연결한다.
롤백은 이 작업의 서버/웹 변경만 복원하며, 문항 재업로드·DB 복원·학습 기록 삭제는 필요하지 않다.

## 운영 배포 구성
- 서버: meddeck-503318/asia-northeast3/studyez-api. 이전 최신 준비 버전 studyez-api-release-1793523763317944700로 100% 트래픽 복원 가능.
- 웹: Cloudflare Pages study-ez-open/master, https://studyez.kr 및 https://study-ez-open.pages.dev. 이전 운영 배포 85172b8d-6d42-4920-9522-489ccccd8781. 업로드 전 동일 버전인지 검사한다.
- 순서: 서버 후보 준비→현재 사용자 승인 기록→deploy.ps1→실제 새 revision의 준비 상태·100% 트래픽·사후 검사→웹 후보 준비→동일 사용자 승인 기록→publish-web→실제 배포 ID·사후 검사.
- 기존 배포 도구의 환경/Secret Manager 동기화를 사용하며 환경 파일 수정·설정 범위 확대는 없다. 후보는 환경 파일 지문만 저장한다. DB 마이그레이션·문항 업로드·학습 평가는 실행하지 않는다.
- 필수 검사명 web/server/contracts로 재검증했다. web은 운영 번들에 로컬 검사 인증정보가 없는지 추가 확인, server는 cloze/once/kinds/routes 4개를 개별 실행, contracts는 6개 실제 실행·통과. 계약 검사의 최초 임시 폴더 생성 오류는 전용 로컬 폴더 지정 후 해결했다.
- 사후 검사는 production_smoke의 API health/CORS/인증 경계, 인증된 읽기 전용 source-context 및 웹의 HTML·JS·CSS·프롬프트 파일 SHA256 대조를 사용한다. 로그인된 예습 화면은 별도 브라우저 확인하며 평가·되돌리기 등 기록 쓰기를 하지 않는다.
- 배포 도구/설정 SHA256 postcheck.py: 31ad73598e844f3449fd9468dbba277c5489480019bf0e3b2d7badcc1e54141b
- 배포 도구/설정 SHA256 cloudflare_release.py: b131361d9ab01491fdffb588bf5d2a53a86ef702d071f57aa69bb3cdcf7625c5
- 배포 도구/설정 SHA256 server-release-config.json: 740a7a7e3f43a023e82a573b47354850c12f1f49d71a984cee3b2949568d1d74
- 배포 도구/설정 SHA256 web-release-config.json: 49c4e6eab79ef5e06d8f019a9bda1950dbc18a0fccb7d230b567fe040b783f55

## 실제 배포와 사후 확인 — 2026-11-02
- 서버 후보: 73439c9c457fd27d67fac0a98e0c2b0c1b687f201e768483f843406f144f6975 (139개 허용 파일).
- 서버 attempt: 1793594040147475800. 실제 revision: studyez-api-release-1793594040147475800. Ready/ContainerReady 및 latestCreated/latestReady 확인 후 100% 트래픽 전환을 검증했다. 배포 영수증 succeeded, health healthy, 읽기 전용 smoke 종료 0.
- 웹 후보: 692700c3af53a01792847246dbe7b938834c6e5fa090146936f2db48a376b848 (46개 파일).
- 웹 attempt: 1793594201879185500. 실제 Pages production ID: e6d07947-ddb9-4ff0-a225-b403e431d30a. 이전 운영 버전 일치를 확인한 뒤 고정 후보를 직접 업로드했다. 배포 영수증 succeeded, health healthy, smoke 종료 0.
- https://studyez.kr, https://study-ez-open.pages.dev, https://e6d07947.study-ez-open.pages.dev에서 HTML/JS/CSS/프롬프트 36개씩 총 108개 SHA256이 승인한 파일과 일치했다. API health/CORS와 익명·잘못된 토큰 차단, 인증된 source-context 조회도 통과했다.
- 로그인된 운영 브라우저에서 미생물학/260911_02 「세균의 분류 및 동정 (김범준)」의 c001을 확인했다. 공개 전 세 [____] 표시에서 답 공개 후 분류(Classification)·명명(Nomenclature)·동정(Identification)이 원문 위치에 각각 채워져 파란색 굵은 글씨로 강조됨을 DOM과 화면으로 확인했다. 답 공개 전후 진행률은 0/18이며, 평가·이해 확인·되돌리기 등의 기록 쓰기는 하지 않았다.
- 위 확인용 강의 선택에는 읽기 전용 DB 트랜잭션으로 첫 문항이 cloze인 강의 식별자만 조회했다. 문항·학습 기록은 변경하지 않았다. 어려웠던 문제의 즉시/재방문 적용은 같은 배포 소스의 로컬 UI 및 서버/웹 회귀 검사로 확인했다.
- 두 배포와 사후 검사 상세 영수증은 state.json, Pages 업로드 ID는 pages-upload.json에 보존한다. 별도 git push나 다른 작업의 문서 배포는 하지 않았다.
- 이 절은 배포 후 결과 기록이다. 기존 후보와 승인·검사 시점의 스냅샷은 각 deployment 영수증에 보존되며, 향후 새 배포에는 새 후보 검사를 적용한다.

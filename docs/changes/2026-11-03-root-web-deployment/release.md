# 자동전송 기반 뿌리 출제 배포와 콜린성 1건 시범 — 배포 준비

## 코드 리뷰·검증 결과
고정 배포 사본 `tmp/root-web`에서 source `2ba822b47c0eb7b231d6623eaac9ade87df477582e28da49f19e5986bc8142d6`, plan `3e9967b8008eef907def1cc595d237fbc1e7a94bf5547b920d457daed1e31b21` 기준 contracts/generation/runner/server/ui/web/root-regression 7개 통과. 계약 71·생성 27·러너 34개, 격리 서버 API/권한/이용현황, 자동전송 메시지→실제 MD 회수→HTTP 러너/합성 모델→별도 게시→학습/원본/지도, 기존 브라우저 2건과 적응형/04:00/보존 회귀를 확인했다. TypeScript 및 생산 빌드에서 테스트 로그인 토큰이 제거됨도 검사했다.

리뷰: 웹 요청은 held로만 생성되며 실제 원문 파일 전에는 CLI를 실행하지 않는다. generation_id·과목·강의·프롬프트 판·SHA/바이트 수가 일치하는 완성 파일만 수신한다. 전송 시도는 먼저 저장하며 중복 전송은 자동 반복하지 않는다. 수신 원문 지문을 러너 입력/결과 manifest에 묶고 첫 단계는 원문 보존 정리다. 기존 원본/독립 정답 검수·최대 수정 3회·검수 4회와 ambiguous ledger 보류를 유지한다. 기존 은행 및 링크·개인 수정·제외·학습 사건은 교체하지 않는다. 최초 정리의 전체 웹 Q ID도 대조한다.

다른 작업의 미커밋 변경(예습 cloze, 독립 연결 UI, 러너 데스크톱 등)은 배포 사본에서 제외했다. 사본은 HEAD에서 필요한 root 관련 파일만 추가했고, 공용 진입 파일에서 별개 연결 기능을 분리했다. 검사와 배포의 정본 state는 `tmp/root-web/docs/changes/2026-11-03-root-web-deployment/state.json`이다. 원래 작업 폴더의 다른 변경은 되돌리거나 섞어 커밋하지 않는다.

초기 사본의 긴 Windows 경로로 검사 파일 작성이 실패한 기록을 보존했다. 검사 임시 경로를 줄여 수정 후 같은 최종 소스 지문에서 모두 재검증했다. 배포 후보 저장도 짧은 경로로 사본을 이동했으며 소스·환경 파일 내용과 검증 지문은 유지했다.

## 배포 대상 버전·순서·데이터 변경
대상: 기존 Cloud Run `meddeck-503318/asia-northeast3/studyez-api` 및 Cloudflare Pages `study-ez-open/master` (`studyez.kr`). 서버/웹 각각 별도 고정 후보를 준비하고 사용자 현행 배포 발언을 구체적인 후보 승인에 적용한다. 직접 master push나 작업 폴더 전체 배포는 하지 않는다.

운영 DB에서는 새 root_content/root_control/root_session/root_event/root_generation 5개 표만 만들고 RLS를 켠다. 존재하는 root_generation에 웹 전송/응답 nullable JSON이 없으면 그 두 칼럼만 추가한다. 기존 은행·기록을 변경하는 마이그레이션은 없다. 준비 명령은 `scripts/root_production_schema.py --apply`이며 실행 전 읽기 확인에서 이 5개 표가 없는 것을 확인했다.

순서: 새 표/RLS → 고정 API 후보 배포와 revision 100%/health/auth/신규 경로 읽기 확인 → 현행 러너의 새 하위 프로세스 소스 확인 → 고정 웹 후보 배포 및 정확한 Pages ID/공개·인증 경계 확인 → Study EZ에서만 개인 시범 자동전송 1회. 전체 root 기능 플래그를 켜되 콘텐츠의 기본 허용은 요청 관리자 개인이다. 기존 루트 공개 판이 없는 상태에서 시작한다. 브리지 1.3.20 연결을 실제 Study EZ 화면에서 확인했다.

예시 원본은 등록된 콜린성 약리학(1) 261002_01 PDF 5,419,206바이트와 교수별 족보 MD 19,731바이트, 이미 수신한 Concept map/출제포인트다. 기존 은행은 build c7fbb80dee4540a1/ready/69문항이며 별도 보존한다. 과거 기존 은행 수정 잔여 횟수는 새 작업의 상한으로 초기화하지 않는다.

## 배포 후 확인·롤백·필요한 사람 승인
복원 API: `studyez-api-release-1793594040147475800`으로 기존 서비스 트래픽 복원. 웹: Pages production `e6d07947-ddb9-4ff0-a225-b403e431d30a`로 복원. 새 root 판을 비활성화하고 전송/실행을 멈출 수 있으며 원본·문항·수신 MD·ledger·검수·이전/새 학습 사건은 삭제하지 않는다. 새 DB 표는 비파괴적으로 보존한다.

사후 자동 확인은 기존 public HTTP/auth/CORS 및 새 root catalog/admin의 익명 차단, runner의 존재하지 않는 generation 입력 GET 404로 경로·표 접근을 확인하는 `scripts/root_production_smoke.py`다. 실제 로그인 UI·출제/회수/게시·검수 주석·고정 원본·포인트 지도는 별도 브라우저 증거로 확인한다. ChatGPT 탭에 에이전트가 직접 들어가거나 직접 답을 작성하지 않는다. Study EZ 자동전송 브리지만 사용한다.

사람 승인 근거: 2026-11-03 사용자 “배포하고 하나 예시로 돌려보자. Chatgpt에는 네가 직접 들어가지 말고 자동전송버튼을 이용하면 될듯.” 현재 기능의 배포·실제 1건 시범/필수 DB 준비·개인 시범 범위에 적용하며 새 범위의 포괄 승인으로 확장하지 않는다. 실제 배포 revision·응답·게시 결과는 별도 deployment.md에 누적한다.

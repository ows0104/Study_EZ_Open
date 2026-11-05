# 예습 기본 링크·GPT 초안 복구 운영 웹 배포 — 구현 계획

## 변경 범위·대상 파일·순서
1. Cloudflare 읽기 전용 목록으로 현재 운영 ID를 확인한다. 현재 기준은 57fe6571-2415-4250-9895-e5f2bb903171이다.
2. prepare_scope.py로 기존 운영 검증 사본의 site 소스를 새 사본으로 복사하고 재빌드한 web/dist가 이전 운영 후보와 바이트별로 같은지 확인한다. 기존 사본·현재 사용자 작업은 변경하지 않는다.
3. 원 승인 작업의 bridge 1.3.21 파일, PreviewAction, 관련 테스트만 반영한다. GuidePage는 예습 버튼/초안 복구 안내 hunk만 반영한다. 사후 검사 스크립트는 배포/공개 파일을 읽기만 한다.
4. bridge/web-links/web-types/web/contracts를 development.py verify로 새 사본에서 실행하고 코드·원본 보존·운영 기능 유지·ZIP/소스 일치를 리뷰한다.
5. 구체적 대상·복원 기준·검사 명령을 release-config에 고정하고 prepare한다. 현재 사용자의 운영 배포 지시를 해당 후보의 deploy 근거로 기록하고 check --phase deploy 후 publish-web을 실행한다. 동일 범위의 승인을 다시 요청하지 않는다.
6. 실제 Pages ID, studyez.kr 및 pages.dev의 배포된 번들·브리지 ZIP·인증 경계를 확인하고 결과를 원 작업 폴더에 보존한다.

## 검사 명령과 성공 조건
bridge: node --test tests/bridge/test_autosend.cjs tests/bridge/test_link_recovery.cjs tests/bridge/test_web_versions.cjs tests/bridge/test_bank_file.cjs tests/bridge/test_bank_download.cjs.
web-links: node --test web/tests/preview-actions.test.cjs. 실제 Chrome은 로컬 모의 화면만 사용한다.
web-types: npm --prefix web run typecheck.
web: npm --prefix web run build (고정 후보의 산출물/환경 지문을 남기는 정본 검사 이름).
contracts: server Python -m unittest discover -s tests/bridge -p test_extension_providers.py. 웹/확장/서버 제공자 URL·메시지·버전 경계와 링크 라우팅의 Node 검사를 함께 본다.
배포 smoke는 고정 후보와 원격 HTML/JS/ZIP 해시·예습 카드/초안 복구 문자열 및 기존 production_smoke.py의 health/CORS/익명 차단을 읽기 전용으로 확인한다.

## 위험·복원·승인할 범위
사용자 “운영 사이트에도 배포해줘”는 앞서 승인한 수정의 운영 웹과 브리지 ZIP 게시를 승인한 것으로 적용한다. 운영 API·DB, 확장 자동 설치·스토어 게시·GPT 자료 전송은 승인 범위가 아니다. 다른 작업의 미커밋 기능이 섞이면 배포하지 않고 사본을 정정해 재검증한다. 복원 기준은 직전 Pages 57fe6571-2415-4250-9895-e5f2bb903171이며 실제 기록은 유지한다. 배포 실패는 성공으로 표시하거나 자동 반복하지 않고 실제 원격 상태를 먼저 확인한다.

# 운영 웹 배포 — Implementation Plan

## 순서·파일
1. prepare_isolated.py로 검증된 현재 운영 소스를 별도 폴더에 복제하고 기존 산출물 전체를 재현한다. 승인된 아홉 파일만 적용하고 isolation.json에 입력 해시를 고정한다.
2. 별도 폴더의 development.py에 현재 사용자의 구현·배포 요청을 기록한다. verify_production_base.py와 block-selection 회귀, check_browser.py의 격리 로컬 브라우저 검사, TypeScript/production build와 tests/contracts 검사를 revision-bound로 수행한다.
3. 기존 cloudflare_release.py·postcheck.py·production_smoke.py를 이 작업 경로에 고정해 사용한다. 운영 직전 버전 확인과 현재 버전 복원 계획을 포함한다. release.md·코드 리뷰·정확한 웹 후보를 준비한 뒤 현재 사용자의 “그럼 운영 사이트에도 배포해줘.”를 해당 후보의 중요 승인 근거로 기록한다.
4. check --phase deploy 통과 후 release_evidence.py publish-web만 실행한다. 실제 게시 버전 및 사후 확인을 저장하고 공유 작업 기록에도 정본 위치·영수증·로그를 보존한다. Git push·서버 배포는 없다.

## 검사
production-base: verify_production_base.py. block-selection: node --test web/tests/study-blocks.test.cjs. browser: 로컬 Vite에서 격리 fixture 및 check_browser.py로 11가지 동작 확인. web: npm.cmd --prefix web run build(타입 검사 포함). contracts: 프로젝트 Python으로 -m pytest tests/contracts -q.

## 복원·승인
현재 사용자 요청은 위 동일 수정의 운영 반영을 명시 승인한다. 현재 운영 0ca1ec7b-bdc2-4775-8916-4b1dca98563d를 복원 대상으로 기록한다. 정적 웹만 변경하므로 DB/API/자료 복원은 없다. 자동 롤백·무한 재배포는 하지 않는다. 다른 작업의 수정은 건드리지 않는다.

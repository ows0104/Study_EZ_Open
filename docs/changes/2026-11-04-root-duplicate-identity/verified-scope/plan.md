# 자동 시험일과 재개 요청의 동일 작업 보존 — 구현 계획

## 변경 범위·대상 파일·순서
server/app/routes/root_generation.py에 고정 입력 동등성/중복 보존 helper, 원래 입력/requestId 응답, 요청 재사용, 중복 MD 저장 후 요청 종료·원문 보존, latest 원본 해석을 추가한다. web/src/bank/RootGenerationPanel.tsx는 재개 requestId만 원래 ID를 사용한다. server/tests/test_root_one_click.py에서 자동 날짜가 다시 전송돼도 동일 generation, 원래 입력으로 재개, 시간표 변경/자료 조회 없이 같은 requestId 재개, 실제 중복 MD 보존·모델 미등록·취소/변경 입력 경계를 확인한다. 변경 전 승인 범위를 기록하고 관련 파일만 고정 배포 사본에 반영한다.

## 검사 명령과 성공 조건
contracts 전체, server root_generation/root_web_generation/root_one_click/root_job_claim/root_preservation/route_contract 격리 검사, web TypeScript/생산 빌드/테스트 토큰 비포함 검사를 development.py verify로 기록한다. 새 원본/범위/확인된 시험일은 기존 작업으로 합치지 않아야 한다. 구형 provided 요청·공개 충돌·취소·응답 덮어쓰기와 기존 게시/학습 보존 회귀를 포함한다.

## 위험·복원·승인할 범위
이미 승인된 단일 버튼/배포/개인 시범 범위의 중복 방지 수정이며 새로운 내용 수용 정책은 포함하지 않는다. 고정 API 후보 검증 후 배포·사후 확인, 웹 고정 후보 배포·사후 확인, job525만 중복 보존 처리한다. API 복원 기준 studyez-api-release-1793707198430414200, 웹56553b7c-ddef-492f-af4d-5cdf4c6ab524. 필요하면 코드/트래픽만 복원하며 중복 원문과 원래 시범/검수 원장은 삭제하지 않는다. job525가 자동으로 재시작되지 않도록 중복 종료 상태를 유지한다.

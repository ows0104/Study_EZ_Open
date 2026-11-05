# 예습 기본 링크·GPT 초안 복구 운영 웹 배포 — 배포 준비

## 코드 리뷰·검증 결과
운영 검증 사본의 baseline 재빌드가 직전 Pages 후보 4c8b9dc6be6df49de1e31d9f0f54c53686c99deaa727e8beaa18489c7ae68cea의 전체 파일 manifest와 일치했다. 그 사본에 이번 승인 범위 13개 파일만 변경/추가했다. 가이드는 예습 버튼·초안 복구 안내 3줄 hunk만 반영했다. 새 사본에서 bridge 92/92, 실제 Chrome 모의 화면 12/12, 웹/확장/서버 계약 7/7, TypeScript 및 생산 빌드가 통과했다. 데이터 보존·중복 전송 방지·버전/ZIP/서버 URL 계약과 변경 allowlist를 자체 리뷰했다. 최초 bridge 검사는 테스트 fixture 2개 복사 누락으로 실패했으며, 기존 운영 사본의 동일 fixture를 복사한 뒤 92/92 통과했다. 제품 코드를 추가 변경하지 않았으며 실패 기록을 보존한다.

## 배포 대상 버전·순서·데이터 변경
대상은 Cloudflare Pages study-ez-open/master의 studyez.kr와 study-ez-open.pages.dev, 다운로드 브리지 1.3.21 ZIP이다. 현재 운영 기준은 57fe6571-2415-4250-9895-e5f2bb903171이다. 새 사본 source 지문 b51f7bdb77ec7b8a70c8ecd837fa8626c27a2007e517b8d9e715c88a709d8ac4, plan 지문 4faa0fc2ef417f591bd583991bd53a9be95ac7079bbc06dbd07e8828d9d23650, web artifact 지문 fcaf7347a8f3e7efa9f9233392d03383640370fc969a02f36ce89cc9169504dc. 정본 소스/검사/후보/영수증은 tmp/preview-bridge-20261105에 보존한다. prepare 후 고정 후보만 publish-web으로 업로드한다. API/DB/인증 설정·실제 데이터 변경과 GPT 자료 전송·스토어 게시는 없다.

## 배포 후 확인·롤백·필요한 사람 승인
사용자 2026-11-05 “운영 사이트에도 배포해줘”를 앞서 승인한 수정의 웹·ZIP 운영 배포에 적용한다. 같은 범위의 승인을 다시 요청하지 않는다. prepare/check 뒤 배포된 정확한 Pages ID를 확인하고, 사후 스크립트는 studyez.kr/pages.dev/고유 배포 URL의 HTML·ZIP과 변경된 JS를 고정 후보 바이트와 대조한다. 기존 production_smoke.py로 API health/CORS와 보호 학습 경로 익명 차단을 확인한다. 모두 읽기 전용이며 실제 자료를 생성·전송하지 않는다. 실패 시 업로드 상태를 확인하고 실패/미확인을 그대로 남긴다. 복원은 Cloudflare Pages의 직전 성공 배포 57fe6571-2415-4250-9895-e5f2bb903171로 rollback하며 기존 원본·학습·검수·대기 응답을 유지한다. 결과는 deployment.md에 남긴다.

2026-11-05 01:03 KST 운영 배포 완료: Pages `d7970ab3-67ef-4598-aaf5-8903bd268b1e`, 후보 `8f20afebae1d3e393dc6684c87025d310271e36cbff8e1cbac7b0d42e5ef75d8`. health와 읽기 전용 사후 검사가 통과했고 3개 origin의 HTML/ZIP 및 변경 JS 27개가 후보와 일치했다. 상세는 deployment.md를 따른다. prepare 당시 release 원문은 verified-scope/release.md 및 분리 실행 공간에 보존한다.

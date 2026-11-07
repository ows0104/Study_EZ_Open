# 운영 반영 완료

2026-11-07 사용자: “PR 16 병합하고 사이트에 반영해줘.” 이 발언을 검증된 PR16 head 8d010b19265b462ae9d296ad5dc7d14827319791의 병합·일반 코드 배포 승인으로 적용했다.

PR16은 b8a9540ae4d4991c935d6e68835d90fd54c683a6으로 병합됐다. master 자동 실행 https://github.com/ows0104/Study_EZ_Open/actions/runs/42369151301 의 Tests and build 및 Deploy production API가 모두 success다. Pages production 219bb8bf-6698-438f-a6e0-e6598eed9035도 같은 b8a9540 소스로 게시 완료됐다.

운영 health가 production / status ok / 정확한 전체 merge SHA를 반환했다. 공개 studyez.kr HTML과 Pages의 실제 RootLearning-xaIt3kg-.js에서 네 평가와 selfRating·답 입력 제거를 확인했다. RootPdfSlides-CGcfuPuE.js 및 pdf.worker.min-CIqJB0yW.mjs를 실제 다운로드했고 worker SHA가 검증된 로컬 라이브러리 파일과 일치했다. 한국어 CMap도 실제 제공된다. 무인증 root-learning API는 401이다.

생산 자료/문항/권한 변경 및 운영 사람 학습 사건 쓰기 0. 로그인 후 동작은 앞서 격리 Chrome 브라우저에서 검증했으며 운영 학습 평가를 테스트로 만들지 않았다. 공개 응답 검증에서 urllib의 Pages 요청은 403이었고 curl의 실제 공개 HTTP 요청으로 정상 파일을 확인했다. 실패를 숨기지 않는다.

로컬 기계 근거: runs/_development/2026-11-07-main-quiz-pharm-ui/production-receipt.json. 예시 PNG와 이전 검증 근거는 그대로 보존한다. 배포 기록만 기능 브랜치에 보존하며 새로운 master 배포를 만들지 않는다.

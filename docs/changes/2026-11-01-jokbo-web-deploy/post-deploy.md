# 웹 배포 및 사후 확인

2026-11-01 KST, 현재 사용자 “오케이 그럼 웹배포도 해줘.” 승인에 따라 완료했다.

- 실제 Pages production: `0ca1ec7b-bdc2-4775-8916-4b1dca98563d`.
- 검증한 고정 후보: `9e7a9fdb6bd0b7bf1f726689d485c4c39a4a08465165db9db1fe1dd829b074be`.
- 기존 운영 `a0edf1f4-981e-4568-8b5a-7c2ad1e54617`을 전체 파일 바이트까지 재현한 뒤 교수 확인의 네 파일만 반영했다. 이용현황 개선과 예습 판정을 보존했다.
- 프롬프트 회귀 10개·공용 계약 6개·운영 기준 보존 검사·TypeScript/production build 통과. 테스트 보조 원본/임시 경로 누락으로 난 초기 실패는 보존했고 경로를 바로잡은 해당 검사를 재실행해 통과했다.
- 최신 사후 확인: 사이트 healthy, API health/CORS/인증 경계 정상, 권한 있는 읽기 전용 강의 원본 조회 정상. studyez.kr·study-ez-open.pages.dev·고유 배포 주소의 HTML/JS/CSS/정본 프롬프트 36개씩 총 108개 SHA256이 고정 후보와 일치했다.
- 새 복습/Quiz Bank 요청에는 실제 올해 필기 파일명 교수 재확인 및 같은 교수 기출 우선 규칙이 적용된다. 기존 PDF 첨부·JSON·그림·문항·학습 기록·DB/API는 변경하지 않았다.

검증·후보·배포·최신 postcheck의 정본은 `output/releases/jokbo-web-deploy/docs/changes/2026-11-01-jokbo-web-deploy/state.json`이다. 작업 기록과 실제 게시 영수증·로그는 공유 폴더에도 사본을 보존한다. 공유 작업 폴더의 다른 미커밋 코드는 배포하지 않았다.

복원 대상은 직전 Pages `a0edf1f4-981e-4568-8b5a-7c2ad1e54617`이다. 이번 작업은 웹 정적 배포만 수행했으므로 DB/API/자료 복원은 필요하지 않다.

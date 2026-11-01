# 운영 웹 배포 — Spec

## 계약과 수용 기준
기준은 output/releases/jokbo-web-deploy의 검증된 현재 운영 소스·고정 후보이며 실제 Pages production ID가 0ca1ec7b-bdc2-4775-8916-4b1dca98563d인지 업로드 직전까지 확인한다. 원래 빌드를 바이트 해시까지 재현하고 web/CLAUDE.md, StudyOverview.tsx, studyBlocks.ts, useStudyCourse.ts, calendar/entries.ts, GuidePage.tsx와 세 회귀 검사 파일만 적용한다. 변경 내용은 2026-11-01-block-auto-selection의 승인·검증 범위와 같다.

별도 output/releases/block-auto-deploy에서 소스 allowlist 검증, 회귀 13개, 실제 브라우저 전환 11가지, TypeScript/production build, 공용 계약 검사를 실행한다. 검사와 후보는 이 별도 소스의 지문에 결합한다. 고정 산출물을 study-ez-open/master에 게시하고 실제 배포 ID·건강 상태·기존 API 인증 경계·읽기 전용 강의 조회·운영/Pages/고유 배포 주소의 파일 SHA256을 확인한다.

## 보존
현재 운영의 미커밋 개선을 기준 소스에서 보존한다. 공유 폴더의 다른 미완료 수정은 배포하지 않는다. 비밀 값은 환경 파일에서만 재사용하고 출력·배포 산출물에 넣지 않는다. API·DB·PDF·문항·학습 기록은 쓰지 않는다. 기존 운영 버전이 달라지면 업로드 전에 중단해 새 기준을 검토한다.

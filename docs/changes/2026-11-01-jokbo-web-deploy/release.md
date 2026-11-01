# 현재 운영 웹에 복습 교수 재확인 규칙 배포 — 배포 준비

## 코드 리뷰·검증 결과
현재 Pages production a0edf1f4-981e-4568-8b5a-7c2ad1e54617의 검증 소스에서 별도 사본을 만들었다. 교수 규칙 반영 전 빌드의 모든 파일이 해당 운영 고정 후보 bcb69fa47fdf87fd955cf63a7fab76c4b2bb52c567f3fa40485d1486cfd36c3d와 바이트 해시까지 일치했다. production-baseline.json에 전수 파일 해시를 보존했다.

그 위에 이전에 검증한 교수 확인 helper·reviewPrompt·bankPrompt 1.79·회귀 검사 네 파일만 반영했다. production-base 검사가 소스 차이 allowlist와 입력/이전 후보 해시를 확인했다. 프롬프트 회귀 10개와 공용 계약 6개, TypeScript/production build가 통과했다. 웹 산출물 지문은 c7586bb4225535ad9bc094bb7e97d79f07af0cf5d18996c79fc808e1bdf7b78d다.

검증 및 배포 기록의 정본은 output/releases/jokbo-web-deploy 안의 scripts/development.py와 docs/changes/2026-11-01-jokbo-web-deploy/state.json이다. 공유 폴더의 다른 작업 소스를 직접 빌드·배포하지 않는다. 이용현황 개선과 기존 예습 판정을 보존한다.

## 배포 대상 버전·순서·데이터 변경
Cloudflare Pages study-ez-open/master, studyez.kr 및 study-ez-open.pages.dev에 고정 웹 산출물만 게시한다. 실제 올해 필기 파일명 교수를 복습에 우선하고, 이름 미확인/필기자 구분·같은 교수 기출 우선·다른/미상 기출 참고 지침을 제공한다. 서버·DB·기존 첨부 PDF·문항·학습 상태는 변경하지 않는다.

현재 사용자의 “오케이 그럼 웹배포도 해줘.”가 앞서 보류한 동일 기능 배포의 명시적 승인이다. 새 후보 prepare 후 이 발언을 정확한 후보의 deploy 근거로 기록하고 check --phase deploy 및 release_evidence.py publish-web을 실행한다. 업로드 직전 production ID가 기준 버전 그대로인지 다시 검사한다. Windows 짧은 경로는 os.path.samefile로 같은 폴더임을 확인하고 전달한다.

## 배포 후 확인·롤백·필요한 사람 승인
postcheck.py는 건강 상태·공개/인증 경계, runner 권한의 읽기 전용 강의 원본 조회 및 사이트/Pages/고유 배포 주소의 HTML·JS·CSS·정본 프롬프트 SHA256을 확인한다. 배포 ID와 최신 production 목록이 정확히 일치해야 성공으로 기록한다. 정적 파일 전수 대조로 실제 교수 확인 규칙과 이용현황 개선이 함께 게시됐음을 확인한다. 생성·전송·학습 평가를 실행하는 검사는 없다.

복원 대상은 직전 실제 운영 a0edf1f4-981e-4568-8b5a-7c2ad1e54617이다. 문제 발생 시 그 Pages 버전을 복원하며 DB/API/자료에는 복원 변경이 필요하지 않다. 실패·확인 불가를 성공으로 처리하지 않고 실제 영수증을 보존한다.

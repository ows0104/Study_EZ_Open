# Implementation Plan

현재 명시적 구현 요청을 승인 근거로 한다. web/src/connection-pilot에 데이터·상태·React 화면·CSS, 별도 HTML/Vite 설정과 실행 스크립트, tests에 상태 전이 검사를 추가한다. 기존 전역 파일 수정은 package.json 실행 명령 추가로 제한한다. 코딩 후 typecheck, 상태/데이터 테스트, 전용 build, 실제 브라우저 공개·후속·저장·검토·모바일 화면을 확인한다. 실행은 127.0.0.1 전용이며 운영 배포는 하지 않는다. 복원은 새 파일과 추가 script 항목만 대상이다.

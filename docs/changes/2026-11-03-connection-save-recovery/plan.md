# Implementation Plan

현재 요청과 기존 연결 학습 제품 Build 승인을 적용한다. web/src/bank/connectionRecovery.ts에 요청별 보관·기존 보관함 이관·초안 보존을 구현하고 ConnectionLearning.tsx에 연결한다. 충돌 보존 입력을 화면에서 확인하고, 새로고침 시 초안과 미확인 요청을 복원하며 POST 후 최신 GET으로 재개한다. 안내 문구도 실제 동작에 맞춘다.

검사: server는 기존 제품 check.py로 격리 API/경로/이용현황/개인문항 회귀를 실행한다. recovery-ui는 요청별 보관 단위 검사와 실제 제품 화면의 합성 API 브라우저 검사로 입력 복원, 저장 응답 유실, 최신 상태 재조회, 충돌 보존, 모바일을 확인한다. web-types는 실제 타입 검사, web-build는 web에서 npm run build 전체 실행이다. development.py verify에 모든 검사를 기록하고 현재 revision에서 review/release gate를 확인한다.

복원은 이번 웹 보완만 되돌린다. 보관함과 충돌 응답을 삭제하지 않는다. 다른 작업의 변경은 보존한다. 운영 배포·공개·DB 변경·새 의학 답안/모델 호출은 범위 밖이다.

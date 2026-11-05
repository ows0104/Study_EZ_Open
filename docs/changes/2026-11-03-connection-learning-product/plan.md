# Implementation Plan

현재 실제 구현 요청을 API/DB/실제 앱 통합 Build 승인으로 적용한다. 전용 SQLAlchemy 모델·API·관리자 콘텐츠 등록/공개·학습 화면·BankStart 진입·안내를 구현한다. 신규 표는 create_all 및 PostgreSQL RLS hook으로 준비하며 운영 DB에는 접속하지 않는다. 격리 DB 테스트로 권한/단계/중복/충돌/보존을 확인하고 타입·제품 빌드를 실행한다. 원래 시범은 보존하되 제품은 시범 전역 스타일/로컬 상태를 사용하지 않는다. 운영 반영은 DB→API→웹 순서의 별도 후보로 남긴다.

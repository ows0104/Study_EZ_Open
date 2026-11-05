# 실제 제품 구현 위치

- 서버: app/models/connections.py, app/routes/connections.py. main.py에 등록, models import로 init-db 표 생성/RLS hook에 포함.
- 웹: bank/ConnectionLearning.tsx. App의 인증된 강의 경로, Main-Quiz 시작 및 미준비 화면에서 진입.
- 관리자: 같은 화면에서 JSON 파일의 제목·판·범위·원문을 검토한 후 비공개 등록. 명시적 공개/중지.
- 이용현황: connection_save는 서버에 확정된 이동·열람·자기확인 작업 수이며 숙련이나 완료 수가 아니다. 원문 답을 관리자 집계로 전달하지 않는다.
- 내용: Document(title, revision, scope, bundles). 각 Bundle에 root/follow(question, answers, explanation), 분류/나열(type), 구조(structure), 학습 역할(role), connection/next, 구조·시험·임상 근거, 출처와 gap을 둔다. 기존 시범 Bundle 구조를 일반 강의 입력으로 검증한다. 공용 learning-links 전체 계약을 대신하는 인증은 아니다.

로컬 실제 앱 확인: serve_local.py는 tmp/connection-product-local/app.db만 사용하고 운영 .env를 읽지 않는다. API 8016, 실제 Vite 앱 5187. 웹은 기존 local-test 개발 인증을 사용한다. 공개 주소나 운영 로그인 우회가 아니다.

첫 10묶음 외 자료도 같은 등록 경로로 사용할 수 있다. 기존 49문항 원문은 유지하며 아직 이 새 두 단계 질문 형식으로 전부 변환하지 않았다. 콘텐츠 자동 생성/대조 파이프라인과 오늘 추천은 이 서버 학습 기능의 완료와 구분한다.

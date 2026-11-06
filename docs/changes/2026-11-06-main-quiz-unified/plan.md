# 새 생성·학습 파이프라인을 Main Quiz에 통합 — 구현 계획

## 변경 범위·대상 파일·순서
서버 root_learning.py에 읽기 전용 Main Quiz entry 판정 추가, usage 라벨만 갱신. BankPanel의 기존 공부하기 카드를 새 자료 유무와 연결하고, BankStudy 기존 진입에 structured/legacy 선택을 연결하고 BankStart의 별도 root 링크를 생성/지도 진입으로 통합한다. RootLearning/Solve/Today/Map/GenerationPanel 및 전용 main-quiz.css에서 Main Quiz 표시·기록·빈칸·선지·단축키를 연결한다. 내부 파일명/URL/사건코드는 호환 보존. 새 웹 출제에도 별도 web-author.md의 회상 부담 지침을 실제 전송하고 최종 결합 프롬프트 지문을 고정한다. 공통 1.82 정본은 보존한다. 짝짓기·순서형의 발문 항목과 답은 공개 전후 허용 목록에서 보존한다.

## 검사 명령과 성공 조건
main-quiz-contract: 공개/허용계정/중지/구형서버/기존자료·학습 보존과 새 진입, 회상 단위 계약. server-regression: root/bank/route/usage/보존. web: UI 단위/타입/빌드. browser: 실제 격리 API/SQLite와 새 자료로 기본 Main Quiz 주소에서 시작·답 공개·평가·undo·맵·새로고침/계정 분리·기존 자료 호환 확인. 대상 snapshot/실행 지문을 보존한다.

## 위험·복원·승인할 범위
사용자 승인: 사이트 Main-Quiz 대체 구현과 운영 코드 반영. 범위 조정 명시 승인으로 App/메뉴/캘린더/목록/GuidePage/전역CSS는 다른 세션에 남긴다. 새 코드만 테스트/리뷰/PR/일반 자동배포 경로로 반영하며 기존 운영 자료·학습/권한·검수횟수는 변경하지 않는다. 기능 전역설정 활성화가 필요하면 실제 상태와 데이터 준비를 확인한 뒤 현재 사이트 대체 승인 범위에서 기록하고 수행한다. 해당 변경이 기존 허용계정·강의 검토/활성화 조건을 우회해서는 안 된다.

# Implementation Plan

1. 기존 RootGeneration에 웹 전송/수신 증거를 추가하고 전용 입력·전송·수신 API를 연결한다. file MD 공용 검증을 재사용한다. 웹 대기 작업은 자동 실행되지 않는다.
2. RootGenerationPanel 자동전송 버튼·완성 파일 복구와 bankBridge generation_id 수신 분기를 구현한다. 현재 설치 확장의 은행 파일 계약과 버전을 유지한다. 기존 bank 링크는 자동 생성 작업 동안 보존한다.
3. connection_generate에 웹 원문 보존 정리와 입력 지문을 연결한다. 검수/수정 상한과 실패 ledger 보존은 기존 구현을 유지한다.
4. production 배포에 필요한 root flag 전달, 관련 소스 사본/DB 준비와 고정 후보를 준비한다. 사용자 현재 발언을 Build와 이 기능/기존 서비스/개인 시범의 Deploy 승인으로 적용하며 같은 범위 재승인을 요청하지 않는다.
5. contracts/generation/runner/server/ui/web/root-regression 검사를 현재 배포 사본에서 실제 실행하고 review/release 및 고정 후보 승인 근거를 기록한다. API·웹 실제 revision과 read-only smoke를 확인한다.
6. Study EZ에서만 261002_01을 열어 수신된 map/points로 개인 시범 자동전송을 1회 누른다. ChatGPT 직접 접속 없이 회수·러너·게시 상태로 완료를 검증하고 생성 결과 링크/미해결 사항을 보고한다.

복원은 전송 중지·새 판 비활성화 및 이전 앱 revision 복원이며 생성 입력·원본·파일·ledger·학습 기록을 삭제하지 않는다.

# 구현 계획 — 승인된 P3b

1. 현재 작업 트리를 비밀값·실제 데이터 없는 복사본으로 만들고 전후 SHA-256을 기록한다.
2. 변경 전 runner 검사를 실행한다. bank/publish/agent의 함수·호출자·기존 테스트를 조사한다.
3. transport와 agent_state를 추출하고 publish/agent의 기존 import를 유지한다.
4. bank를 sources/state/execution/upload로 분리한다. 실제 실행은 기존 run_forwarded를 유지한다.
   원본 함수 AST 동등성을 비교하며 추출한 실패·업로드 구간은 기존 동작과 차등 재현한다.
5. 모듈 소유 위치로 mock을 갱신하고 HTTP 인증·서명 파일 헤더·재시도·부분 실패 검사를 추가한다.
6. runner 전체, 공용 계약·개발 게이트 검사를 수행한다. CLI help 및 별도 프로세스 import로
   진입점·순환 의존·경로를 확인한다. 네트워크/모델은 대역을 사용한다.
7. 기능별 읽기 지도를 갱신하고 코드 리뷰·release 준비를 기록한다. 다른 변경 파일을 보존하면서
   백업·충돌 확인·검증된 파일만 원본에 반영한다. 적용본과 테스트 코드 해시를 대조한다.

현재 사용자의 명시적 P3b 승인으로 실행한다. 실제 러너 가동·배포·운영 업로드 승인은 포함하지 않는다.
복원은 work/runner-originals와 runner-apply-manifest.json으로 이번 파일만 되돌리는 방식이다.
기존 사용자 변경이나 runs 원본을 복원 명목으로 덮어쓰지 않는다.

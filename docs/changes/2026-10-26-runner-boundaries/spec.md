# 설계

- runner/bank.py는 기존 run/prepare_points/jokbo_slices와 보조 함수 import의 호환 진입점이다.
- bank_flow/execution.py: 자료·재개 기록으로 CLI 인수를 구성하고 기존 subprocesses.run_forwarded로 실행한다.
- bank_flow/sources.py: 붙였던 PDF 선택과 족보 조각 캐시. 원본 선택·캐시 키·경로 유지.
- bank_flow/state.py: JSON 읽기, 기존 은행/웹 응답 식별자, 재개 여부, 남은 수정 횟수, 검수 요약.
- bank_flow/upload.py: 실패 보고, 이미지 확인/업로드/재확인, 결과 PUT, 기존 단계 로그와 시간 기록.
- runner/transport.py: Client, PublishError, Upload, MIME/URL 처리, 파일 재시도.
  publish.py는 대상 자료 계획·보류·게시 ledger를 유지하며 기존 이름을 재수출한다.
- runner/agent_state.py: 로그 의미·한도/동기화 대기·인증 재시도 기록.
  agent.py는 일감 실행·잠금·중단·하트비트·업로드 직렬화의 소유자로 유지한다.
- HTTP 경로/헤더/본문/호출 순서, CLI 인수·종료 코드·로그 형식, 캐시/재개 파일 형식은 같다.
- 수정 상한·예외·사용자 기록·학습 정책은 변경하지 않는다. 원본 데이터 폴더는 접근하지 않는다.
- import 호환성은 유지하되 테스트 mock은 실제 소유 모듈을 대상으로 한다.

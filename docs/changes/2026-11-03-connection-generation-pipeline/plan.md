# Implementation Plan

현재 사용자 자동출제·게시 연결 요청을 아래 코드/격리 검증 범위의 Build 승인으로 적용한다.

1. studyez_contracts/roots/automation.py: 정규화 brief·검수 결과·포인트/방향→과제 어댑터. learning_links와 bank 계약을 재사용한다.
2. quizbank/connection_generate.py 및 단계 프롬프트: 원본 사본/텍스트/이미지 → brief → BANK → 원본 대조+독립 정답 검수 → 최대 3회 수정 → roots/1와 실행 증거. 같은 job 출력 폴더의 단계 ledger를 재사용하고 중단·실패·완료를 구분한다.
3. RootGeneration 새 표/RLS 및 전용 API: 관리자 입력·요청 중복·원본 고정·기존 bank 큐 등록, runner 입력/결과, 조건부 원자적 콘텐츠 게시. 기존 bank-response에서 명시적 생성 작업만 분기한다.
4. runner/connection_generation.py: 서명된 고정 원본 다운로드/지문 확인, 생성기 하위 프로세스, 결과 재시도 게시. 모델/토큰/서명 URL을 생성 원문이나 로그에 섞지 않는다. 기존 runner finish_bank 요약 계약을 유지한다.
5. 실제 RootLearning/BankPanel의 요청 UI·진행/실패·공개 대상, RootMap 포인트 대조, 답 공개 후 검수/원본 링크, 이용현황 등록과 안내를 연결한다.
6. 새 check 실행기로 contract/generation/runner/server/ui/web-types/web-build/root-regression 8개 required_checks를 실행한다. 합성 PDF·모델 stub·실제 격리 API/DB/브라우저로 입력→큐→러너→원자적 게시→학습을 검증한다. 서버는 파일별 독립 프로세스, source/기존 상태/수정 상한·중복/취소/지문 충돌 회귀를 포함한다. 최종 같은 코드 지문에서 review/release gate를 기록한다.

복원: 신규 요청 경로 사용 중지 후 이전 앱/러너로 돌아간다. 생성 입력·원본 사본·각 모델 결과·실패 로그·검수 상한·기존/새 콘텐츠와 사용자 사건은 삭제하지 않는다. 실제 운영 배포·콘텐츠 일괄 생성은 이번 로컬 Build의 자동 후속으로 실행하지 않는다.

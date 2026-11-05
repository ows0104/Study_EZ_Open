# Implementation Plan
1. claim 반환 helper에서 RootGeneration을 실제 job ID로 검증해 rootGenerationId를 추가한다.
2. Agent Job/claim/블럭 판단/명령 인수와 bank CLI를 같은 ID에 연결한다. 기존 일반 작업과 중지·취소·시간표 실패 제한은 그대로 둔다.
3. 계약 검사, runner 전체(범위·ID 고정·일반 작업 차단·취소 포함), 격리 root/claim/route API를 검사한다. 검토·배포 기록과 현행 사용자 승인 근거로 고정 API 후보 및 로컬 러너를 갱신한다. 다른 작업이 실행 중이면 멈추지 않고 안전한 시점을 기다린다.
4. 기존 시범 job 524만 같은 입력·남은 상한으로 재개해 실제 검수/게시 결과와 기존 69문항 보존을 확인한다. ChatGPT에 직접 들어가거나 모델 호출을 초기화하지 않는다.
복원: 직전 API revision 및 로컬 변경 이전 코드. 원본·응답·ledger·데이터는 삭제하지 않는다.

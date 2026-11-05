# 불확실한 연결을 미준비로 보존하는 뿌리 학습 채택 — 구현 계획

## 변경 범위·대상 파일·순서
1. 원래 실행 코드/입력/원장/완료 출력의 hash 증거를 보관한다.
2. studyez_contracts/roots의 순수 채택 함수와 합성 계약 검사를 작성한다. 기존 learning_links/validate.py의 엄격한 수용 규칙은 유지한다.
3. quizbank/connection_generate.py의 최종 문서 조립과 server/app/routes/root_generation.py의 소비자 재검증·검토 결과 표시에 같은 함수를 연결한다. raw AUDIT와 임상 검수 판정은 그대로 보관한다.
4. runner에 완료된 동일 캐시만 조립·검증·전송하는 제한된 운영 경로와 검사/증거를 둔다. 실패/started 단계 재실행, 독립 검수 추가, 원장 초기화는 금지한다.
5. 관련 변경만 담은 고정 사본에서 검사·리뷰·API 고정 후보/사후 확인을 마친 뒤 동일 시범1건을 개인 게시하고 기존 은행 보존·화면의 미준비 표시를 확인한다.

## 검사 명령과 성공 조건
scripts/development.py의 contracts 체크는 tests/contracts 전체, generation은 tests/quizbank/test_connection_generate.py, server는 격리 root_generation/root_web_generation/root_one_click/root_preservation/route_contract를 실행한다. runner는 완료 캐시 조립/게시와 모델 호출 금지·지문 불일치 보류·실패/started 거절·상한 유지·임상 판정 보존을 검사한다. 새 누락/역할 불일치/잘못된 coverage, 위조된 채택 증거는 전부 합성 자료로 검사한다. UI 변경이 필요하면 web 체크와 실제 화면 확인을 추가하고 계획을 갱신한다.

## 위험·복원·승인할 범위
새 동작은 불확실한 방향의 채택을 낮출 수만 있으며, 의미 판정/관계를 대신 작성하지 않는다. 원본 오류를 숨기거나 부분 결과를 전체 검수 통과로 부르면 안 된다. 원본 지문·검수 전수·전역 참조 오류는 계속 전체 보류한다. 변경 전 API revision은 studyez-api-release-1793707198430414200이며 복원 시 새 roots 판만 비활성화하고 자료/검수/학습 기록은 삭제하지 않는다.

현재는 제안 단계다. 이 부분 채택 방식에 대한 사람의 선택을 받은 뒤에만 구현한다. 추가 문항 수정이나 추가 의학 검수 승인을 요청하는 계획이 아니다.

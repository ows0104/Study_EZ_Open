# 중요도 근거 통합 — 구현 계획

## 변경 범위·대상 파일·순서
브랜치 `claude/root-importance-basis`(origin/master 5acb5287).
1. `studyez_contracts/bank/importance.py`(새 파일): 근거 kind·점수·판정·포인트표·목표 3축·Must-Know 비율. 검사 `tests/contracts/test_importance_basis.py`.
2. 은행 3.3: `bank/schema.py`(문항 `point_ids` 선택 칸, 버전), `bank/priorities.py`(버전별 IMPORTANCE), `bank/validate.py`, `bank/quality.py`.
3. 포인트 `exam-point-extract/3`: `point-output.schema.json`·`point-extract.md`(v2 사본 보존), 예시.
4. 루트 생성: `quizbank/connection_generate_v2.py`가 `importanceTable`을 저작·원본 대조 입력에 넣고 조립 때 투영한다.
   `roots/generation_v2.py`: `project_importance`·`make_document` snapshot 허용 범위·`validate_result` 재계산·`quality_reasons` 보정.
5. 지시문: `automation/author-v2.md`(point_ids, 표 값 옮기기), `automation/source-v2.md`(근거 확인).
6. 감염병리1 실행 스크립트: 새 폴더 `runs/_e2e/26110803`, Map은 26110802 것을 복사, 포인트부터.

## 검사 명령과 성공 조건
루트 `pytest tests`, `map_numbers --check`, 서버 bank·root_·route_contract·retention(격리 sqlite).
기존 결과·3.2 은행 검증 불변. 감염병리1 새 실행 조립 성공, 등급 분포 보고.

## 위험·복원·승인할 범위
구현·검사·PR·병합은 사용자 요청(2026-11-08 「고친 뒤 다시」와 이후 토의)으로 진행한다.
감염병리1 재실행은 S1·S2를 Codex(gpt-6.1-sol)로 보내는 같은 범위이며, 사용자가 「고친 뒤 다시」로 요청했다.
복원: 병합 되돌리기. 운영 DB·은행·학습 기록 변경 없음.

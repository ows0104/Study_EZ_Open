# 중요도 근거 통합 — 배포 준비

## 코드 리뷰·검증 결과
- `studyez_contracts/bank/importance.py`(새 파일, 서버 별칭 `server/app/bank_validation/importance.py`)
  - 근거 kind·점수·판정을 둔다: 예고는 Must-Know, 제외는 Optional, 하이라이트는 Important 바닥값, 필기강조형은 +1.
  - 포인트표, 문항 판정(포인트별 최대), 목표 3축(unreviewed 없음), Must-Know 비율 경고(34%), 예고 원문 번짐 보고를 한다.
- 은행 3.3
  - 문항에 `point_ids` 선택 칸을 더했다.
  - importance는 5/4/3/2다.
  - `validate_bank`가 버전별 표로 확인한다. 3.2 이하는 그대로다.
- `exam-point-extract/3`: `point-output-v3.schema.json`·`point-extract-v3.md`. v2와 병렬 경로는 그대로다.
- `generation_v2`
  - 새로 넣은 것: `importance_table`·`target_importance`·`point_id_reasons`·`project_importance`/`restore_importance`
  - `make_document(importance=…)`: snapshot이 tier·importance만 다른 경우를 허용한다.
  - `validate_result`가 투영을 다시 계산하고, 포인트 /3이면 투영을 반드시 요구한다.
  - `quality_reasons`를 `without_retired` 은행으로 잰다(cloze 오탐 수정).
- `connection_generate_v2`
  - 중요도표를 입력에 넣는다(`importanceTable`, 원본 대조에는 `targetImportance`도).
  - point_ids 누락을 보완 사유로 만든다.
  - 조립 때 투영하고 manifest에 `importanceProjection`을 남긴다.
- 지시문
  - author-v2: point_ids, 표 값 옮기기, 제외 포인트는 채점 문항으로 만들지 않기
  - source-v2: target_checks로 근거 확인
- 실행 스크립트 `run.py`·`run-all.sh`(26110803, Map은 26110802의 완료본을 복사).

검사
- 새 검사: 배점 26(관리자 판정 그대로)·투영 파이프라인 3(계산·변조 거절·point_ids 보완과 대체·옛 형식 유지)
- 루트 `pytest tests` 2,169 통과(제외 1: `test_desktop_control` 바로가기, master 동일)
- `map_numbers --check` 정상
- 서버(격리 sqlite, `.env` 없음): bank 33 · root_ 25 · route_contract · retention 통과

## 배포 대상 버전·순서·데이터 변경
- master 병합 → 검사 → API → Pages 자동 배포. server/에는 별칭 파일 하나뿐이고 web/ 변경은 없다.
- API는 3.3 은행을 받을 수 있게 된다. 3.2 이하 은행·운영 Quiz Bank·학습 기록·DB 스키마는 바뀌지 않는다.
- Study Engine 정책표는 이미 importance 1–5를 가진다.

## 배포 후 확인·롤백·필요한 사람 승인
- 배포 영수증과 API health SHA를 확인한다. 롤백은 병합 되돌리기다.
- 감염병리1 재실행은 사용자 「고친 뒤 다시」 요청 범위다(S1·S2를 Codex gpt-6.1-sol로).
- 운영 등록·학생 공개·기존 98문항 판 교체는 별도 승인이다.

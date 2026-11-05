# 기존 Must-Know 등급 별칭의 Native 전송 복구 — 구현 계획

## 변경 범위·대상 파일·순서
authored_json.py의 기존 inline 대응을 canonical_tier로 공용화한다. generation_v2.py에 AUTHOR 별칭 projection 및 명시 형식 복구 증명 검증을 추가한다. root_native_json.py는 실제 provider JSON 원문을 보존하고 정규화/영수증을 검증하며 기존 authoring recovery의 실행 지문 연결을 보존한다. root_tier_recovery.py는 완료 파일만 검증해 보완/사용량을 재사용하고 같은 ledger에서 후속 검수로 이어간다. connection_generate_v2.py는 형식 복구 증명과 원래 authoring recovery를 최종 manifest에 연결한다. 관련 계약/Native/복구 회귀를 추가한다.

## 검사 명령과 성공 조건
tier-contract: 단일 canonical alias와 unknown tier 거절, 원문/의미/중요도 불변, 실제 파일·완료 영수증·단계 지문·실패/소비 보존 및 변조/반복/거절 방어. tier-regression: 기존 contracts/생성/Native/authoring 복구, API v2·보존. live-tier-recovery: 심내막염 실제 마지막 완료 파일의 정해진 별칭 한 곳만 변환하고 모델0회/소비3 유지·최종 원본/정답검수를 확인한다.

## 위험·복원·승인할 범위
현재 승인된 완료 작성 복구의 기계적 형식 변환 범위로 진행한다. 기존 inline 규칙의 재사용이며 의학/중요도 판정은 추가하지 않는다. CNS 실행 소스는 수정하지 않는다. 실행 지문을 새 명시 증명으로 연결하고 원래 실패/파일/모델 호출/보완 예산을 보존한다. 운영배포·기존은행 교체·기록 승계 없음. 복원해도 실제 소비나 과거 실패를 지우지 않는다.

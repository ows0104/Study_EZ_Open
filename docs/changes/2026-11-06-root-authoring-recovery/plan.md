# 완료 작성 초안의 구조 실패를 기존 보완 예산으로 복구 — 구현 계획

## 변경 범위·대상 파일·순서
quizbank/connection_authoring_recovery.py에 입력·완료 파일 영수증·출처·실패상태의 명시적 복구 준비 명령을 작성한다. connection_generate_v2.py는 증명 있는 failed generate를 다시 호출하지 않고 다음 repair-1에서 brief 구조만 보완한 뒤 원본/정답검수를 이어간다. studyez_contracts/roots/generation_v2.py는 원래 실패/소비를 연결한 복구 증명과 실제 단계 집합·개정 계보를 검증한다. runner/root_native_json.py는 해당 repair-1의 문항 보존/brief 전체 수용과 실패 Native 파일 영수증을 재검증한다. 기존 입력·검수·미준비/내용 판정 기준은 완화하지 않는다.

## 검사 명령과 성공 조건
recovery-contract: 실제 파일을 사용하는 합성 성공/변조/중단/거절/예산/재복구 거절 및 전체 원본·정답검수 누락 거절. pipeline-regression: contracts, generation v2, connection_generate 및 root_native_json 관련 회귀. live-recovery: 심내막염 이전 입력/작성 원문 SHA·실패·예산 보존, 실제 복구 보완·원본/정답검수 결과 검증. 서버 공용 결과 검증과 원래 비복구 경로를 함께 확인한다.

## 위험·복원·승인할 범위
현재 사용자의 구체 구현 승인을 본 파일 범위에 적용한다. 별도 브랜치/대시보드 점유를 마쳤다. CNS 실행 코드와 기존 자료는 읽기 전용이다. 실제 복구는 수정 및 검사가 끝난 뒤 승인된 같은47문항/원본/포인트와 잔여 예산으로만 진행한다. 운영배포/공개/548 재개는 하지 않는다. 복원은 코드 변경만 되돌리며 원래 실패·복구 증명·추가 모델 호출과 소비는 보존한다.

같은 E2E 실험에서 CNS의 완료 보완도 구조 수용 실패로 종료됨을 확인했다. 복구 기능은 실제 강의 경계(label/included/excluded)는 보존하고 검토 설명(reviewed/limitations/outside_list_review)의 근거 있는 교정을 구분한다. CNS는 새 모델 호출 없이 실제 완료 원문을 현행 전체 계약으로 재검증하는 수용 복구, 심내막염은 남은 예산을 쓰는 구조 보완 복구로 구분한다. 사용자에게 이 동일 기능의 구체 실패 두 유형과 처리 방향을 알렸으며 별도 실행 공간에서만 구현한다.

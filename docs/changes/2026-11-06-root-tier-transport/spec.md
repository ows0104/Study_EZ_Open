# 기존 Must-Know 등급 별칭의 Native 전송 복구 — 설계

## 요구사항과 수용 기준
공용 함수로 기존 Must-Know→Essential 대응을 중앙화한다. Native AUTHOR의 BANK.questions[].tier만 이 대응으로 정규화한다. importance 수치·tier 이외 모든 값과 순서는 보존한다. 원본 파일 바이트 SHA와 정규화한 객체 hash·실제 변경 question_id를 별도 projection 증명으로 연결한다.

## 책임·입출력 계약·오류 상태
이미 완료된 Native 파일이 이 별칭 때문에만 수용 실패한 경우의 명시적 운영자 복구를 추가한다. 원래 모델을 재호출하지 않고 provider receipt/실제 파일/전체 계약/그림/원본을 검증한다. 원래 failed ledger 및 failed Native journal을 별도 바이트 사본과 증명에 유지한다. 현재 예산3회를 그대로 적용하고 다음 원본·독립 정답 검수는 필수다. 이전 authoring recovery의 실행 지문은 새 형식 복구 증명을 통해 이어지며 바꿔 쓰지 않는다.

## 호환성과 데이터 보존
기존 projection 없는 결과를 계속 수용한다. 별칭 수용에는 해당 projection이 반드시 일치해야 한다. unknown tier/내용 변경/가짜 완료/변조/반복 복구/모델거절은 거절한다. API 순수 계약도 원문→정규화의 정확한 관계·실패와 이전 복구 보존·예산을 재검증한다. CNS의 이전 실행 지문·결과는 별도로 보존하고 최신 순수 검증이 읽을 수 있어야 한다.

실제 재개에서 cached source audit의 파생 coverage.reason 설명 구절만 set 순회로 순서가 달라져 잘못된 추가 수정 사유가 생김을 확인했다. 향후 파생 설명을 정렬하고 기존 결과는 coverage.reason의 동일 구절/중복 개수를 순서 독립 비교한다. 원본 assessment의 판정·이유와 coverage 상태/방향/근거 등 나머지 필드는 정확히 같아야 한다. 캐시 파일·입력 hash는 바꾸지 않는다. 모든 캐시와 실제 원본·Native 영수증·raw assessment를 재검증한 명시 runtime revalidation 증명으로만 새 코드 지문을 연결한다. 모델0회·기존3회 소비 및 이전 복구 증명은 그대로 유지한다.

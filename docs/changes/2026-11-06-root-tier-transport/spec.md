# 기존 Must-Know 등급 별칭의 Native 전송 복구 — 설계

## 요구사항과 수용 기준
공용 함수로 기존 Must-Know→Essential 대응을 중앙화한다. Native AUTHOR의 BANK.questions[].tier만 이 대응으로 정규화한다. importance 수치·tier 이외 모든 값과 순서는 보존한다. 원본 파일 바이트 SHA와 정규화한 객체 hash·실제 변경 question_id를 별도 projection 증명으로 연결한다.

## 책임·입출력 계약·오류 상태
이미 완료된 Native 파일이 이 별칭 때문에만 수용 실패한 경우의 명시적 운영자 복구를 추가한다. 원래 모델을 재호출하지 않고 provider receipt/실제 파일/전체 계약/그림/원본을 검증한다. 원래 failed ledger 및 failed Native journal을 별도 바이트 사본과 증명에 유지한다. 현재 예산3회를 그대로 적용하고 다음 원본·독립 정답 검수는 필수다. 이전 authoring recovery의 실행 지문은 새 형식 복구 증명을 통해 이어지며 바꿔 쓰지 않는다.

## 호환성과 데이터 보존
기존 projection 없는 결과를 계속 수용한다. 별칭 수용에는 해당 projection이 반드시 일치해야 한다. unknown tier/내용 변경/가짜 완료/변조/반복 복구/모델거절은 거절한다. API 순수 계약도 원문→정규화의 정확한 관계·실패와 이전 복구 보존·예산을 재검증한다. CNS의 이전 실행 지문·결과는 별도로 보존하고 최신 순수 검증이 읽을 수 있어야 한다.

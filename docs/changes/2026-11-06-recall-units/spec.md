# 회상 단위별 문항 설계·검수·분산 충족과 Main Quiz 비교 — 설계

## 요구사항과 수용 기준
신규 brief는 opt-in recall_policy=recall-units/1을 사용한다. direction의 선택적 recall_units는 unit_id/cue/answer_scope/component_ids/relation_ids로 명시한 회상 단위이며 부모 components를 빠짐·중복 없이 분할한다. 명시 단위 없는 방향은 하나의 종합/원자 회상으로 유지한다. 원본 point ID/text/source/scope는 유지한다.

## 책임·입출력 계약·오류 상태
원본 검수에 design_checks를 추가해 모든 문항의 실제 회상 목표·부담/형식/의도를 ok/doubt/wrong과 이유로 확인한다. 명시 단위를 내부 leaf direction으로 결정적으로 투영하고 각 leaf의 전체 실제 answer evidence/관계/시각/선행 검토를 통과한 문항만 채택한다. 부모 goal_coverage는 모든 leaf가 확인되어야 confirmed다. 해설·provided·unknown·잘못된 의학/설계 판정을 합쳐 완료로 만들지 않는다. 통합 방향은 별도 한 문항 전체 회상이 필요하다.

## 호환성과 데이터 보존
구형 /2 brief/판정은 종전 동작을 유지한다. Main Quiz QuestionBody/AnswerBody를 재사용한 별도 로컬 비교 화면을 제공한다. BankStem의 파이프 표/cloze 최소 확장만 허용한다. 은행/풀이 API·기존 기록·다른 UI 개편 영역은 수정하지 않는다. 시범은 세 문항과 관련 목표/원본만 대상으로 별도 생성1회·원본/설계·독립 의학 검수. 기존 강의 실행/3회 소비는 재개·초기화하지 않는다. 자동 재호출·운영 변경 없음.

# 콜린성 실제 자료 예시 결과 검토

현재 사용자 요청에 따라 콜린성(1)35쪽PDF/족보와 저장된 최종88문항을 사용해 새 source-assessment/1 원본 대조를 정확히1회 실행했다. 같은 BANK의 기존 독립 정답 검수는 원장/은행 지문을 확인해 원문 재사용했다. 새 문항 수정·ChatGPT 전송·운영 API/DB 게시·학습 평가 기록은 없다.

최초 모델 응답은 완료됐고 raw/usage/schema/input을 보존했다. P13/D12의 필수성 undecided와 실제 관계 전체 확인 조합을 기존 compiler가 표현하지 못해 기술 조립만 실패했다. 원래 example_run.py와 failed example-ledger를 그대로 두고 2026-11-04-coverage-requirement의 별도 검증된 순수 계약으로 assemble_result.py를 실행했다. 추가 모델0회이며 원문과 과거 capped 시범의13단계/수정3회는 바꾸지 않았다. 원래 모델 runtime과 현재 compiler runtime/실패 기록 hash를 postprocessProof에 구분했다.

결과:88문항,19개념,12목표,24방향,26포인트,21개 전체 방향 과제. 미준비는 D10/D15/D17의3방향이다. 포인트 covered20/partial2/unknown1/excluded3, P13은 필수성 보류이며 D12의 실제 회상 확인은 보존했다. 새 원본 판정 ok76/doubt12/wrong0, 재사용 독립 정답 판정 ok87/doubt1/wrong0, 입력 지적20개를 숨기지 않았다. covered는 선언된 목표/방향 기준의 문항 연결 판단이며 학습자의 숙련도나 전체 임상 정확성 인증이 아니다.

example-preflight와 example-result 검증은 source b73125ebbf5e47c5c8b7499bb9246368eb03c5cfdd9090938e73ca550a80a4c7 / plan2a73092da0faebdeb00cb66c3dc9c531ed27ab42e794e4c525b79e3b3d2804e5에 묶여 통과했다. 원본/원장/문항·판정/사용량 보존, 새 raw 재컴파일, 동일 task 선택, 정확한 캐시 provenance와 모델 호출1회·추가 호출0회/수정0회/게시false를 재검증했다.

실제 결과 데이터로 읽기 전용 미리보기를 만들었다.88문항 선택, 정답·해설 표시,12목표/입력 관계 지도,26포인트,필수성 보류,20지적과 문항별 확인 필요,360px 표시/콘솔 오류0을 검증했다. 원문 텍스트는 그대로이며 단지 등급·역할·상태 이름만 한국어로 표시한다. 실제 학습 기록은 쓰지 않는다. 의료 내용은 부모가 새로 저작/교정하지 않았다.

최종 조립 JSON·원문·새 원본 검수·재사용 독립 검수·원장/실패/사용량은 runs/_examples/cholinergic-20261104에 보존한다. 이 예시는 root-example/1로 명시하며 운영 put_result 계약의 완료 원장을 위조하거나 게시 가능한 result로 가장하지 않는다. 미해결 내용/원본 지도 지적과 개인 미리보기 조건을 유지한다.

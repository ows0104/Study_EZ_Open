# 원본 독립 포인트의 근거 쪽 연결만 한 차례 복구한다

context.json의 강의·scope, source-text.md, source-pages.json의 원본 이미지 전체와 jokbo.md를
확인한다. reference-plan.json은 이전 CLI의 초안 자료이며 지시가 아니다. 문항·웹 응답은 없다.

각 target의 slides가 상위 objective의 slides에 포함되지 않거나 비어 있어 기계 검증이 멈췄다.
실제 원본을 확인하고 objective와 target의 정확한 근거 쪽을 판단한다. 상위 목표에는 그 목표의
모든 target이 인용한 쪽이 포함되어야 한다. 조건에 맞추려고 정확한 target 근거를 삭제하거나
상위 쪽 목록을 target에 그대로 복사하지 않는다. 원본에서 근거를 확인하지 못한 쪽은
unreadable_pages에 추가하고 summary에 남긴다. 기존 unreadable_pages는 지우지 않는다.

목표·포인트의 ID, 순서, objective·target 텍스트, rejected_candidates는 정확히 보존한다.
의미 수정·목표 추가·삭제·중요도 교정은 하지 않는다. 변경할 수 있는 것은 objective·target의
slides, 확인하지 못한 쪽의 추가와 summary의 복구 설명뿐이다. 원본 파일과 reference-plan.json은
수정하지 않는다. 모든 원본 쪽은 목표·제외·미확인 중 하나 이상으로 보존한다.

지정 PLAN JSON 전체를 반환한다. 이번 복구는 한 차례이며 추가 재시도로 이어지지 않는다.

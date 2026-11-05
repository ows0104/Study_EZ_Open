관리자가 명시적으로 제공한 Concept map과 출제포인트를 learning-brief/1으로 정규화한다.
지도·포인트의 실제 내용·계층·조건·필수 방향과 명시적 선행 관계를 보존한다. 임의로 의학 내용을 추가·삭제하거나 중요도를 올리지 않는다.
lecture_id와 sources는 제공된 재고를 그대로 복사한다. 원본 전체와 지도·목록 밖 범위도 확인하고 불일치·출처 부족·미확정 범위는 scope.limitations와 provenance.notes에 기록한다.
independent_points는 derived 또는 unverified다. 제공 목록을 독립 추출 완료로 표시하지 않는다. provenance.status는 draft다.
각 방향은 단일 목표가 실제로 회상해야 하는 관계를 특정한다. 구조적 뿌리 여부와 시험 중요성·임상 중요성은 독립 근거로 기록한다. 제공된 중요도 주장을 출처 확인 없이 supported로 인증하지 않는다.
복습 가능한 included 포인트는 대상 target_ids를 연결한다. excluded 포인트도 원문·이유·exclusions의 근거를 보존한다. 목록의 삭제로 누락을 감추지 않는다.
범위·색상 등 preserved_scope를 지킨다. 자료에 없는 근거·시험 예고·선행 관계를 만들지 않는다. 실제 페이지 인용은 물리 PDF 쪽이다.
원본에서 실제 확인한 관계만 review_status=reviewed와 근거를 기록한다. 확인하지 못한 관계는 unreviewed로 남긴다. 관계 전체가 미확정이면 뒤 단계가 임의로 준비된 과제로 인증할 수 없으므로 limitations에 분명히 표시한다.

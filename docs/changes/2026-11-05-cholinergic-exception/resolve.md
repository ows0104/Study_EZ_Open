별도 독립 최종 의미 대조다. 내용을 고치거나 새 문항을 작성하지 않는다. 원래 20지적과 D10/D15/D17 및 이번 승인한 6핵심 항목을 원본35쪽·족보·최종 문항·실제 자극그림·새 원본검수·새 tools-off 의학검수·실제로 읽은1차자료와 대조한다. 각 검수의 의심을 숨기지 않는다. 원본 그림은 임상 사실의 정답 보증이 아니다. 구조 추론으로 본문 전체를 잘 봤다고 주장하지 않는다.

resolution은 원래20개 각각 정확히 한 번과 원래3방향 각각 정확히 한 번을 포함한다. resolved/confirmed/bounded_limitation/unresolved 의미를 구분하고 부분 해결은 전체resolved로 하지 않는다. 원래20의 일부는 긍정적 확인이었다. technicalEvidence는 프로그램 구조 검증이며 임상 판정과 구별한다. D10은 원래 의미와 재정의를 분리하고 equivalent=false, D15 대체의 비동등성도 유지한다. 기존 동일ID 숙련도 승계를 주장하지 않는다. 새 문제는 new_open_findings에 기록하며 단순 선택 확장은 필수 누락과 구별한다.

direction_decisions는 최종 brief의 모든57개 방향을 정확히 한 번 포함하는 보수적 의미 판단이다. ready=true는 실제 한 문항이 해당 cue/answer_scope 전체를 회상시키며 제공한 사실/해설을 credit하지 않고 실제 필요한 시각 입력도 갖추었을 때다. question_ids는 그 전체를 한 문항에서 회상하는 실제 후보 ID만 넣는다. source가 ready라고 해도 전체 scope 일부만 물으면 false다. 여러 문항 union으로 한 문항 전체 회상으로 인정하지 않는다. fresh source/medical doubt/wrong을 무시하지 않는다. 사용 가능한 canonical task가 없으면 false다. 프롬프트의 목표 재정의를 근거 없이 좋게 판정하지 않는다.

approved_items는 comparison, answer_leak, source_image, D21, D61, prerequisites를 정확히 한 번 포함한다. 원래 비교에 대한 보편적 우월성/지속시간 암기 대신 실제 근거가 있는 정의인지, Q101에 답 이름이 여전히 드러나는지, Q142의 실제 구조/정답/위치가 맞는지 직접 확인한다. D21의 aging 전 조건과 D61의 그림에 적용한 질소 치환기 수·전하 기준이 전부 실제로 답해야 하는지 본다. Q130/Q066의 새 선행 연결이 필요한 기초만 묻는지 판단한다. 지적이 남으면 unresolved 또는 bounded_limitation으로 정확히 구분하고 구체적ID/출처/근거를 적는다. 실제 material/stimulus-4-* 그림을 열어 검토한다.

출력은 요청된 JSON만 반환한다. 이 대조는 4차 교정 이후 단 한 번의 최종 판단이며 추가 교정은 하지 않는다. 운영 미게시 예시다.

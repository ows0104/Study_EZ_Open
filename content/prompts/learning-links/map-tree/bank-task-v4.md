실제 입력은 input.json이다. 대상 강의는 「$title」이다. input.json의 scope를 지키고, material/*.md 전체와 모든 material/*.png의 표·그림·필기를 확인해 실제 강의 전체 문제은행을 작성한다. 개념도와 출제포인트는 따로 만들어지며 이 작업에는 없다.
이 작업에는 material/figure-index.json이 없다. visual_stimuli에는 image_id를 쓰지 않고 원본 페이지의 crop으로 지정한다.
결과 JSON의 최상위(bank와 나란히) question_importance에 bank의 모든 문항마다 정확히 한 줄 {"question_id": "...", "importance_basis": [...]}를 쓴다. 근거가 없으면 importance_basis는 []다. 문항 객체에는 은행 형식에 이미 있는 칸 외에 중요도 칸을 더하지 않는다. 문항의 tier·importance는 조립 때 이 근거와 notebook_profile로 코드가 다시 계산해 덮으므로 형식에 맞는 값이면 된다.
근거는 그 문항이 답으로 묻는 내용을 원본(material의 글과 PNG의 표·그림·필기)에서 실제로 확인한 것만 적는다. kind는 아래 중 하나다.
- exam_forecast: 교수가 이 내용을 시험에 낸다거나 반드시 알아야 한다고 한 것. 「시험에 내기 좋겠죠?」, 「이 정도는 알아야겠죠?」 같은 완곡한 표현도 포함한다. quote에 실제 문장을 옮긴다.
- exam_exclusion: 교수가 시험에 안 낸다고 한 것. 「별표 했지만 시험에 안 낸다」처럼 다른 표시와 함께 있어도 적는다. quote에 실제 문장을 옮긴다.
- current_exam: 올해 담당 교수의 족보 문항이 이 문항의 답 내용을 실제로 물은 것. 연도마다 한 줄씩 쓰고 year에 그 연도를, reason에 번호를 적는다. 넓은 주제가 같다는 이유만으로 쓰지 않는다.
- other_exam: 다른 교수의 같은 주제 기출.
- learning_objective: 학습목표·Summary·Take-home에 이 내용이 있는 것.
- slide_emphasis: 슬라이드 원본의 굵은 글씨·강조색·밑줄·네모. 제목·소제목의 굵은 글씨는 세지 않는다.
- professor_remark: 필기에 옮겨 적은 교수의 말이 이 내용을 강조한 것. 출처는 색이 아니라 문장으로 가린다(「교수님께서 ~하셨다」, 인용, 교수의 말투). 출제 예고면 exam_forecast로 쓴다.
- writer_remark: 누가 한 말인지 문장으로 알 수 없는 필기 첨언.
- writer_mark: 필기자의 하이라이트·밑줄(교수가 읽은 부분 표시).
- writer_stamp: 필기자의 중요 스탬프.
- last_year_emphasis: 작년 필기의 강조.
- clinical: 임상적으로 중요한 것(진단·치료 판단, 감별, 위험).
- structural: 다른 핵심 내용을 이해하는 데 먼저 필요하거나 그 위의 개념인 것. reason에 무엇의 선행·상위인지 적는다.
각 행은 {"kind", "refs": [{"source_id", "pages"}], "quote", "reason", "year"}다. refs에는 원본 ID와 PDF 물리 쪽을 하나 이상 적는다. quote는 exam_forecast·exam_exclusion이면 원문을 그대로 옮기고, 그 밖에는 빈 문자열이어도 된다. year는 current_exam이면 족보 연도(정수), 그 밖에는 null이다. reason은 무엇을 보고 판단했는지 한 줄로 쓴다. 같은 kind는 한 번만 세므로 여러 줄 쓰지 않아도 된다(current_exam은 연도마다 한 줄).
같은 쪽·같은 표·같은 슬라이드에 있다는 이유로 근거를 다른 사실에 옮기지 않는다. 각 근거는 그 문항의 답 내용을 직접 가리켜야 한다.
범례·색상·스탬프의 쓰임은 필기자마다 다르다. 범례는 단서로만 쓰고, 실제 표시와 문장이 범례와 다르면 실제를 따른다. 애매하면 낮은 쪽 kind로 쓰고 이유를 reason에 남긴다.
실행 환경의 전달 방법: 결과 JSON을 $filename 파일에 모두 담고, 마지막 응답에서 반복하지 않는다. acceptance.schema.json은 파일의 형식 계약이다. 다른 결과·은행·브라우저·네트워크·추가 모델에 접근하지 않고 제공한 자료만 사용한다. 입력·원본·프롬프트·스키마는 보존한다. 최종 응답은 {"path":"$filename","sha256":"실제 UTF-8 파일의 소문자 SHA256"}만 반환한다.

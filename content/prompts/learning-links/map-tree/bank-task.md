실제 입력은 input.json이다. 대상 강의는 「$title」이다. input.json의 scope를 지키고, material/*.md 전체와 모든 material/*.png의 표·그림·필기를 확인해 실제 강의 전체 문제은행을 작성한다. 개념도와 출제포인트는 따로 만들어지며 이 작업에는 없다.
이 작업에는 material/figure-index.json이 없다. visual_stimuli에는 image_id를 쓰지 않고 원본 페이지의 crop으로 지정한다.
실행 환경의 전달 방법: 결과 JSON을 $filename 파일에 모두 담고, 마지막 응답에서 반복하지 않는다. acceptance.schema.json은 파일의 형식 계약이다. 다른 결과·은행·브라우저·네트워크·추가 모델에 접근하지 않고 제공한 자료만 사용한다. 입력·원본·프롬프트·스키마는 보존한다. 최종 응답은 {"path":"$filename","sha256":"실제 UTF-8 파일의 소문자 SHA256"}만 반환한다.

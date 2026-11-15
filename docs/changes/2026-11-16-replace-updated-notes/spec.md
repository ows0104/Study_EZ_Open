# Main-Quiz 재배치가 바뀐 필기(같은 쪽 수)를 이어받기 — 설계

## 요구사항과 수용 기준
- R1 입력 비교(`connection_replace`): 강의 입력이 다르면 지금처럼 멈추되, 다른 것이 **원본 파일 자체**뿐이고
  (같은 source id·kind·순서, 원본 수 같음) 바뀐 원본마다 PDF 쪽 수가 같으면 「필기 교체」로 받는다. 그 밖의 차이(제목·범위·시험일 등)는 계속 멈춤.
- R2 바뀐 쪽 계산: 원본마다 쪽별 텍스트와 저해상도 렌더를 비교해 `changedPages`를 구한다. 그 쪽을 `source_refs`·`learning_page`·근거 쪽으로
  쓰는 문항 목록(`questionsOnChangedPages`)을 만든다. 결과 manifest에 `sourceUpdate: {sources: [{source_id, fromSha256, toSha256, pageCount,
  changedPages}], questionsOnChangedPages}`로 기록하고 진행 로그에 출력한다. 바뀐 쪽 0개면(다시 올린 같은 파일) 그대로 받는다.
- R3 원본 교체: brief·`material/`·모든 판정은 이전 파일 그대로 둔다 — 러너가 단계 영수증을 그 검사 스키마·입력·쪽 그림 지문으로 다시
  검증하므로(`root_native_json.validate_stage`), 원본 스키마에 칸을 더하거나 쪽 그림을 다시 그리면 이 편뿐 아니라 이미 만든 모든 실행의
  영수증이 떨어진다(구현 중 실측으로 확인). 공개 문서에서만 `review.sources`의 그 원본 이름·sha256을 새 파일로 바꾸고(답면 근거 쪽이 새 필기로
  보인다), 문서 최상위 선택 칸 `replaced_sources: [{source_id, sha256}]`에 대신한 이전 파일을 적는다. 문항·지문 그림·검토·의학 검토는 그대로 —
  그림은 이전 파일에서 자른 것이고 그 sha를 유지한다(바꾸면 문항 지문이 바뀌어 학습 기록이 끊긴다).
- R4 결과 검사: 계약 `roots/generation_v4.apply_source_update`가 교체를 하고(기록의 fromSha256 = brief 원본, toSha256 = packet 원본, 필기 PDF만),
  `_judgments4`가 재배치 기록의 `sourceUpdate`로 같은 교체를 다시 조립한 문서에 적용해 대조한다. `roots/validate.validate_document`는
  `replaced_sources`를 받고, 지문 그림 검사(`roots/media.validate_images`)는 원본 sha 또는 그 원본이 대신한 이전 sha를 받는다.
  기록은 manifest `unplacedOnly.sourceUpdate`. 서버는 계약을 import하므로 병합(API 배포) 뒤에 이 문서를 받는다.
- R5 학습 기록: 기록을 잇는 지문(`question_fingerprint`)은 문항 내용만 쓰고 원본 sha·bank 맥락을 넣지 않는다(확인함) — 같은 문항은 그대로 잇는다.
- R6 바뀐 쪽을 근거로 한 원본 충돌 기록(`source_conflicts`, 예: 261112_03 CF01 「p.17 주석 O vs 족보 정답」)도 `questionsOnChangedPages`처럼
  `conflictsOnChangedPages`로 적는다. 충돌 기록 자체는 고치지 않는다(문항과 같은 원칙).
- 수용: 테스트 — 같은 쪽 수의 교체는 받아 원본만 바뀐 문서·바뀐 쪽 기록, 쪽 수 다르면 멈춤, 원본 밖 입력 차이는 멈춤, 결과 검사 통과,
  carry 링크가 같은 수. 실측 — 261112_03 운영 데이터로 로컬 재생(쓰기 없음): 바뀐 쪽 = {1, 7, 17, 29}, 이을 과제 수 = 이전 판 과제 수.

## 책임·입출력 계약·오류 상태
- 생성기 `quizbank/connection_replace.py`, 새 `quizbank/source_update.py`, 계약 `roots/generation_v4.py`·`roots/validate.py`·`roots/media.py`.
- 러너: `duplicates_front`가 요청 packet으로 derived packet을 다시 만들므로 원본은 이미 새 것 — 변경 없음 예상(확인). 서버: 요청 경로 변경 없음
  예상(원본은 요청 시점 `assets_now`). 관리자 결과 화면에 `sourceUpdate` 표시는 있으면 좋음(선택).
- 오류: 쪽 수 다름·원본 수/종류 다름 → 「필기 쪽 구성이 바뀌어 재배치로 이을 수 없습니다 — 처음부터 출제」.

## 호환성과 데이터 보존
이전 판·실행 폴더·이벤트 불변. `sourceUpdate`가 없는 재배치 결과는 지금과 같다. DB 스키마 변경 없음. 러너 재설치 필요(생성기·계약).

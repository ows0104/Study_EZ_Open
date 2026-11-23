# Main-Quiz 강의 문항 전체 보기 — 설계

## 요구사항과 수용 기준
- R1 `GET /api/root-learning/lectures/{subject}/{run_id}/questions`: 활성 판의 문항 전체를 판 문서 순서로.
  각 행: `question`(content.front와 같은 허용 목록, 그림 바이트 없음 — `figures` 개수만), `answer`(content.answer),
  `pages`(강의록·족보 쪽 번호: `source_refs`의 pages/locator와 `stimuli`의 page), `planned`(학습 과제가 있는 문항).
  개인 수정본·내 중요도가 반영된다. 그림 바이트·R2 서명·근거 asset을 읽지 않는다(가벼운 사본만).
- R2 `GET …/questions/{question_id}/detail`: 그 문항 하나의 풀이 화면과 같은 앞면(그림 포함)·답면(pdfSlides·족보·검토 기록·메모).
  화면에서 「참고 쪽」을 누를 때만 부른다.
- R3 두 API 모두 읽기 전용: root_event·세션·개인 수정 표에 쓰지 않는다.
- R4 권한은 풀이와 같다(`active()` — 공개 범위의 학습자). 다른 강의·없는 문항은 404.
- R5 화면 `/bank/:subject/:runId/roots/questions`: 검색·형식·중요도·내 수정본 거르기, 정답 보이기/가리기,
  참고 쪽 버튼(누르면 R2를 읽어 슬라이드를 그린다), 「수정·제보」(PersonalQuestionDialog), 「내 중요도」 선택(PUT …/tier).
  Main-Quiz 시작 화면에 「전체 문항」 링크.

## 책임·입출력 계약·오류 상태
- 서버: `server/app/root_learning/question_list.py`(행 만들기), `routes/root_learning.py` 끝에 두 경로.
- 쪽 번호: `{sourceId, page, exam}` — exam은 판의 review.sources에서 kind == 'exam'. 범위 밖 쪽(page_count 초과·1 미만)은 뺀다.
- 오류: 공개 안 됨 404, 문항 없음 404. 화면은 목록 실패 시 다시 불러오기, 상세 실패 시 그 행에서 다시 시도.

## 호환성과 데이터 보존
- DB 스키마·프롬프트·판 문서 변경 없음. 기존 API의 응답은 그대로다.
- 편집은 기존 개인 수정·내 중요도 API를 그대로 부른다(기록 방식 동일: bank_personal_edit·bank_feedback·root_event kind='tier').

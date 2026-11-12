# Main-Quiz 미리 받기: 검수 메모를 판마다 한 번 — 설계

## 요구사항과 수용 기준
- `routes.root_learning.active_generation`: 언제나 `defer(result)`, `defer(web_response)`(`light` 인자는 호환용).
- 새 `app/root_learning/review_notes.py`: `extract(result) -> {notes, issues}`(교체·큐레이션 판은 `replacement_import.report`,
  그 밖은 원본 대조·의학/독립 정답 검수의 ok 아닌 리뷰와 입력·검증 이슈), `for_generation(db, generation)`(LRU 64, 읽기 잠금).
- `revealed_answer`: `notes`를 문항 ID로 거르고 `question_issues(issues, qid)` — 예전 식과 같은 순서·값.

## 책임·입출력 계약·오류 상태
API 응답 모양 그대로. result가 없으면 빈 메모. 캐시 키에 result_digest가 있어 기록이 바뀌면 다시 뽑는다(기록은 넣기만 한다).

## 호환성과 데이터 보존
읽기만 바뀐다. 출제 기록·학습 기록 변경 없음.

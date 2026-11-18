# Main-Quiz 복습 간격: 쉬운 문항이 곡선대로 빠지게 — 배포 준비

## 코드 리뷰·검증 결과

- 새 `server/tests/test_root_review_curve.py`: spec 표의 출제일(첫 30일)과 정확히 같다. /2 파라미터 그 자체의 계산(예전 날짜)도 고정해 비교한다.
- 기존 검사 수정: /2로 표시한 사건을 쓰는 `test_root_score`·`test_root_tier`는 /2 파라미터를 저장한 사건으로 두고(R3로 /3 규칙에 읽힘),
  `test_root_score`의 「보이는 값 > 계획 값」은 Good 한 번이 이제 목표치를 넘으므로 Hard 한 번으로 확인한다.
  `test_root_tier`·`test_main_quiz_four_ratings`는 저장 정책 `/3`, 도움 뒤 Good → independent(R2)로 바꿨다.
  `test_root_question_progress`의 도움 받은 Good은 「인지」 대신 「인출」.
- 서버 전체 검사(`server/`에서 메인 체크아웃 venv, `PYTHONPATH=..`, 각 검사의 격리 sqlite): 158/160 통과.
  실패 2개(`test_root_map_tree`, `test_root_map_tree_v3`)는 서버 venv에 `fitz`/`pymupdf`가 없는 환경 문제로 이번 변경과 무관.
- R3(지난 /2 평가 다시 읽기): `test_root_review_curve`가 `replay_parameters`를, `test_root_score`·`test_root_tier`가 /2 사건 재생을 확인.
- 미확인: 운영 기록으로 재생한 실제 강의(콜레라)의 오늘 복습 수 변화.

## 배포 대상 버전·순서·데이터 변경

- 서버만. DB·API 형식 변경 없음. 새 평가 사건 payload의 `ratingPolicy`가 `roots-four-rating/3`, `targetParameters`에 두 키 추가.

## 배포 후 확인·롤백·필요한 사람 승인

- master 병합 = 자동 배포. 병합은 사용자 확인 뒤.
- 확인: 새로 Easy를 누른 Core 문항의 다음 복습일이 4일 뒤인지(강의 화면 「오늘 추천」 수가 다음 날 줄어드는지).
- 롤백: `git revert`. 이미 저장된 /3 사건은 자기 파라미터로 재생된다(plan.md 참고).

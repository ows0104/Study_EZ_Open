# Main-Quiz 풀이 중 내 중요도 변경 — 배포 준비

## 코드 리뷰·검증 결과
- 서버: 새 `test_root_tier`(표시·멱등·409/422/404·세션/미리받기 반영·같은 시각 선택은 seq 순서·
  목표값이 Quiz Bank `target_for`와 전 경우 일치·간격이 `review_schedule`과 일치(5.19일→6)·30일 상한·
  Good 연속에서 Must-Know≤Core≤Important≤Optional·이전 사건 간격 불변·다른 판 무시·이용현황 5회),
  `test_main_quiz_four_ratings`(새 사건 roots-four-rating/2·targetParameters),
  `test_route_contract`(새 PUT 경로 1개), 서버 전체 `-m tests`(격리 SQLite, `PYTHONPATH`=이 worktree).
- 웹: typecheck·build 통과. `check_root_learning.py --check root-ui` 5/5(새 「내 중요도」 브라우저 검사 포함:
  선택 → 안내 → 다음 문항은 자기 중요도 → 저장 확인 뒤 새로고침에도 유지 → 원래대로).
- 화면: 문항 번호·진행 막대 줄 오른쪽에 「내 중요도 [선택] 목표 N% 원래대로」.

## 배포 대상 버전·순서·데이터 변경
- master 병합 → 검사 → Cloud Run API → Pages(자동). API가 먼저 올라가고 웹이 뒤따르므로 순서 문제 없음.
- DB 스키마 변경 없음. 새 데이터는 사용자가 고를 때 쌓이는 `root_event(kind='tier')` 행뿐이다.
- 기존 학습 기록·예정일은 바뀌지 않는다. 배포 뒤 새 평가부터 목표 기억률 간격이 적용된다(사용자 「새 평가부터 적용」).

## 배포 후 확인·롤백·필요한 사람 승인
- 확인: health revision SHA, 새 경로 `PUT …/questions/{id}/tier` 비로그인 401, openapi에 경로 존재, Pages 청크에 「내 문제 중요도」.
- 롤백: git revert → 자동 배포, 또는 이전 Cloud Run revision·Pages. 남은 `tier` 사건은 옛 코드가 읽지 않는다(예정일은 기본 계산으로 돌아감).
- 사람 승인: 「사람에게 묻는 것」에 해당 없음(스키마·학습 기록 변경·새 공개 범위 없음). 사용자 요청이 근거.

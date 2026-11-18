# 선행 문항 포함/미포함 선택 — 배포 준비

## 코드 리뷰·검증 결과
- 서버 전체(`server/`에서 `python -m tests`): 166개 중 164 통과. 실패 2개(test_root_map_tree, test_root_map_tree_v3)는
  검사 환경에 pymupdf가 없어 import에서 멈춘 것(ModuleNotFoundError). 이번 변경과 무관.
- 새 검사 `server/tests/test_root_prereq_toggle.py`: 계획(존재 연결·문항 선행·필터 안 선행·필터 없음 동일), 모아풀기 고르기
  (문항 선행·존재 연결·나중 제외·복습 대상 포함·연쇄·선행만으로 회차 없음), 경로(기본·저장·생략 시 유지·멱등·사용자 분리·회차 조건).
- 웹: typecheck·build 통과. 고정물 `web/tests/root-today-prereqs.html` 5개 확인 통과(브라우저).
- 모아풀기 시작 화면 체크는 실제 서버가 필요한 화면이라 띄우지 않았다(경로 검사·타입으로 확인).

## 배포 대상 버전·순서·데이터 변경
- 서버와 웹을 함께 배포. DB 표·열 변경 없음(root_event payload 키 `prereqs` 추가).
- 옛 웹은 `prereqs`를 보내지 않으므로 서버가 지난 선택을 유지한다. 순서 제약 없음.

## 배포 후 확인·롤백·필요한 사람 승인
- 확인: 강의 하나 오늘 추천에서 중요도를 좁히고 「선행 문항」을 끄면 카드 수가 줄거나 같고, Optional 선행이 나오지 않는다.
- 롤백: git revert, 이전 Cloud Run revision·Pages. 남은 `prereqs` 키는 옛 코드가 무시한다.
- 사람 승인: 해당 없음(되돌릴 수 있는 코드 배포, DB 스키마 변경 없음).

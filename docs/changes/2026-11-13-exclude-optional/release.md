# Optional 문항 계산 제외 토글 — 배포 준비

## 코드 리뷰·검증 결과
- 서버: 새 `test_root_optional_exclusion`(꺼짐=기존 값, 켜짐=Optional 제외, 내 중요도 반영, 전부 Optional이면 None,
  옛 문서는 방향 단위, 계획·focus·preparationProblems 불변, 계정 단위·멱등·다른 계정 무영향), `test_route_contract` 경로 추가.
  `-m tests root` 43개 중 41 통과, map_tree 2개는 로컬 PyMuPDF 미설치(설치 뒤 전체 재실행 결과는 state.json의 verify 기록).
- 웹: typecheck·build 통과.
- 브라우저(로컬 격리 DB `server/local_test_data/optional-check`, 합성 강의 1편·Q3 내 중요도 Optional·Q1 평가 1회):
  강의 목록 전체 3→2장·미열람 2→1·학습률 6→9%, 패널 같은 값, 끄면 즉시 원래 값, 캘린더 칸 9%·목표 0/2,
  Main-Quiz 시작 화면 학습 목표 2·Optional 칩 개수 1(불변). 운영 DB 미사용.
- 경계 확인: `available`·`planning.plan` 입력은 거르지 않음. 사용 현황 집계(`usage._root_field`)와 `events_for`는
  subject가 빈 `kind='optional'` 행을 읽지 않음.

## 배포 대상 버전·순서·데이터 변경
- DB 스키마·migration 없음. 새 데이터는 사용자가 토글을 누를 때 생기는 append-only `root_event` 행뿐.
- 일반 코드 자동 배포 경로(master 병합 → API → 같은 SHA 웹). 옛 웹은 새 API를 부르지 않아 꺼짐과 같다.

## 배포 후 확인·롤백·필요한 사람 승인
- 확인: `/api/health` SHA, 강의 목록에서 토글 켬/끔에 따라 학습률·카드 수 변화.
- 롤백: PR revert. 남은 `kind='optional'` 행은 다른 기능이 읽지 않는다.
- master 병합(=운영 배포)은 사용자 승인 후.

# Main-Quiz 선행: 끌어오기·막기는 문항 사이 선행만 — 배포 준비

## 코드 리뷰·검증 결과

- contracts `pytest tests/contracts` 416 통과. 새 검사: 목표 선행만으로 끌어오지 않음·고른 과제끼리 순서·문항 선행 끌어옴·
  평가한 선행 재출제 없음·준비 안 된 선행 건너뜀·판 작성/검증 호출 결과 불변.
- server `-m tests prereq_closure·root·main_quiz·route_contract`: master와 같은 결과. root 47 중 `test_root_map_tree`·`_v3` 2개 실패는
  로컬에 `pymupdf`가 없어서이며 master(382dd17b)에서도 같다. 나머지 전부 통과(격리 SQLite, 운영 DB 미사용).
- web `npm --prefix web run typecheck` 통과. 새 고정물 `web/tests/root-prerequisite-tag.html` 브라우저에서 ALL PASSED(4개), 화면 확인.
- 구현 중 결정(spec R1): 계획의 「명시적 선행 연결」(고른 중요도 안의 후보에서만 안 배운 앞 목표를 당겨 옴)은 남겼다.
  지우면 의도된 설계를 검사하는 11개가 실패하고, 신고 사례에서는 결과가 같았다. 사용자 확인(2026-11-16): 유지.
- 운영 사본 재현(읽기 전용 조회 → 로컬 계산, 2026-11-16): 판 `auto-2bcdcf1f…`
  - Essential만: 52과제(Essential 17 + 끌려온 35) → 18과제(Essential 17 + 문항 선행 Core 1). 두 학습자 모두 같은 모양.
  - 10문항을 제외한 학습자: master 코드로는 계획이 「Prepared prerequisite became unavailable」로 실패하거나(닫힘 없이 계산 시)
    뒤 목표 과제가 막혔는데, 바꾼 뒤에는 막힌 과제 0.

## 배포 대상 버전·순서·데이터 변경

- 서버(Cloud Run)와 웹(Pages)이 master 병합으로 함께 배포된다. 순서 제약 없음: 옛 웹은 새 `prerequisite` 필드를 무시하고,
  새 웹은 필드가 없으면 표시하지 않는다.
- DB 스키마·운영 데이터·학습 기록 변경 없음.

## 배포 후 확인·롤백·필요한 사람 승인

- 확인: 운영 `/health` SHA, 레지오넬라 편 Essential만 선택 시 오늘 목록 수(이미 시작한 오늘 흐름은 고정이라 다음 학습일부터 반영).
- 롤백: `git revert` 뒤 재배포.
- 승인: master 병합(=배포)은 사용자 확인 뒤. 겹침 PR #190·#194(목표 사이 존재 선행)·#185(같은 파일 다른 줄)는 나중 병합 쪽이 rebase.

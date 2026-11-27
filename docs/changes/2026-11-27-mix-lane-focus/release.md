# 모아풀기 강의별 중요도·저장값 기본 — 배포 준비

## 코드 리뷰·검증 결과

- server: `root_mix`(root_mix·root_mix_v4 2개)·`route_contract` 통과. 새 검사: 고른 적 없는 강의 `focus` null,
  `PUT …/focus` 뒤 그 값(TIERS 순서), 두 번째 선택이 마지막 값.
- web: `web-types` 통과. `root-batch` 브라우저 검사 4/4 통과 — 기존 3개(펼침 기본에 맞춰 「강의별」 클릭을 펼침 확인으로 바꿈)와
  새 검사(두 번째 강의에 Essential만 저장 → 그 줄만 Essential, 첫 강의는 전부, 전체 Core 「일부」, 화면에서 바꿔도 저장값 그대로).
  스크린숏 `runs/_development/2026-11-27-mix-lane-focus/batch-start-saved-focus.png`.

## 배포 대상 버전·순서·데이터 변경

- master 병합 = API(Cloud Run)·웹(Pages) 자동 배포. 서버·웹 순서 제약 없음(옛 서버면 처음 값이 전부일 뿐).
- 데이터 변경 없음.

## 배포 후 확인·롤백·필요한 사람 승인

- 확인: 라이브 `/mix` 응답에 `focus`, 강의 화면에서 범위를 좁힌 강의를 모아풀기에 넣어 그 줄의 칩이 저장값인지.
- 롤백: `git revert` 후 병합(자동 배포).

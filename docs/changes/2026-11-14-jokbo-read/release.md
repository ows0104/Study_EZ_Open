# 족보 1회 풀이를 회독에 기록 — 배포 준비

## 코드 리뷰·검증 결과
- 서버 검사(임시 SQLite·임시 저장소): `jokbo`(회독 POST 1→2, 시간표 `jokboRounds` 2, 남의 것 0, 목록만 읽기 0,
  없는 칸·관리자 전용 족보 404), `route_contract`(새 경로 1), 시간표를 읽는 검사 10개 통과.
- 웹 `typecheck`·`build` 통과. 실제 화면(로컬 API+족보 데이터) 확인은 하지 않았다.
- `scripts/map_numbers.py --check`는 이 PC의 Python에 검사 의존성이 없어 master 그대로도 같은 오류로 멈춘다 — CI에서 확인.

## 배포 대상 버전·순서·데이터 변경
1. **러너 PC에서 운영 DB에 `jokbo_round` 표 생성**(`create_table.py`, 출력 `jokbo_round: 새로 만듦 · RLS 켜짐`).
2. PR CI `Tests and build` 통과 확인 → master 병합(API 자동 배포 → Pages).
- 데이터 변경: 새 표 하나. 기존 표·행은 바뀌지 않는다.

## 배포 후 확인·롤백·필요한 사람 승인
- 확인: 운영 `/api/health` SHA, 족보 퀴즈 하나를 끝 화면까지 풀고 캘린더 칸·패널 회독 줄에 진한 회색 토막 1개.
- 롤백: PR revert(표는 남겨 둬도 옛 코드에 영향 없음).
- 사람 승인: 운영 표 생성(러너 PC), master 병합.

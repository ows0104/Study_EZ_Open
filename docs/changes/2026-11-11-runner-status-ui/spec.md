# 러너 상태 창 개편 — 설계

## 요구사항과 수용 기준
- 실행 중 작업 N개 → 카드 N개가 모두 보인다(고정 높이 캔버스 없음).
- Main-Quiz 카드: `강의명 · 경과` / 시간 비례 바 / `약 N분 남음 · HH:MM 완료 예상` / 6구간 줄(✓ 끝남, ● 지금, ○ 남음).
- 그 밖의 작업(예습·옛 Quiz Bank·다른 세션 등록 작업): 강의명·경과 / (서버 etaSeconds나 실측 범위가 있을 때만) 바·남은 시간 / 단계 문구.
- 상단 한 줄: `실행 중 n개 · 대기 n개 · 완료 n개 · 확인 필요 n개`, 「목록」을 누르면 기존 다섯 목록이 펼쳐진다.
- 상세 기록(러너 로그·내부 단계 이름)은 접혀 있다.

## 책임·입출력 계약·오류 상태
- `status_phases.py`는 읽기만 한다. 입력은 `runs/_root-generation/<gid>/` 아래 파일 이름·수정 시각뿐이다.
  - 구간 분류: `front/**` → 지도·포인트, `normalize`·`v?-brief-fix`·`v?-coverage-*`·`v?-map-check-*`·`v?-supplement*` → 커버 확인,
    `v?-add-*` → 추가 출제, `v?-review-*`·`v?-fix-*`·`v?-coverage-fix-*` → 검토·수정, `v?-context-*`·`medical-*` → 의학 검토,
    `result.json`·`published.json` → 게시. 구간 = 시작된 단계 중 가장 뒤 구간(뒤로 가지 않는다).
  - 구간 시작 시각 = 그 구간 첫 파일 시각. 지난 실행의 구간 소요 = 다음 구간 시작 − 이 구간 시작(다음 구간이 시작된 경우만).
    게시 구간은 `result.json` → `published.json`. 최근 실행 12개, 구간별 중앙값.
  - 이어 하기로 예전 파일이 남은 실행(앞 구간 파일이 작업 시작보다 이른 것)은 시작 시각을 작업 시작으로 자른다.
  - 남은 시간 = max(0, 현재 구간 중앙값 − 구간 경과) + 뒤 구간 중앙값 합. 현재 구간 경과가 중앙값을 넘으면 overrun.
    어느 구간이든 표본이 없으면 None(숫자 없음, 바 없음).
- 오류: 폴더·파일을 못 읽으면 None을 돌려주고 창은 기존 단계 문구만 보인다. 창이 멈추지 않는다.

## 호환성과 데이터 보존
- `JobStatus`에 기본값 있는 `generation` 칸만 더한다. 기존 호출자 그대로.
- `StatusWindow`의 `cards`(title, stage, detail)·`bars`·`state`·`overview_views`·`queue_view`·`heartbeat`·`toggle_details`는 유지(데스크톱 창·테스트가 쓴다).
- runs 파일은 읽기만 한다. 서버 대기열 조회 방식 불변.

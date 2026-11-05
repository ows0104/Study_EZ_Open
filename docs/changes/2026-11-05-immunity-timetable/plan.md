# 수정 감염과 면역 시간표 — Implementation Plan

## 변경 범위·대상 파일·순서
1. 현재 사용자 요청을 해당 범위 승인으로 기록하고 build gate 확인.
2. data/timetable/2026_본1_2학기_시간표.json의 주제별 변경, data/timetable/identities/2026-2.json의 이동 강의 안정 ID 작성.
3. runner/ahead.py의 기존 변경을 보존하면서 Cell.key/read_cells만 안정 ID 지원. 기존 _pairs는 유지.
4. scripts/immunity_timetable_update.py로 검증·차이 출력·데이터 후보 고정·조건부 적용·사후 확인 지원.
5. tests/runner/test_timetable_identity.py에서 JSON/SQLite 동일 ID·수정 위치·기존 작년 짝·기본 동작 검증.
6. 로컬 테스트 후 review/release 작성. 데이터 전용 후보(정본·ID·패치·도구)를 고정해 승인 근거를 묶고 deploy gate 확인.
7. 운영과 로컬 사본에 적용 후 별도 연결 검증. 서비스 앱은 재배포하지 않는다.

## 검사 명령과 성공 조건
- timetable: .venv/Scripts/python.exe -m pytest tests/runner/test_timetable_identity.py -q 및 원본 4쪽 전체와 패치 직접 대조.
- server: server/.venv/Scripts/python.exe -m tests matching (기존 매칭 회귀).
- data: 검증 도구의 격리 SQLite roundtrip 테스트: 재실행 무해·실패 시 rollback·자료/링크/학습 보존·seed 후 연결 유지.
- production: 시간표 전체 일치, 기존 강의 키·FK·보존 필드 일치, 누락·잘못 재연결 없음. 기존 미연결 1개는 새 손실과 구분.

## 위험·복원·승인할 범위
사용자의 2026-11-05 직접 반영 요청을 이 구체적 범위 승인으로 적용한다. 중복 승인을 요구하지 않는다.
DB는 전체 재시드 대신 변경 칸만 갱신한다. 사전 스냅샷과 양방향 패치를 보관하고 조건부 역패치로 복원한다.
시간표 데이터 전용 변경은 앱 패키지 배포와 다르므로 데이터 전용 후보를 고정한다. 기존 release_evidence의 server/web 패키지로 위장하지 않는다.
다른 세션의 변경을 커밋·배포에 포함하지 않는다. 실행 러너를 중단하거나 학습 작업을 새로 시작하지 않는다.

수정 위치에 올해 필기가 도착할 때도 기존 자료를 덮지 않도록 runner/filenames.py에서 날짜/교시와 명시적 전체 주제가 일치하는 12강의만 기존 키로 해석한다. data/timetable/identities/2026-2-notes.json의 검토된 정확한 별칭만 사용하며 다른 과목/시기에는 적용하지 않는다.

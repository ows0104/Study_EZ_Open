# Main-Quiz 지도에 못 붙은 문항 재배치 — 구현 계획

## 변경 범위·대상 파일·순서
1. R1: `quizbank/connection_generate_v4.py` 늦은 보충 입력에서 기존 포인트를 비움. 테스트 `tests/quizbank/test_map_relation_guard.py`에 더함.
2. R2 생성기: 새 `quizbank/connection_replace.py`(seed는 `connection_dedupe`의 것을 함께 씀), `quizbank/connection_generate.py`
   `run(..., unplaced_of=)` 분기·`--unplaced-of`, `runner/root_native_json.py` 인자 전달, `connection_generate_v4.run`에
   A를 건너뛰는 표식(ledger `unplacedOnly`가 있을 때만).
3. R2 러너: `runner/connection_generation.py` `_generate`에서 unplacedOnly면 duplicates_front와 같은 앞 단계 생략·`--unplaced-of`·근거 재사용.
4. R2 서버: `server/app/routes/root_generation.py` 요청 필드 `unplacedOnly`(duplicatesOnly와 같은 조건, 둘 다 켜면 거절)·packet·보고.
5. R3 웹: `web/src/bank/RootGenerationPanel.tsx` 요청 버튼.
6. 테스트: `tests/quizbank/test_connection_replace.py`(새), 서버 요청 검증 테스트, 러너 분기 테스트.
7. 실측(운영 쓰기 없음): 피코르나 261111_02 공개 실행을 로컬 사본에서 재배치 — 모델 호출 수·시간·미배치 전후·과제 유지 확인.

## 검사 명령과 성공 조건
- `python -m pytest tests/contracts tests/quizbank tests/runner -q` 통과(알려진 환경 실패 test_desktop_control 바로가기 제외).
- 서버 `python -m tests root`(`PYTHONPATH=..`, 격리 DB) 통과(pymupdf 없는 2개 제외), 웹 `tsc --noEmit` 변경 파일 오류 없음.
- 실측: 이전 과제 전부 유지, 미배치 감소, 새 모델 단계가 late 단계(+범위 밖이 있을 때 의학·맥락)뿐.

## 위험·복원·승인할 범위
- 위험: 범위 밖 판정이 늘면 문항이 offGoalQuestions로 빠진다(보고됨). 역방향·중복 목표가 늘어 과제 수가 늘어난다(의도).
- 위험: 재배치 판의 선지(root_mcq) 생성이 새 판 전체에 다시 돌 수 있다 — 실측에서 시간 확인.
- 복원: PR revert. 공개판은 이전 판으로 다시 교체 가능(이전 실행 폴더 보존).
- 순서상 조정: 러너 재설치는 job 620(레지오넬라 Claude 판)이 끝난 뒤. 소아감염 261113_02 재실행은 보충 포인트 ID 세션과 겹치므로 그 세션 확인 뒤.
- 이번 승인 범위(요청): 1~7 구현·검사·로컬 실측·Draft PR. 병합·러너 재설치·운영 공개판 교체(편마다)는 실측 보고 뒤 따로.

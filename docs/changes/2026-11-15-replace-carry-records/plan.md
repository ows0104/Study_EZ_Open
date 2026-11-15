# Main-Quiz 재배치 판에 기존 학습 기록 승계 — 구현 계획

## 변경 범위·순서
1. 계약 R3: `studyez_contracts/roots/validate.py` equivalence 고유 조건. 테스트 `tests/contracts`.
2. 서버 R2: `server/app/routes/root_generation.py` unplacedOnly packet에 `carrySources`. 테스트 `server/tests/test_root_restart.py`.
3. 생성기 R1: `quizbank/connection_replace.py` 최종 조립 뒤 링크 계산·manifest·0개면 보류. 러너는 packet을 그대로 넘기므로 변경 없음(확인).
4. (R4 선택 A일 때) `server/app/root_learning/state.py` `personal_tiers`, `content.py` `excluded_ids` — 학습률 절반 작업(#166)과 같은 파일·다른 함수.
5. 실측(운영 쓰기 없음): 3편의 운영 문서·이벤트를 읽기 전용으로 받아, 링크를 단 문서로 학습자별 `replay_tasks`를 돌려
   옛 판으로 계산한 과제 상태(답 봄·평가·예정일)가 새 문서의 같은 과제에서 같은지 대조.

## 검사
- `pytest tests/contracts tests/quizbank tests/runner` (알려진 바로가기 실패 제외), 서버 `python -m tests root` (`PYTHONPATH=..`, 격리 DB).

## 운영 적용 (병합 뒤, 각각 사용자 승인)
1. master 병합(API 자동 배포) → 러너 .runtime 재설치(러너가 한가할 때).
2. 이미 교체한 3편(피코르나·병리1·병리2)에 재배치 한 번 더: 남은 미배치 3~5문항을 다시 시도하고 이전 판들을 잇는다(편당 약 10분).
3. 무산소세균(job 623) 이어 하기, 간염바이러스 등 나머지 편 교체.

## 위험·복원
- 위험: 여러 판 기록을 한 과제에 합치면, 같은 학생이 옛 판과 새 판에서 각각 푼 기록이 한 줄로 이어진다(시간순 재생, 의도).
- 복원: 공개 판을 이전 판으로 되돌리면 그 판의 기록으로 돌아간다. 기록은 어느 쪽에서도 지우지 않는다.

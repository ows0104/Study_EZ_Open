# 늦은 보충 뒤 옛 검토 — 구현 계획

## 변경 범위·대상 파일·순서
1. `quizbank/connection_generate_v4.py` 문맥 고치기: `fix_round` 전에 `S.reviews = reviews`, 뒤에 `reviews = S.reviews`.
2. `tests/quizbank/test_review_evidence.py`: 사람이 뺀 문항으로 `reviews`를 바꾼 뒤 문맥 재검토가 다른 근거 쪽을 대면
   최종 인용이 재검토 쪽을 따르는지(고침 없이 「2쪽」으로 실패 확인).

## 검사 명령과 성공 조건
- `python -m pytest tests/quizbank tests/studyez_contracts -q` — 회귀 없음.
- 261124_02 사본 재생(모델 스텁): 의학 검토 호출까지 간다(로컬 확인, 2026-11-24).

## 위험·복원·승인할 범위
- 위험: 늦은 보충·사람이 뺀 문항이 있는 편의 조립 입력이 바뀐다(재검토를 반영). 이것이 의도한 동작이다.
- 복원: 이 PR revert 후 러너 재설치.
- 승인 범위: 위 파일과 이 폴더, Draft PR(사용자 「Yes, fix and PR」). 병합·러너 재설치·261124_02 requeue는 따로 확인.

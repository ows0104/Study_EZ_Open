# 관리 탭 로딩 지연 제거 — 구현 계획

## 변경 범위·대상 파일·순서
1. `server/app/admin_banks.py` — `revision`을 꺼낼 키에서 빼고 요약에서도 뺀다. `validation`은 `json_each` 한 번으로 꺼낸다.
2. `server/app/routes/bank_api/feedback.py` — `bank_feedback`의 `db.get(QuizBank)`에 `load_only(build_id, bank, review)`.
3. `server/tests/test_admin_egress.py` — 한 번 훑기·`revision` 제외·JSON null 행을 검사에 추가.

## 검사 명령과 성공 조건
- `server/`에서 `.venv/Scripts/python.exe -m tests` 전체 통과(worktree를 `PYTHONPATH`에 둔다).
- 운영 DB 읽기 전용 대조: 새 쿼리 결과의 요약이 전체 행으로 만든 `summary()`와 같다(작은 은행 5편).

## 위험·복원·승인할 범위
- 위험: overview 화면에서 쓰지 않는 값만 뺐다. 강의별 상세는 그대로다.
- 복원: git revert 후 master 병합, 또는 이전 Cloud Run revision.
- 승인: 사용자 요청 발언이 구현 승인이다. DB 쓰기·스키마·학습 기록 변경이 없어 「사람에게 묻는 것」에 닿지 않는다.

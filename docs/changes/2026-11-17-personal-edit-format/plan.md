# Main-Quiz 개인 수정 형식 — 구현 계획

## 변경 범위·순서
1. `server/app/models/bank.py`(structure 칼럼), `server/app/cli.py`(ADDED_COLUMNS)
2. `server/app/bank_personal.py` `apply_edit`
3. `server/app/routes/root_learning.py` `read_personal`·`save_personal`
4. `server/app/root_learning/mcq.py`: 형식 바뀐 수정본엔 선지 없음(mcq.py만, choices.py는 글 해시로 이미 안 맞음)
5. `web/src/bank/PersonalQuestionDialog.tsx`
6. `server/tests/test_root_personal.py`에 절 추가

## 검사
`server/`에서 격리 로컬 DB로 `-m tests root main_quiz bank_personal route_contract`, 웹 `typecheck`·`build`.

## 위험·복원·승인할 범위
- 운영 DB에 JSON 칼럼 하나 추가(NULL, 기존 행 영향 없음). **API 배포(master 병합) 전에 운영 `init-db`가 먼저** — 둘 다 사람 승인.
- 복원: 커밋 revert. 칼럼은 남아도 무해.

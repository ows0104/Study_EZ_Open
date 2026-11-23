# 관리 페이지 로딩 속도 — 구현 계획

## 변경 범위·대상 파일·순서

1. `server/app/routes/bank_api/feedback.py`: `_tally`, `GET /bank-feedback/count`,
   Main-Quiz 문면을 사본에서 읽는 `questions_of`.
2. `server/app/routes/cards.py`: `_flagged_runs`, `GET /card-review/count`.
3. `server/tests/`: `test_route_contract.py`(경로 둘 추가), `test_bank.py`·`test_card_edits.py`(숫자 = 목록),
   `test_root_personal.py`(원본을 읽지 않는다 · 옛 판 · 사본 칸이 빈 행).
4. `web/src/admin/AdminPage.tsx`·`CardReviewTab.tsx`·`BankReportTab.tsx`, `web/src/types/admin.ts`.

## 검사 명령과 성공 조건

- 서버(`server/`에서, `PYTHONPATH=..`): `.venv/Scripts/python.exe -m tests` 전부 통과.
- 웹: `npm --prefix web run typecheck`, `npm --prefix web run build`.
- 로컬 미리보기(격리된 로컬 DB): `/admin`이 뜰 때 목록 두 요청이 나가지 않고, 탭을 열면 한 번 나간다.
- 재현 검사는 고치기 전 코드에서 실패해야 한다(`test_root_personal`의 원본 읽기 단언).

## 위험·복원·승인할 범위

- 위험: 숫자 전용 경로와 목록의 수가 갈리는 것. 같은 함수에서 세고 검사가 둘을 맞대 본다.
- 복원: git revert와 이전 Cloud Run revision·Pages 배포. 데이터 변경이 없어 되돌릴 데이터도 없다.
- 승인: 사용자의 작업 요청이 구현 승인이다. 「사람에게 묻는 것」(운영 DB 쓰기·공개 범위 등)에 닿지 않는다.

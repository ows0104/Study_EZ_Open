# Main-Quiz 내 문제(추가·복사 후 수정)와 뒷면 메모 — 구현 계획

## 변경 범위·대상 파일·순서
1. 서버 `server/app/root_learning/mine.py`(새): 이벤트 접기(`current_mine`, `current_memos`), 덧붙인 사본
   `with_mine`, 준비 상태 `mine_availability`, 복사 초안 글 만들기.
2. 서버 `server/app/root_learning/content.py`: `front()`에 `personalAdded` 한 줄.
3. 서버 `server/app/routes/root_learning.py`:
   - 계획·흐름·풀이 경로(overview_data의 plan, refocus_stream, project_session, prepare, act)에 덧붙인 사본과 준비 상태.
     summary·question_progress·칩 개수는 원래 사본·원래 준비 상태 그대로. 「오늘 복습」 수에서 내 문제 제외.
   - 답에 `memo`, 투영에 `mineEnabled`. act의 건너뛰기에 지운 내 문제 포함.
   - 새 API 4개(mine-draft·mine 만들기·mine 고치기/지우기·memo).
   - 2026-11-16: 내 힌트 API `PUT …/questions/{id}/hint`(kind=hint), 앞면 `clue`·`personalClue`. 웹 `HintBox`(MineQuestionDialog.tsx)·RootSolve 메뉴·RootLearning `onHint`.
   - 내 문제에 대한 개인 수정·내 중요도 API는 404(원래 문항에만).
4. 서버 테스트 `server/tests/test_root_mine.py`(새): 만들기·복사·고치기·지우기·멱등·상한·이전 정책 409,
   계획에 나옴·평가 저장, 학습률·카드 수 불변, 메모 저장·답에 붙음·다른 사용자 안 보임, 은행 연결 판 허용.
5. 웹 `web/src/bank/MineQuestionDialog.tsx`(새), `RootSolve.tsx`(메뉴 항목·「내 문제」 표시·뒷면 메모),
   `RootLearning.tsx`(경로·저장 뒤 회차 다시 불러오기), `web/src/types/bank.ts`·`rootLearning.ts`(새 칸), CSS 몇 줄.
6. 안내: `web/src/notices/GuidePage.tsx` 한 줄, `docs/map.md` 행 하나.

## 검사 명령과 성공 조건
- 서버: `server/.venv`로 `PYTHONPATH=..` 붙여 `python -m pytest server/tests -k "root"` 전부 통과, 그다음 서버 테스트 전체.
  격리된 로컬 SQLite만 쓴다(`server/.env`의 운영 DB를 읽지 않게 테스트 설정 확인).
- 웹: `npm run typecheck`, `npm run build`(web/) 통과.
- 브라우저: 로컬 서버+웹으로 Main-Quiz 한 편을 열어 새 문제·복사·고치기·지우기·메모를 눌러 보고 화면·네트워크 확인.
- `python scripts/map_numbers.py --check`.

## 위험·복원·승인할 범위
- 위험: 덧붙인 사본이 캐시된 사본을 고치면 다른 사용자에게 내 문제가 보인다 → 얕은 복사 + 테스트(두 사용자).
- 위험: 내 문제를 선행으로 끌어오다 `order_plan` 500 → 준비 상태를 덧붙인 사본으로 다시 닫는다 + 테스트.
- 위험: 계산 경로에 덧붙인 사본이 새어 학습률이 바뀜 → 「내 문제 있음/없음 학습률 동일」 테스트.
- 복원: 코드만 바뀐다. git revert와 이전 Cloud Run revision·Pages 배포로 되돌린다. 쌓인 `mine`·`memo` 이벤트는
  옛 코드가 무시하므로 남겨 둬도 된다.
- 승인: 사용자 요청 발언이 구현 승인(개발 루프). DB 스키마 변경·운영 데이터 수정이 없어 따로 묻지 않는다.
  master 병합(=배포)은 PR 준비 뒤 진행한다.

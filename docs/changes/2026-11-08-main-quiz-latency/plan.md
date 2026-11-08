# Main-Quiz 풀이 지연 제거 — 구현 계획

## 변경 범위·대상 파일·순서
1. 서버 `server/app/routes/root_learning.py`: `prepare` 경로, `revealed_answer`가 미리 읽은 생성 기록을 받음,
   `frozen_source` 캐시. `server/tests/test_root_prepare.py`(신규), `server/tests/test_route_contract.py`.
2. 웹 `web/src/bank/useRootStudyWrites.ts`(순서 대기열), `useRootFrames.ts`(신규, 미리 받기·이미지 예열),
   `RootLearning.tsx`(즉시 그리기·확인 뒤 정합), `RootPdfSlides.tsx`(범위 전송·문서 유지·미리 그리기),
   `RootSolve.tsx`(대기 문구), `web/src/types/rootLearning.ts`.
3. `web/tests/root-learning.test.cjs`에 저장 1.5 s 지연 검사 추가.

## 검사 명령과 성공 조건
- `server/.venv/Scripts/python.exe -m tests` 전체 통과(격리 SQLite, `PYTHONPATH`=이 worktree).
- `python scripts/check_root_learning.py --check root-ui` 4개 통과(소유 fixture 8027/5193).
- `npm --prefix web run typecheck`, `npm --prefix web run build` 통과.

## 위험·복원·승인할 범위
- 위험: 미리 그린 상태와 서버가 어긋나는 경우(다른 탭, 문항 준비 상태 변화) → 다음 이벤트가 409로 거절되고 충돌
  보존·다시 불러오기로 복구된다. 화면이 잠시 앞서 있다가 되돌아갈 수 있다.
- 복원: git revert 후 master 자동 배포, 또는 이전 Cloud Run revision·Pages 배포로 되돌림. DB 변경 없음.
- 승인: 사용자 작업 요청(intent.md 원문)이 구현·되돌릴 수 있는 코드 배포 근거다. 「사람에게 묻는 것」에 닿지 않는다.

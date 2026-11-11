# 복습 퀴즈 되돌리기 무제한 — 구현 계획

## 변경 범위·대상 파일·순서
1. `server/app/routes/root_learning.py`: undoStack 도우미(옛 칸 호환), act의 reveal·rate·skip push / undo pop, project_session의 canUndo.
2. `server/app/root_learning/content.py`: events_for가 되돌린 이벤트를 뺀다. `state.py`: replay 두 곳에서 되돌린 reveal 무시.
3. `server/tests/test_root_undo_stack.py`(새): 답 보기·평가 여러 번 → 연속 되돌리기로 회차 처음까지, 보류 되돌리기, 되돌린 답 보기 다시 가능,
   인지·첫 학습 집계에서 빠짐, 옛 `undo` 칸 세션 호환.
4. `web/src/bank/RootLearning.tsx`: predict의 화면 목록.
5. `web/tests/root-learning.test.cjs`: 답 화면에서 Z, 연속 Z, 다시 나아가기.

## 검사 명령과 성공 조건
- `server`에서 root 관련 검사(root_api·root_state·root_adaptive·root_question_progress·root_usage·main_quiz·새 undo 검사) 통과. 격리된 로컬 테스트 DB만 사용.
- `web`에서 typecheck·build, `scripts/check_main_quiz_ui.py browser`(격리 fixture) 통과.

## 위험·복원·승인할 범위
- 진행 중 세션: 옛 칸 호환으로 끊기지 않는다. 롤백 시 옛 코드는 `undo` 칸만 읽어 한 칸 되돌리기로 돌아간다.
  롤백 뒤에는 되돌린 답 보기가 다시 인지로 집계된다(이벤트는 그대로 남아 있음).
- 운영 배포는 master 병합 시 기존 자동 배포 절차를 따른다.
- 승인 범위: 위 파일의 서버·화면 변경과 로컬 검사.

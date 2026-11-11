# 복습 퀴즈 되돌리기 무제한 — 설계

## 요구사항과 수용 기준
- 세션 state에 `undoStack`(목록)을 둔다. 답 보기·평가·보류마다 한 항목을 쌓는다.
  - reveal: `{requestId, kind:'reveal', taskId, added:[이번에 새로 노출된 관계 ID]}`
  - rate·skip: `{requestId, kind, index}`
- undo는 맨 위 항목을 꺼내 되돌린다. reveal이면 `reveals[taskId]`를 지우고 `added`를 `exposedRelations`에서 뺀다.
  rate·skip이면 `index`로 돌아간다. 비어 있으면 기존 409. 이벤트 payload `undo`에는 꺼낸 requestId를 기록한다.
- 결과: Z를 누를 때마다 직전 화면으로 한 단계씩(답 화면 → 문제 화면 → 이전 문항 답 화면 …) 회차 처음까지 간다.
- `canUndo` = 목록이 비어 있지 않고 학습일이 지나지 않음.
- 되돌린 reveal·rate는 학습 집계에서 빠진다: `content.events_for`가 undo가 가리키는 이벤트를 빼고 돌려준다
  (인지·첫 학습·학습 계획 습관·복습 일정 모두 같은 입력). `state.py`의 replay도 되돌린 reveal을 무시한다.

## 책임·입출력 계약·오류 상태
- 서버 `routes/root_learning.py`: act의 reveal·rate·skip·undo 분기, project_session의 canUndo.
- 서버 `root_learning/content.py`(events_for), `root_learning/state.py`(replay 두 곳의 reveal 조건).
- 웹 `RootLearning.tsx`: 즉시 그리기(predict)가 행동 전 화면을 목록으로 보관하고 Z마다 하나씩 꺼낸다. 서버를 다시 읽으면 목록을 비우고 서버 결과를 기다린다.
- API 응답 형태(`canUndo: boolean`)는 그대로다.

## 호환성과 데이터 보존
- DB 표·칼럼 변경 없음. 이벤트 기록은 지우지 않고 undo 이벤트로 표시만 한다.
- 진행 중 세션의 옛 `undo` 칸은 읽을 때 rate 한 항목으로 취급한다. 쓸 때 옛 `undo` 칸에 맨 위가 rate·skip이면 그 항목을 적어,
  롤백해도 한 칸 되돌리기는 동작한다.
- 이용현황(`usage.py`)의 행동 수는 활동 기록이라 바꾸지 않는다.

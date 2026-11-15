# Main-Quiz 내 문제(추가·복사 후 수정)와 뒷면 메모 — 설계

## 요구사항과 수용 기준

### 내 문제
- 풀이 화면 「더 보기」 메뉴(문항이 있을 때):
  - 「이 자리에 새 문제」: 빈 발문·정답·해설 칸. 지금 문항을 기준 자리(anchor)로 삼는다.
  - 「복사해서 고치기」: 지금 문항이 내게 보이는 그대로(개인 수정본 포함) 발문·정답·해설을 채워 연다. 빈칸 문항은 빈칸이
    보이는 발문, 선지가 있는 문항은 선지를 발문 아래 줄로 붙인다. 문항 그림(stimuli)은 그대로 따라온다(그림 바이트는 복사하지 않고
    sha256으로 같은 그림을 가리킨다).
  - 지금 문항이 내 문제면 「내 문제 고치기」「내 문제 지우기」. 이때 「문제 수정·제보」와 「내 중요도」는 보이지 않는다.
- 내 문제는 언제나 주관식(basic)이다. 중요도는 만들 때 기준 문항이 내게 보이는 중요도를 받는다.
- 자리: 기준 문항 과제의 방향(direction)에 붙고, 문서 과제 순서에서 기준 과제 바로 뒤에 온다. 내 문제를 기준으로 또 만들면
  그 내 문제의 기준 과제를 따른다.
- 일정: root-generation/4(문항별 상태) 판에서 일반 과제와 같은 계획 규칙(새 목표·복습 확인·미평가 과제·선행)을 받는다.
  만들거나 고치면 오늘 흐름의 안 푼 뒷부분을 다시 고른다(칩 바꿀 때와 같은 `refocus_stream`). 그래서 기준 목표를 이미
  배운 경우 새 내 문제는 보통 오늘 흐름 뒤에 붙는다.
- 이전 정책 판(/2 등, 방향마다 과제 하나만 내는 판)에서는 만들 수 없다. 메뉴 항목을 숨기고 API는 409.
- 학습률·카드 수·목표 요약·시험 계획·「오늘 복습」 수·중요도 칩 개수에 내 문제를 세지 않는다.
- 상한: 한 사람·한 강의·한 판에 내 문제 300개. 발문·정답·해설 각 4000자.
- 지우기: 계획·풀이에서 빠진다. 오늘 흐름에 이미 들어 있으면 그 자리는 건너뛴다(개인 제외와 같은 건너뛰기).
  저장된 평가 기록과 만든·고친 기록은 남는다.

### 뒷면 메모
- 답을 연 뒤 정답 바로 밑(해설 위, 2026-11-16 사용자 「메모는 정답 바로 밑에」, 짝짓기는 짝 목록 밑)에 「내 메모」. 비어 있으면 「메모 쓰기」 버튼, 있으면 글과 「고치기」.
- 저장: 「저장」 또는 Ctrl/⌘+Enter. 빈 글로 저장하면 지운 것과 같다. 2000자.
- 메모 칸에 입력하는 동안 풀이 단축키(1–4·Space·Z 등)는 동작하지 않는다(기존 키 처리가 textarea를 이미 건너뛴다).
- 내 문제에도 메모를 달 수 있다.

### 내 힌트(2026-11-16)
- 앞면 힌트 칸(`clue`)이 있을 때만 「힌트 보기」(H)가 보인다(기존 photo-quiz-import 동작 그대로). 없으면 화면에 아무것도 없다.
- 답 보기 전 「더 보기」에 「힌트 쓰기」(힌트 없을 때)·「힌트 고치기」(있을 때). 펼친 힌트 옆에도 「고치기」.
- 내 힌트가 있으면 원래 힌트 대신 보이고 「내 힌트」 표시. 「내 힌트 지우기」(빈 글 저장)로 원래 힌트(없으면 칸 없음)로 돌아간다.
- 나만, 이 판에만. 원래 `clue`·판 사본·문항 지문은 바꾸지 않는다. 1000자. 모든 판(메모처럼 이전 정책 판 포함)·내 문제에도.
- 쓰는 동안 타이머가 멈추고 풀이 단축키는 동작하지 않는다. Ctrl/⌘+Enter 저장, Escape 취소.

## 책임·입출력 계약·오류 상태

### 저장(새 표 없음)
`root_event`에 append-only. subject·run_id·revision은 그 판, session_id는 빈 값.
- `kind='mine'`: payload `{_request, action: 'save'|'delete', mine_id, anchor_task_id, source_question_id|null,
  question, answer, explanation, tier, stimuli:[{sha256,…그림 바이트 제외}], seq}`. 같은 mine_id의 최신(seq, created_at)이 현재 값.
- `kind='memo'`: payload `{_request, question_id, text, seq}`. 문항마다 최신 값. 빈 글은 지움.
- 둘 다 판(revision)별이다. 새 판에는 옮기지 않는다(ID만으로 승계하지 않는 규칙과 같다). 옛 판의 기록은 지우지 않는다.

### 문서 덧붙이기(`server/app/root_learning/mine.py`)
`with_mine(row, events)`가 요청마다 판 사본(LightRow)의 얕은 복사본을 만든다. 캐시된 사본은 고치지 않는다.
- `tasks`: 기준 과제 뒤에 `{task_id: mine_id, question_id: mine_id, direction_id: 기준의 방향, …기준 과제의 나머지 칸}`.
- `bank_snapshot.questions`: `bank_personal.added_question` 모양 + `personalAdded`, `stimuli`(sha만), `prerequisites: []`.
- `task_fingerprints`: 내 문제 내용(발문·정답·해설·그림 sha)의 sha256.
- 이 사본은 계획(`planning.plan`)·오늘 흐름·풀이 투영·미리 읽기·행동 기록에만 넘긴다.
  `state.summary`·`state.question_progress`·`score` 계열은 계속 원래 사본을 받는다 → 학습률에서 빠진다.
- 준비 상태: 원래 `content.availability` 결과에 「기준 과제가 준비된 내 문제」를 더하고 덧붙인 사본으로
  `content.close_prerequisites`를 다시 돈다(목표 선행 때문에 준비 안 된 과제에 기대는 내 문제가 계획에 들어가 500이 나지 않게).

### API (`BASE = /api/root-learning/lectures/{subject}/{run_id}`)
- `GET BASE/questions/{question_id}/mine-draft` → `{question, answer, explanation, mine: bool, enabled: bool}`.
  내 문제면 그 값, 아니면 복사에 쓸 지금 보이는 글.
- `POST BASE/mine` `{requestId, anchorQuestionId, copy: bool, question, answer, explanation}` → `{mineId, question(front)}`. 201.
- `PUT BASE/mine/{mine_id}` `{requestId, action:'save'|'delete', question?, answer?, explanation?}` → `{question(front)|null}`.
- `PUT BASE/questions/{question_id}/memo` `{requestId, text}` → `{memo}`.
- `PUT BASE/questions/{question_id}/hint` `{requestId, text}` → `{hint, clue(지금 보일 힌트, 없으면 ''), personalClue: bool}`.
  앞면에 내 힌트를 `clue`로, `personalClue: true`. root_event kind='hint'(메모와 같은 payload).
- 답(answer)에 `memo: string`, 앞면(front)에 `personalAdded: true`(내 문제), 회차 투영에 `mineEnabled: bool`.
- 같은 requestId 재전송은 처음 결과를 돌려준다. 다른 내용이면 409.
- 오류: 판에 없는 기준 문항 404, 이전 정책 판 409, 상한 초과 409, 빈 발문·정답 422, 남의 것·지운 mine 404.

## 호환성과 데이터 보존
- DB 스키마·migration 없음. 기존 문항·ID·학습 기록·개인 수정·제외 문항·내 중요도는 읽기만 한다.
- `events_for`가 새 kind를 함께 읽는다. 기존 소비자는 kind를 걸러 쓰므로(replay는 reveal·rate, 사용 현황은 reveal·rate,
  _habitual은 reveal) 값이 바뀌지 않는다. 검사로 확인한다.
- 내 문제의 평가 이벤트는 `task_id = mine_id`로 남는다. 원래 사본으로 돌리는 집계는 그 task를 모르므로 무시한다.
- 옛 웹은 새 칸을 몰라도 동작한다. 새 웹이 옛 서버를 만나면 `mineEnabled`가 없어 메뉴를 숨기고, 메모 칸은 `memo`가 있을 때만 그린다.
- 운영 데이터 직접 수정 없음. 사용자 화면에서 만든 기록만 쌓인다.

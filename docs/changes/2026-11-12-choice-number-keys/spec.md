# 복습 퀴즈 객관식 선지 번호 표시와 1–4 키 선택 · 5 키 제외 — 설계

## 요구사항과 수용 기준

1. `QuestionBody` 선지 머리표 = 화면 순서 번호. `AnswerBody` 선지별 해설 머리표도 같은 번호.
   객관식 정답 줄·선지 밖 해설 줄의 줄 앞 선지 ID 머리표(`B:`·`**B**:`·`B.`·`B)`)와 ID만 나열한 정답(`B`, `A, C`)은 번호로 보인다.
   짝짓기 오른쪽 A·B는 그대로.
2. `RootSolve` 키: 답 공개 전·선지 보임 상태에서 1–4 → `pick`(없는 번호는 무시). 답 공개 뒤 1–4 평가, `5` → 제외.
   메뉴에 「이 문제 제외 5」 버튼.
3. 서버 `POST /root-learning/sessions/{id}/events` `kind:'exclude'`:
   - 현재 과제가 없으면 409. 이벤트(RootEvent kind 'exclude', payload question_id·task_id·revision) 기록.
   - 회차 위치를 다음 과제로 옮긴 뒤, 같은 판에서 Main-Quiz로 제외한 문항의 과제는 건너뛴다.
   - undo 스택에 `{kind:'exclude', index:원래 위치}`. Z는 위치를 되돌리고, 기존 규칙대로 undo된 이벤트는 집계에서 빠지므로 제외도 풀린다.
4. `content.availability`: 같은 판(revision)의 undo되지 않은 exclude 이벤트 문항을 「개인 제외」로 뺀다(standalone 은행 포함).
   rate·skip으로 위치가 옮겨질 때도 Main-Quiz 제외 문항의 과제는 건너뛴다.
5. 사용 안내(GuidePage) 단축키 문장 갱신.

## 책임·입출력 계약·오류 상태

API는 Action.kind에 'exclude' 하나 추가. 응답 형식 같음. 같은 requestId 재요청은 기존처럼 같은 결과.
DB 스키마 변경 없음(RootEvent 한 종류 추가). 옛 Quiz Bank `BankState`는 쓰지 않는다.

## 호환성과 데이터 보존

제외는 판(revision)별이다 — 새 판에서 같은 ID를 학습도·제외로 승계하지 않는다. 기존 이벤트·기록은 지우지 않는다.
옛 코드로 롤백하면 'exclude' 이벤트는 집계에서 무시되고(알 수 없는 kind), 제외된 문항이 다시 나온다 — 기록은 남는다.

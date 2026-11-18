# 선행 문항 포함/미포함 선택 — 설계

## 요구사항과 수용 기준
R1 오늘 학습(강의 하나)
- `PUT .../focus`가 `prereqs: bool`(생략 시 true)을 받는다. 같은 `focus` root_event payload에 `prereqs`로 남긴다.
  `content.focus_for`는 (tiers, prereqs)를 돌려준다. 옛 기록(prereqs 없음)은 true다.
- `planning.plan(..., prereqs=True)`. false이고 focus가 있으면 선행을 끌어오는 범위를 `available`이 아니라 `focus`로 한다:
  존재 목표의 문항 단위 연결(`links`), links 없는 판의 존재 목표 전체, `order_plan`의 문항 선행 모두.
  필터 밖 선행은 「없는 것」(personal exclude와 같은 대우)이 되어 뒤 문항을 막지 않는다.
- 중요도가 모두 켜졌거나 prereqs가 true면 결과는 지금과 같다(바이트 단위).
- 개요 `focus`에 `prereqs`가 함께 온다. 회차 ID 키는 prereqs가 false이고 중요도가 좁혀졌을 때만 `{'prereqs': False}`를 더한다
  (기존 회차 ID 보존). 단추를 바꾸면 칩처럼 오늘 흐름의 안 푼 뒷부분만 다시 고른다(refocus_stream).

R2 모아풀기
- `MixStart.prereqs: bool = False`. 회차 options에는 true일 때만 `prereqs: true`를 넣는다(기존 열린 회차와 같은 조건이면 잇는다).
- `mix.select(..., prereqs=False, links=None)`: true면 고른 과제마다 문항 선행(`question_dependencies`)과 존재 연결(`links`)을
  따라가며, 강의 단위 과제(`classes`) 중 「미열람」·「복습 대상」인 것을 중요도·체크와 상관없이 더한다(재귀). 「나중」은 더하지 않는다.
  결과는 판 문서 과제 순서(순서대로) 또는 기존 `shuffled`(섞어서, 문항 선행 앞).
- 웹 `RootMixOptions.prereqs?: boolean`, 같은 조건 비교에 포함(없으면 false).

R3 화면
- 오늘 추천: 중요도 칩 줄 끝에 같은 모양의 토글 단추 「선행 문항」(aria-pressed). 칩이 모두 켜졌으면 비활성.
- 모아풀기: 「기존 학습률 무시」「미열람 문항 보기」 옆 체크 「선행 문항 포함」.
- 설명 문장은 넣지 않는다(라벨만).

## 책임·입출력 계약·오류 상태
- `PUT /root-learning/{subject}/{run_id}/focus` body `{requestId, tiers, prereqs?}` → overview. 같은 requestId 다른 내용은 409(기존과 같음).
- `POST .../mix-sessions` body에 `prereqs?` 추가. 고른 조건에 문항이 없으면 409(기존과 같음, 선행만으로는 회차를 열지 않음).

## 호환성과 데이터 보존
- DB 표·열 추가 없음. append-only root_event payload 키 하나 추가.
- 학습 기록·복습일·개인 중요도·제외 문항을 읽기만 한다.
- 기본값이 지금 동작이라 사용자가 바꾸기 전에는 계획·회차가 그대로다.

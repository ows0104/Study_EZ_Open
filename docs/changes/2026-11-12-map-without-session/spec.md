# Main-Quiz 개념 지도 회차 분리 — 설계

## 요구사항과 수용 기준
1. `POST /api/root-learning/lectures/{subject}/{run_id}/map` `{requestId}` — 회차 없이 활성 판의 지도를 돌려준다.
   응답 모양은 기존 `GET /root-learning/sessions/{id}/map`과 같고 `currentConceptIds`는 `[]`.
2. 이 요청은 학습자·강의·판·학습일당 한 번 `RootEvent(kind='map_view', session_id='')`를 남긴다.
   request_id는 `map-view-` + (subject, run_id, revision, day) 해시로 정해 같은 날 반복 열람은 행을 늘리지 않는다.
   클라이언트 requestId는 payload에만 보관한다.
3. `start()`가 새 `RootSession`을 만들 때 같은 판·학습일의 `map_view`가 있으면 `state.mapSeen = True`로 시작한다.
   이미 있는 회차(같은 identity)를 이어 받는 경우는 바꾸지 않는다.
4. 정책 미설정이면 409(기존 시작과 같은 메시지). 공개 범위 밖이면 404(`active()`).
5. 웹 `showMap()`: 회차(`view`)가 없으면 쓰기 큐를 거치지 않고 새 API로 지도를 받는다. 회차가 있으면 기존 경로.

## 책임·입출력 계약·오류 상태
- 서버 `server/app/routes/root_learning.py`: 지도 응답 생성을 `map_payload(doc, current)`로 묶어 두 route가 공유.
  새 route `lecture_map`, `start()`의 fresh state만 변경. `overview_data`·`act`는 건드리지 않는다(「시험일 미정」 작업 영역).
- 웹 `web/src/bank/RootLearning.tsx`: `showMap()`의 `begin()` 호출 경로와 `mapRequested` 대기 제거.
  실패 시 `error` 배너(쓰기 큐 아님) 후 학습 탭으로.
- 지도 화면 `RootMap`은 `summary`를 받는다. 회차가 없으면 `info.summary`를 넘긴다.

## 호환성과 데이터 보존
- DB 스키마 변경 없음. 새 `kind='map_view'` 행만 추가. 집계(`state`, `planning`)는 kind로 거르므로 영향 없음.
- 기존 회차·이벤트·학습 기록 불변. 기존 `map` 이벤트 경로 불변.

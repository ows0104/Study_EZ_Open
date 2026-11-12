# Main-Quiz 정리 화면 먼저·재개 카드 수·뒤로 — 설계

## 요구사항과 수용 기준
- `RootLearning` 첫 불러오기는 `refresh()`(resume 없음). `?start=1` 처리 제거, 강의 목록 ▶는 `bankHref(l)`로.
- 정리 화면이고 `info.sessionId`가 있으면 `GET /api/root-learning/sessions/{id}`(읽기 전용)로 남은 수를 읽어
  `RootToday.resumeCount`로 넘긴다. 읽는 동안은 배지 없음. 배지 aria-label 「카드 N개」 그대로.
- `RootToday.onBack`: 머리 kicker 맨 앞 `.quiz-back` 「뒤로」.

## 책임·입출력 계약·오류 상태
- 세션 읽기 실패는 배지만 생략(버튼은 그대로). 회차 시작 API(`POST …/sessions`)는 진행 중 회차를 그대로 돌려준다(서버 기존 동작).

## 호환성과 데이터 보존
- 옛 `?start=1` 주소는 무시(정리 화면). 기록·세션·이벤트 변경 없음.

# 화면 토글을 한 번 누른 값으로 기억 — 설계

## 요구사항과 수용 기준
- 새 `web/src/preferences.ts`: `usePreference(key, fallback, allowed)` 훅. 처음엔 저장값, 없거나 허용값이 아니거나 저장소를 못 읽으면 fallback.
  바꾸면 즉시 저장. 저장 실패는 조용히 무시하고 이번 화면에서는 고른 값으로 동작.
- 키: 기존 `studyez-sidebar`("1"/"0"), `studyez-list-view`("type"/"order") 그대로. 새 키 `studyez-map-questions`, `studyez-map-links`,
  `studyez-admin-report-done`, `studyez-admin-card-done`("1"/"0").
- 다시 열거나 새로고침해도 마지막으로 누른 값으로 보인다.

## 책임·입출력 계약·오류 상태
- 각 화면은 기존 useState 대신 usePreference를 쓴다. 표시·동작은 그대로.
- 개념 지도 「문항 접기」로 끌 때 개별로 펼친 문항도 닫는 기존 동작은 유지한다.

## 호환성과 데이터 보존
- 서버·API·DB 변경 없음. 기존 저장값은 같은 키·같은 값 형식이라 그대로 읽힌다.

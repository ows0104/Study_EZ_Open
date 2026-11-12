# 캘린더 복습 막대: 테두리 + 강조색 채움 — 설계

## 요구사항과 수용 기준
- `.meter` 바탕 transparent, `box-shadow: inset 0 0 0 1px var(--accent)`; 채움 `.meter > span`은 base.css의 `var(--accent)`.
- `.meter.is-closed`(불러오는 중)은 회색 테두리 그대로.
- `.readline i.rl-pre` 테두리 `var(--accent2)`, `.rl-pre.is-on` 바탕 `var(--accent2)`.

## 책임·입출력 계약·오류 상태
색은 CSS만 고른다. `ReviewMeter`는 너비(학습률)만 정한다 — 인라인 채움 색과 `reviewFill`은 없앴다.

## 호환성과 데이터 보존
강조색 토큰이라 사용자 조합·다크 모드를 따른다. 데이터 변경 없음.

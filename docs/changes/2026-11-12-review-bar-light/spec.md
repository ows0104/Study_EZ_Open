# 캘린더 복습 막대 색 옅게 — 설계

## 요구사항과 수용 기준
- `.meter` 바탕 = `--accent-soft`, 테두리(inset 1px) = `--accent-line` — `.today-card.is-review`와 같은 값.
- `.readline i.rl-pre.is-on` 바탕 = `--accent2-soft`, 테두리 = `--accent2-line` — `.today-card.is-pre`와 같은 값.
- 채움 `reviewFill(score)` = `color-mix(in srgb, var(--accent) round(42 − score×0.14)%, var(--surface))`.

## 책임·입출력 계약·오류 상태
`ChipLearning.tsx`의 `reviewFill`이 채움 색을 고르고, 범례(`CalendarPage.tsx`)와 막대(`ReviewMeter`)가 함께 쓴다.

## 호환성과 데이터 보존
색 토큰만 바꾼다. 다크 모드는 기존 토큰이 `--surface`와 섞이므로 그대로 따른다. 데이터 변경 없음.

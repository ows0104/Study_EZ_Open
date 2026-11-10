# 강의 패널 개인 대화 버튼 다듬기 (2026-11-10)

## 사용자 지시 (2026-11-10)

1. 개인 대화 링크가 생기면 공통 대화처럼 배경색을 약간 채운다.
2. 개인 대화 옆 ▾ 아이콘을 키운다.
3. ▾ 옆 작은 원(내 프롬프트를 고쳤다는 표시)이 안 보이게 한다.
4. 통계의 회독 옆 「+」 회독 추가 버튼 — 강의록 회독 저장(UI/UX 개편 2단계, 새 표·API·운영 DB 승인)이
   아직 없어 이번 범위에서 뺐다. 대시보드 「앞으로 하기로 약속된 일」의 2단계 항목.

5. (2026-11-10 추가 지시) 「덱 다운로드 칸에서 예습 자료와 복습 자료에 어떤 강의록을 보고 있는지 파일명도 보이도록」
   → 예습 덱 옆에 예습 필기(`notes_prev`), 복습 덱 옆에 올해 강의록(`notes_current`) 파일명. 길면 말줄임, 전체는 마우스를 올리면 보인다.
6. (2026-11-10 추가 지시) 「강의명 ... v3처럼 마지막에 버전 정보가 보였으면」
   → 앞의 `[날짜_교시]`를 떼고, 강의명 쪽만 말줄임, 끝의 판(`v3`)은 늘 보인다. 판이 없는 이름은 판 표시 없음.

## 바꾼 것

- `web/src/calendar/ChatSplit.tsx`: `linked`면 `is-linked`, `promptCustom`·`is-dot` 제거.
- `PreviewAction.tsx`·`ReviewAction.tsx`: 저장된 대화를 여는 칸에 `linked`.
- `web/src/styles/calendar.css`: `is-linked` 갈래 색 바탕(예습 `--accent2-soft`, 복습 `--accent-soft`), ▾ 11px→16px.

- `web/src/calendar/EventPanel.tsx`·`calendar.css`: 덱 다운로드를 세로 목록으로, 덱마다 강의록 파일명.
- `web/tests/professor-preview.tsx`: `?decks`로 덱·올해 강의록 파일을 붙이는 확인용 옵션.

API·DB·문항 변경 없음.

## 검사

- `npm run typecheck` 통과, `node tests/preview-actions.test.cjs` 21/21.
- `tests/professor-preview.html?decks`: 두 파일명이 덱 버튼 옆에 나오고, 긴 이름은 말줄임·패널 안에 들어감.
- `tests/review-actions.html?saved&student` 고정물: 예습·복습 개인 대화 모두 `is-linked` 바탕, ▾ 16px, 점 없음.

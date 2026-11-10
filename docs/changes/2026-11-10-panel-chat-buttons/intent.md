# 강의 패널 개인 대화 버튼 다듬기 (2026-11-10)

## 사용자 지시 (2026-11-10)

1. 개인 대화 링크가 생기면 공통 대화처럼 배경색을 약간 채운다.
2. 개인 대화 옆 ▾ 아이콘을 키운다.
3. ▾ 옆 작은 원(내 프롬프트를 고쳤다는 표시)이 안 보이게 한다.
4. 통계의 회독 옆 「+」 회독 추가 버튼 — 강의록 회독 저장(UI/UX 개편 2단계, 새 표·API·운영 DB 승인)이
   아직 없어 이번 범위에서 뺐다. 대시보드 「앞으로 하기로 약속된 일」의 2단계 항목.

5. (2026-11-10 추가 지시) 「덱 다운로드 칸에서 예습 자료와 복습 자료에 어떤 강의록을 보고 있는지 파일명도 보이도록」
   → 예습 덱 옆에 예습 필기(`notes_prev`), 복습 덱 옆에 올해 강의록(`notes_current`) 파일명. 길면 말줄임, 전체는 마우스를 올리면 보인다.

6. (2026-11-10 추가 지시) 「강의명 ... v3처럼 마지막에 버전 정보가 보였으면」 → 강의명만 말줄임, 끝의 판은 늘 보임, 앞의 `[날짜_교시]`는 뗌.
7. (2026-11-10 추가 지시, 운영 화면 확인 후) 「"예습"과 "오류 제보"가 잘리는 문제를 고쳐줘」, 「덱 다운로드와 예습/복습 자료 파일명은 전혀 다른 영역이야…
   "정보" 칸 아래에 들어가야 해. 그 아래에 기존 덱 다운로드가 들어가는 거고.」
   → 통계 아래 새 「정보」: 예습(`notes_prev`)·복습(`notes_current`) 파일명, 덱 유무와 상관없이 파일이 있으면 보임.
     덱 다운로드는 원래 한 줄로 되돌리고 그 아래에 둔다. 덱 버튼·「오류 제보」는 줄바꿈 금지.
     (첫 판은 파일명을 덱 줄에 붙여서 Main-Quiz 강의처럼 `main_apkg`가 없으면 복습 파일명이 안 보였다.)

## 바꾼 것

- `web/src/calendar/ChatSplit.tsx`: `linked`면 `is-linked`, `promptCustom`·`is-dot` 제거.
- `PreviewAction.tsx`·`ReviewAction.tsx`: 저장된 대화를 여는 칸에 `linked`.
- `web/src/styles/calendar.css`: `is-linked` 갈래 색 바탕(예습 `--accent2-soft`, 복습 `--accent-soft`), ▾ 11px→16px.

- `web/src/calendar/EventPanel.tsx`·`calendar.css`: 덱 다운로드를 세로 목록으로, 덱마다 강의록 파일명.
- `web/tests/professor-preview.tsx`: `?decks`로 덱·올해 강의록 파일을 붙이는 확인용 옵션.

- (7) `EventPanel.tsx` 「정보」 절·`NotesName`·`splitNotesName`, `calendar.css` 덱 줄 한 줄·nowrap·`notes-name`. 브랜치 `claude/panel-file-info`.

API·DB·문항 변경 없음.

## 검사

- `npm run typecheck` 통과, `node tests/preview-actions.test.cjs` 21/21.
- `tests/professor-preview.html?decks`: 두 파일명이 덱 버튼 옆에 나오고, 긴 이름은 말줄임·패널 안에 들어감.
- `tests/review-actions.html?saved&student` 고정물: 예습·복습 개인 대화 모두 `is-linked` 바탕, ▾ 16px, 점 없음.
- (7) `professor-preview.html?decks`, 패널 폭 280·300·321px: 통계→정보→덱 줄 순서, 복습 파일명 말줄임·`v3` 보임, 덱 버튼·오류 제보 한 줄.

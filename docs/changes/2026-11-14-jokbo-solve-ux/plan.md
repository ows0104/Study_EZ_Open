# 구현 계획

승인: 사용자 요청(2026-11-14 채팅) 자체가 이 범위의 구현 지시(개발 루프 3단계). 웹만, DB 변경 없음.

## 파일

1. `web/src/jokbo/marks.tsx`: 3단계 표(모르겠음 high · 주의 mid · 괜찮음 null), `shownBand`(low→mid), `RatingButtons`.
2. `web/src/jokbo/JokboPage.tsx`: 풀이를 예습 퀴즈 틀로(머리줄·진행 막대·카드·독), 답 뒤 3단계 독과 키, 끝 화면(요약·버튼·넣은 문제 펼침).
   문항 본문(선지·답·해설)은 풀이·끝·오답노트가 같이 쓰도록 `JokboBody`로 나눈다.
3. `web/src/jokbo/WrongNotePage.tsx`: 강의 칩·강의별 묶음, 풀기/정답 보기 토글 삭제, 전체 정답 보기, 3단계 버튼.
4. `web/src/jokbo/jokbo.css`: 폭·글자·줄간격, 독, 끝 화면, 강의 묶음.
5. `web/src/types/jokbo.ts` 주석, `web/src/notices/GuidePage.tsx` 족보·오답노트 안내.

## 검사

- `web/`에서 `npm run typecheck`, `npm run build`.
- 격리 로컬 API(`api-jokbo-8020`형, 이 worktree의 `server/local_test_data/jokbo-*` 사본)로 풀이·끝·오답노트 화면 확인.

## 위험·복원

- 키: 숫자 키를 답 전엔 선지, 답 뒤엔 표시로 쓴다. 길게 누름(repeat)은 무시한다.
- 복원은 `git revert`(웹만).

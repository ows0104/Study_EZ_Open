# 출시 기록

## 검사 (2026-11-14)

- `web/`: `npm run typecheck` 통과, `npm run build` 통과.
- `node --test web/tests/jokbo-selection.test.cjs` 5/5 통과(선택·채점 로직은 바꾸지 않음).
- 격리 로컬 API(sqlite `server/local_test_data/jokbo-dev.db` 사본, 운영 DB 아님) + vite로 확인:
  - 풀이 본문 폭 780px(문제 줄 폭 약 720px). 원인은 main-quiz.css의 셸 안 `max-width:1100px`였다.
  - 답 뒤 독 모르겠음/주의/괜찮음, 키 1·2·3·Enter. 틀림이면 기본값 모르겠음, 맞음이면 괜찮음.
  - 10문항을 섞어 고른 뒤 DB의 band: 주의→mid, 모르겠음→high, 틀린 뒤 괜찮음→NULL(채점 기록 뒤에 표시를 써서 high로 덮이지 않음).
  - 끝 화면: 뒤로·다시 풀기·족보 마치기, 요약 `10문항 · 맞힘 0 · 모르겠음 5 · 주의 2`, 넣은 문제 7개 답·해설 펼침.
  - 오답노트: 강의 칩(전체 8 · 강의 둘), 강의별 묶음, 한 강의 거르기 1장, 전체 정답 보기 켜면 8장 모두 열림, 풀기/정답 보기 토글 없음.
  - 375px 폭에서 풀이 화면·독 확인.

## 배포

웹만. 서버·DB 변경 없음. master 병합 시 자동 배포(Pages). 복원은 `git revert`.

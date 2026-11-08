# 감염병리1 Main-Quiz 진입 버튼과 시작 화면 (2026-11-08)

## Intent (사용자 원문 요약)

> 감염병리1에서 Main-Quiz 버튼이 왜 활성화가 안 되어 있지? 학습현황에서도.
> 우리가 만든 그래프가 반영된 게 맞아? 학습한 사람은 나밖에 없어서 학습기록 날아가도 돼.
> Main-Quiz로 갈 때의 UI를 홈 화면과 일치시키고, 필요 없는 건 날리고 더 예쁘게.

## 진단 (운영 DB 읽기 전용 조회, 쓰기 0)

- 감염병리1 = `감염과 면역/261104_02`. Quiz Bank 행이 없고, 뿌리 학습(Main-Quiz) 판
  `main-quiz-reviewed-6143c8c89ad64d9c`만 검토·공개(enabled)되어 있다. Cloud Run의
  `STUDYEZ_ROOT_LEARNING_ENABLED=true`, 학습 기록이 있는 계정은 관리자다.
- `GET /api/main-quiz/.../entry`는 이 계정에 `structured`를 돌려준다(격리 실행으로 확인, 1.1–1.6 s).
- 그런데 시간표 `/api/timetable`의 `marks.quiz`는 Quiz Bank만 센다. 캘린더 칸의 복습 자리,
  강의 목록(학습현황)의 열림·링크, 패널 버튼의 첫 표시가 모두 이 값을 본다.
  → Main-Quiz만 있는 강의는 「퀴즈 없음」·비활성으로 그려졌다(패널 버튼은 entry 응답 뒤에야 켜짐).
- 그래프: 감염병리1 Map /3 실행(`runs/_e2e/26110801/`)은 중요도 단계에서 결과 없이 멈췄다
  (`docs/changes/2026-11-08-infection-path1-map/stopped.md`). 운영의 Main-Quiz는 그 전 판(문제은행 변환본,
  평평한 지도)이다. 이 변경은 그래프를 등록하지 않는다.

## 변경

- 서버: `root_learning.content.published_for` — 계정에 열린 검토·공개 Main-Quiz를 문서 JSON 없이 센다.
  시간표가 강의마다 `marks.mainQuiz`를 싣는다. `marks.quiz`(Quiz Bank) 의미는 그대로.
- 웹
  - 캘린더 칸·관리자 칸: `quiz || mainQuiz`면 복습 자리를 연다. 패널 「▶ 복습 퀴즈」는 `marks.mainQuiz`로 바로 켜진다.
  - 강의 목록: Main-Quiz만 있는 강의는 링크로 열리고 「Main-Quiz · 첫 학습 n/N · 회상 가능 m」과 회상 비율을 보인다.
    모아풀기(은행만 섞음) 선택에는 넣지 않는다. 「더 보기」 아래 중복 목록(RootOverviewPanel)은 뺐다.
  - Main-Quiz 시작 화면: 홈과 같은 좌측 메뉴 안에 선다. 머리(배지·제목·개념 지도), 숫자 칸 셋, 진행 막대,
    「오늘 추천」 카드와 시작 버튼, 접힌 「학습 현황·자료 범위」. 문항을 푸는 동안만 기존처럼 창 전체를 쓴다
    (`shell/studyChrome.tsx`). 「← 강의로」「기존 문제·기록」 머리 줄은 없앴고, 기존 문제 링크·자료 판·만들기·
    공개 관리는 관리자 접힘 하나로 모았다.
- DB 스키마·학습 기록·문항·공개 범위 변경 없음.

## 검사

- 서버 `-m tests` 전체(격리 SQLite), 새 `test_root_timetable_mark`(계정 범위·전역 설정·중지).
- `check_root_learning.py --check root-ui` 4/4, `web/tests/study-blocks.test.cjs` 14/14(새 Main-Quiz 행 검사 포함),
  `calendar-loading` 통과, `npm run typecheck`, `npm run build`.
- 격리 fixture로 데스크톱 1360·휴대폰 390 화면 확인: 강의 목록 행, 캘린더 칸, 패널 버튼(링크), 시작 화면(좌측 메뉴),
  풀이 중 전체 폭, 쉬기 후 좌측 메뉴 복귀, 가로 넘침 없음, 페이지 오류 0.

## 남은 것

- 감염병리1 그래프(Map /3) 재개와 운영 등록은 별도 작업이다. 사용자는 이 강의의 기존 학습 기록을 잃어도 된다고 했다
  (2026-11-08). 그 허락은 그 등록 작업에서만 쓴다.

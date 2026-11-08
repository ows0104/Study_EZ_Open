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
- 그런데 시간표 `/api/timetable`의 `marks.quiz`는 Quiz Bank만 센다. 캘린더 칸의 학습률 막대,
  강의 목록(학습현황)의 열림·링크, 패널 버튼의 첫 표시가 모두 이 값을 본다.
  → Main-Quiz만 있는 강의는 「퀴즈 없음」·비활성으로 그려졌다(패널 버튼은 entry 응답 뒤에야 켜짐).
- 그래프: 감염병리1 Map /3 실행(`runs/_e2e/26110801/`)은 중요도 단계에서 결과 없이 멈췄다
  (`docs/changes/2026-11-08-infection-path1-map/stopped.md`). 운영의 Main-Quiz는 그 전 판(문제은행 변환본,
  평평한 지도)이다. 이 변경은 그래프를 등록하지 않는다.

## 변경

- 서버: `root_learning.content.published_for` — 계정에 열린 검토·공개 Main-Quiz를 문서 JSON 없이 센다.
  시간표가 강의마다 `marks.mainQuiz`를 싣는다. `marks.quiz`(Quiz Bank) 의미는 그대로.
- 웹
  - 패널 「▶ 복습 퀴즈」는 `marks.mainQuiz`로 바로 켜진다.
  - (정정) #31에서 `calendar/entries.ts`의 `lectureSlots`·`adminLectureSlots`도 `quiz || mainQuiz`로 바꿨지만,
    두 함수는 화면 어디에서도 쓰지 않는 코드다(빌드에서 빠짐). 캘린더 칸 막대는 `ChipLearning`이 그리고,
    #31 시점에는 여전히 `marks.quiz`만 봐서 회색이었다. 아래 후속에서 고쳤다.
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

## 후속 (같은 날, claude/main-quiz-chip-rate)

- 캘린더 칸 막대(`ChipLearning`)·칸 설명·패널 「학습률」이 Main-Quiz만 있는 강의에서 Main-Quiz 학습률을 보인다.
  정의는 강의 목록과 같다: 회상 가능 목표 ÷ 전체 목표(`bank/useRootCatalog.ts`의 `rootRate`).
- 요약은 `/api/root-learning` 한 번으로 받아 칸·목록이 60초 나눠 쓴다. Main-Quiz 강의가 보일 때만 묻는다.
  패널은 이미 받은 entry 개요의 요약을 쓴다(추가 요청 없음).
- 검사: typecheck, `study-blocks` 14/14, `calendar-loading` 3/3. 격리 fixture에서 세 문항을 Easy로 평가한 뒤
  칸 설명·막대·패널·강의 목록이 모두 67%(회상 가능 2/3)로 같음을 확인, 페이지 오류 0.

## 후속 2 (같은 날, claude/main-quiz-solve-ui)

사용자: 「풀이 화면은 옛날 화면이고, 시작하면 새 페이지가 잠깐 보였다가 옛날 풀이 화면으로 넘어간다.」

- 원인: 진행 중 회차가 있으면 화면이 개요를 받아 시작 화면을 먼저 그린 뒤 회차를 불러와 풀이로 넘어갔다(자동 재개).
  풀이 화면은 좌측 메뉴 없는 예전 틀(`StudyNav`·전체 폭)로 바뀌었다.
- 자동 재개(새로고침·다른 탭)는 기존 검사가 요구하므로 유지하고, 회차를 먼저 불러온 뒤 개요를 넣는다 — 시작 화면이 끼지 않는다.
  `web/tests/root-learning.test.cjs`의 새로고침 단계에 「시작 화면을 한 번도 그리지 않음」 확인을 더했다(옛 순서로 되돌리면 실패함을 확인).
- 새 Main-Quiz는 풀이·완료·개념 지도까지 홈 좌측 메뉴 안에 선다. 머리(배지·강의 제목·알약 버튼 개념 지도/쉬기/더 보기),
  진행 막대, 문항 카드, 화면 아래 떠 있는 평가 독(sticky — 좌측 메뉴를 가리지 않음), 완료 카드.
  같은 주소의 기존 Quiz Bank 풀이만 예전처럼 창 전체를 쓴다.
- 검사: typecheck·build, root-ui 4/4, study-blocks 14/14. 격리 fixture 데스크톱 1360·휴대폰 390: 풀이 중 좌측 메뉴 유지·StudyNav 없음,
  다시 열 때 시작 화면 0회, 가로 넘침 없음, 페이지 오류 0. 웹만.

## 후속 3 (같은 날, claude/main-quiz-answer-layout)

사용자: 「문항 검수 기록·참고 슬라이드·파일 줄 같은 건 참고 슬라이드 아래로. 검토 기록은 이 문제 것만. 쉬기는 왜 있지? 문제 수정/오류 제보는 어디 갔지?」

- 답 영역 순서: 답·해설 → 슬라이드 그림 → 파일·PDF 쪽·원본 열기 → 접힌 「이 문항 검토 기록」 하나.
  「참고 슬라이드」 머리글과 답 안의 「문항 검수 기록」은 없앴다(기존 Quiz Bank 화면은 `AnswerBody`의 기본값으로 그대로).
- 서버 `revealed_answer`의 `reviewIssues`가 회차 전체 메모(입력 문제·검증 오류·경고)를 모든 답에 붙이던 것을, 그 문항 id를
  낱말로 가리키는 것만 남기게 했다(`question_issues`, `server/tests/test_root_question_issues.py`). 원본 메모는 생성 기록에 그대로.
  운영 261104_02 읽기 전용 대조: 98문항 중 92문항은 회차 메모 0, 이름이 적힌 6문항(Q085·Q051·Q055·Q084·Q091·Q092)만 남는다.
- 「쉬기」는 풀이를 멈추고 오늘 현황(시작 화면)으로 가는 버튼이었다. 평가는 누를 때마다 저장되고 좌측 메뉴가 있어 헤더에서 뺐고,
  「더 보기 → 오늘 현황 보기」로 옮겼다.
- 오류 제보: #34에서 예전 상단 줄(StudyNav)과 함께 「피드백」 버튼이 풀이 화면에서 빠졌다. 「더 보기 → 문제 제보」로 되살렸다.
  일반 피드백 API(`/api/feedback`)로 보내고, 화면 칸에 강의·문항 id·과제 id·발문을 싣는다. 대화상자 내용은 열 때만 그린다.
- 문제 수정: 기존 Quiz Bank 풀이의 「문제 변경/추가/삭제」(개인 수정·추가·비활성화)는 Quiz Bank API 기능이다. 새 Main-Quiz는
  검토된 판을 그대로 쓰며 문항 수정 API가 없다. 이번 변경에 넣지 않았다.
- 검사: 서버 전체 126, root-ui 4/4, bank-slides·study-blocks 19, typecheck·build. 격리 fixture에서 순서(그림<출처<기록),
  회차 메모 미노출, 제보 전송(화면 칸에 문항 id), 닫힌 동안 입력칸 0, 맨 아래에서 카드와 평가 독 간격 20px 확인.

## 후속 4 (같은 날, claude/main-quiz-question-edit)

사용자: 「문제 수정, 오류 제보 기능은 넣어야 할 듯.」

- 새 Main-Quiz 풀이의 「더 보기 → 문제 수정·제보」. 기존 Quiz Bank와 같은 대화상자(`PersonalQuestionDialog`)를 쓴다.
  - 발문·정답 개인 수정본은 내 계정의 풀이·미리받기에만 보이고 「내 수정본」 표시가 붙는다. 원본 판·다른 계정·학습 사건은 그대로.
  - 저장하면 관리자 신고함(「Quiz Bank 신고」 탭)에 남는다. 수정 내용은 [개인 수정 제안]으로 붙는다. 원본으로 되돌리기는 수정본만 지운다.
- 새 표 없음: `bank_personal_edit`·`bank_feedback`(둘 다 강의 외래키만)을 그대로 쓴다. 제보의 `build_id`는 `root:<판>`(64자 자름)이고,
  신고함은 그 판의 Main-Quiz 문항 문면을 싣고 지금 공개 판이 아니면 옛 판으로 표시한다.
- 개인 수정은 문제은행 없이 선 판(standalone, 감염병리1)만. 문제은행과 연결된 판은 기존 규칙(`content.availability`)상 개인 수정본이
  있으면 그 과제를 연결 미확인으로 막으므로 제보만 받는다(대화상자가 「문제 제보」로 바뀐다).
- 이용현황: 「문제 수정·제보 저장」(`question_report`, bank_feedback 한 줄 = 한 건)을 카탈로그에 등록했다. 기존 은행 제보도 같이 센다
  (이전에는 등록돼 있지 않았다).
- #36의 일반 피드백 「문제 제보」는 이 항목으로 대신했다(`FeedbackButton`의 문맥 prop 제거, 열 때만 그리기는 유지).
- 검사: 서버 전체 127(새 `test_root_personal`: 계정 분리·풀이/미리받기 반영·사건 미기록·신고함 문면·되돌리기·연결 판 제보만·이용현황),
  route_contract, root-ui 4/4, personal-questions 5/5(기존 은행 대화상자), study-blocks·bank-slides 19, typecheck·build.
  격리 fixture 브라우저: 저장 → 「내 수정본」·문면 반영 → 새로고침 유지 → 관리자 신고함 탭에 문면 → 되돌리기, 페이지 오류 0.

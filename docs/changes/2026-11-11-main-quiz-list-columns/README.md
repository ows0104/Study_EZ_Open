# 강의 목록 Main-Quiz 행을 숫자 열로 (2026-11-11)

상태: **구현·로컬 검사 완료, 병합(=배포) 승인 대기**. 사용자 2026-11-11 승인과 추가 지시(아래 「추가 지시」).

## 검사 결과 (2026-11-11)

- 서버 `-m tests test_root_question_progress` 통과(격리 SQLite). `-m tests root` 32개 중 30 통과,
  실패 2개(test_root_map_tree·_v3)는 로컬 venv에 PyMuPDF 없음(`No module named 'pymupdf'`) — 이 변경과 무관, 기존 기록과 같은 증상.
- 웹 `npm run typecheck`·`npm run build` 통과, `node --test tests/study-blocks.test.cjs` 15/15
  (Main-Quiz 행 숫자 열·배지/문장/막대 없음·상단 합계·▶ 단추, 유형별/순서대로).
- 고정물 `web/tests/study-overview.html`(사슬알균을 Main-Quiz만 있는 강의로) 브라우저 확인, 콘솔 오류 0:
  - 사슬알균 행 96·80·9·5·2·4·10%, 상단 합계에 더해짐.
  - 순서대로: 1·2·3·TBL 1 영상·TBL 1·4·실습 1·5·6(날짜 순, 구역 머리 없음), 새로고침 뒤에도 유지.
  - 행 클릭 → 1360 폭에서 목록 오른쪽 374px 패널, 375 폭에서 아래 시트. 누른 행 표시.
  - Quiz Bank 행 ▶ → 그 강의 하나로 모아풀기 시작(패널 안 열림). 가로 넘침 0(1360·375).
- 확인 못 한 것: Main-Quiz ▶(`?start=1`)의 실제 회차 자동 시작은 로컬 API 없이 확인하지 않았다. 운영 판 문항 수 읽기 전용 집계(계획 6단계)는
  이 컴퓨터에 server/.env가 없어 하지 않았다.

## 추가 지시 (2026-11-11, 같은 승인)

> 1. 우선 새로운 구조 기능으로 나타내도록 하고, 옛날 구조 판 문항은 새로 만들 예정이긴 한데 옛 구조도 지금 정의한 문항별 숫자를 따라갈 수 있도록 구현해줘.
> 2. 학습률 버튼 오른쪽에 복습 퀴즈 바로 푸는 버튼을 추가해줘.
> 3. 각 강의를 클릭하면 지금 아예 다른 페이지로 진입하게 되는데, 캘린더에서랑 동일한 사이드 패널을 띄워줘.
> 4. 유형별로 보기/순서대로 보기 전환할 수 있는 토글을 만들어서 순서대로 보기를 클릭하면 최초 디자인했던 것처럼,
>    tbl/cbl 등도 포함해서 강의한 순서대로 배열해줘. 유형별로 보기는 지금 그대로고.

- 1 → 아래 Spec 그대로(새 구조는 문항별 상태, 옛 구조는 방향마다 내는 문항 하나에 같은 열 정의).
- 2 → 학습률 칸 오른쪽에 「▶」 단추. Quiz Bank 강의는 그 강의 하나로 모아풀기(기존 경로, 시작 화면 없이 풀이),
  Main-Quiz 강의는 `/bank/…?start=1` — 시작 화면에서 오늘 계획이 있으면 곧바로 회차를 연다(진행 중 회차는 기존처럼 이어 풂).
  퀴즈 없는 강의는 단추 없음.
- 3 → 행을 누르면 캘린더와 같은 `EventPanel`을 목록 오른쪽에 띄운다(같은 칸의 그 강의 탭이 열림). 제목 링크도 패널을 연다.
  `EventPanel`에 처음 고를 강의 번호(`initialLecture`)만 더한다. 캘린더 화면 불변.
- 4 → 표 위 토글 「유형별」(기본, 현행 그대로)·「순서대로」. 순서대로는 구역 머리 없이 강의·실습·TBL·CBL을 날짜·시각 순 한 목록으로.
  고른 보기는 이 브라우저에만 기억(localStorage).

## Intent

사용자 원문(2026-11-11):

> 강의 목록 페이지가 최초 디자인이랑 너무 많이 달라지지 않았어? main-quiz랑 저 바는 왜 있는 거야?
> 항목별로 숫자만 나타내기로 최초에 디자인하지 않았어?
>
> 저장 = 목표 기억률에 도달한 문항 수로 설정해줘. 복습 문항 수는 프로그램이 계산하는 기존 알고리즘이 있을거야.
> 그리고 학습률 계산을 나 말고 다른 팀원(오정빈)이 검토하도록 대시보드에 작성해줘.
>
> 문항 단위로 계획

- 문제: #31(b10e54b6, 2026-11-08)이 Main-Quiz 버튼을 켜면서 강의 목록 행 모양을 바꿨다. Main-Quiz만 있는 강의는
  다섯 열을 한 칸으로 합쳐 `Main-Quiz` 배지, 「첫 학습 n/N · 회상 가능 m」 문장, 진행 막대를 그린다. 숫자는 목표 단위(감염병리1 44개)다.
  상단 요약(오늘 복습·전체 카드·단계 막대)은 Quiz Bank 카드만 세서, Main-Quiz만 있는 블럭에서는 모두 0이나 —로 나온다.
- 성공: Main-Quiz 행도 Quiz Bank 행과 같은 열(전체·미열람·인지·인출·저장·복습·학습률)에 **문항 단위 숫자만** 보인다.
  배지·문장·막대가 없다. 상단 요약 숫자와 단계 막대에 Main-Quiz 문항이 더해진다.

## Spec

### 열 정의 (문항 단위, Quiz Bank `card_progress`와 같은 규칙)

| 열 | Quiz Bank (현행, `study_engine/card_progress.py`) | Main-Quiz (이번 변경) |
|---|---|---|
| 전체 | 활성 문항 수 | 학습에 쓰는 문항 수(아래 「문항」) |
| 미열람 | 본 적 없음 | 시도 후 답 확인(`reveal`, attempted) 기록 없음 |
| 인지 | 봤지만 마지막 평가가 Good/Easy 아님 | 시도했지만 마지막 평가가 Good/Easy 아님(평가 없음 포함) |
| 인출 | 마지막 Good/Easy, 저장 전 | 마지막 평가 Good/Easy, 저장 전 |
| 저장 | Good/Easy가 서로 다른 이틀 이상 **그리고** 현재 숙련도 ≥ 목표 숙련도 | 같은 두 조건. 목표 = 그 평가에 저장된 목표 기억률(문항 중요도 또는 내 중요도, `policy.target_retention`) |
| 복습 | 오늘 큐의 복습 단위 중 남은 것 | 오늘 계획에서 `복습 확인`으로 고른 수(`planning.plan`·`plan_tasks`, 평가 기록이 있고 복습 예정일 ≤ 오늘이며 오늘 평가 안 한 것) |
| 학습률 | `lecture_mastery.score` | **현행 그대로**(회상 가능 목표 ÷ 전체 목표). 정의 통일은 오정빈 검토(대시보드 2번 표) 뒤 별도 변경 |

- 미열람 + 인지 + 인출 + 저장 = 전체. 복습은 평가한 문항만이므로 미열람은 복습에 들어가지 않는다.
- Good/Easy: 네 단추 평가는 `selfRating`. 그 전 평가는 `rating == 'independent'`(도움 노출이면 이미 partial로 내려가 있음).
- 현재 숙련도: 마지막 평가 때 숙련도 M을 지금까지 `M / (1 + t / 9S)`로 감쇠한 값(Quiz Bank와 같은 식, `next_mastery`의 감쇠).
- 목표 기억률이 없는 평가(2026-11-09 이전, `targetParameters` 없음)만 있는 문항은 저장으로 세지 않는다(인출에 머문다).

### 「문항」

- 새 구조 2(`root-generation/4`): 상태를 문항(task)마다 재생한다(`replay_tasks`). 준비된(available) 문항 하나 = 한 줄.
- 그 전 판(감염병리1 등): 상태가 회상 방향마다 재생되고, 오늘 계획은 방향마다 준비된 첫 문항 하나만 낸다.
  같은 방향의 다른 문항은 출제되지 않으므로 세면 영원히 미열람으로 남는다. → **방향마다 실제로 내는 문항 하나**를 센다.
  감염병리1의 전체 수는 98(문서 문항 수)이 아니라 준비된 방향 수가 된다. 구현 첫 단계에서 운영 판을 읽기 전용으로 세어 기록한다.
- 공개 판 형식(대시보드 완료 기록 기준, 2026-11-11. 운영 DB 확인 전):
  옛 구조 — 병인론 261102_02(/3), 감염병리1 261104_02(map-tree-26110803), 사슬알균 261105_01(map-tree-26110901).
  새 구조 2(/4) — 리케차 261110_03. 아데노·폭스 261110_02는 /4 개인 시범(진행 중).
- 준비 전(available 아님) 문항은 Quiz Bank의 비활성 문항처럼 전체에서 뺀다.

### 계약

- 서버 `overview_data`(entry·목록 `/api/root-learning`·개요가 공유)에 `questionProgress` 필드를 더한다:
  `{total, unseen, recognized, retrieving, retained, reviewDue}`. 기존 `summary`·`plan` 필드와 의미는 그대로.
- 웹 `useRootCatalog`가 강의별로 `summary`와 `questionProgress`를 함께 보관한다. `rootRate(summary)`는 그대로(캘린더 칸·패널 불변).

### 호환성·보존

- DB 스키마·학습 사건·문항·공개 범위·Quiz Bank 계산 변경 없음. 읽기 계산만 더한다.
- 모아풀기(Quiz Bank만 섞음)·체크박스 규칙 불변. 캘린더 칸 막대·패널 학습률 불변.

## Implementation Plan

순서:

1. 서버 `server/app/root_learning/state.py`: `question_progress(doc, events, available, now, policy, plan)` 추가.
   /4는 `replay_tasks`의 과제 값, 그 전 판은 `replay`의 방향 값 + 방향의 첫 준비 문항. 이틀 조건은 사건에서 과제·방향별 Good/Easy 학습일을 모은다.
   `server/app/routes/root_learning.py` `overview_data`에 `questionProgress` 한 줄.
2. 서버 검사 `server/tests/test_root_question_progress.py`(새 파일, 격리 SQLite·고정 시각):
   미열람/인지/인출/저장 경계, 이틀 조건, 목표 없는 옛 평가, 감쇠로 저장→인출, 복습 수 = 계획의 `복습 확인` 수, 미열람은 복습 0,
   준비 전 제외, 옛 판 방향당 한 문항, 합 = 전체.
3. 웹 `web/src/types/rootLearning.ts`(필드 타입), `web/src/bank/useRootCatalog.ts`(값 보관),
   `web/src/bank/StudyOverview.tsx`: `MainQuizCells` 삭제 → Main-Quiz 행도 기존 숫자 칸으로 그림. 상단 합계·단계 막대·「오늘 복습」에 더함.
   `web/src/bank/overview.css`: `list-main-quiz`·`list-main-bar` 규칙 삭제.
4. 웹 검사 `web/tests/study-blocks.test.cjs`: Main-Quiz 행에 배지·문장·막대 없음, 열 숫자, 상단 합계 포함. typecheck·build.
5. 격리 fixture로 데스크톱 1360·휴대폰 390 화면 확인(가로 넘침 없음·페이지 오류 0).
6. 운영 감염병리1 판 읽기 전용 집계(쓰기 0)로 전체 문항 수 확인해 이 기록에 남김.

검사 명령: 서버 `-m pytest tests`(격리 DB), `npm run typecheck`, `npm run build`, `node web/tests/study-blocks.test.cjs`, root-ui 검사.
성공 조건: 위 검사 통과, 합 = 전체, 화면에 배지·문장·막대 없음.

### 위험·승인할 범위

- 목록 요청(`/api/root-learning`)에 강의당 계산이 조금 늘어난다(이미 재생하는 사건을 한 번 더 셈). 측정해 기록.
- 학습률 열 정의는 바꾸지 않는다. 오정빈 검토 결론이 나면 별도 변경.
- 승인 범위: 위 파일, 웹·서버 읽기 계산. 병합(=배포)은 별도 승인.

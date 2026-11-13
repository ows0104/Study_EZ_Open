# 강의별 족보 풀이 자료(jokbo-solve/1)

## 만들기

```bash
python -m runner.jokbo_solve build            # 산출물 다시 만들기
python -m runner.jokbo_solve status           # 세트별 해설 빠진 문항 수
python -m runner.jokbo_solve pack <setId>     # 해설 작성 입력
python -m runner.jokbo_solve check <setId>    # 한 세트의 해설·소속 검사
```

기본 입력: `~/amgi`(족보 세트·그림), `data/timetable/2026_본1_2학기_시간표.json`,
`~/SynologyDrive/감염과 면역/필기/2026`(올해 교수 확인용 파일명).
산출물: 원래 저장소의 `runs/_materials/감염과 면역/jokbo-solve/` (worktree에서 돌려도 같은 곳).

```
jokbo-solve/
  explain/<setId>.json     해설(사람·모델이 쓴 자산, 빌드가 건드리지 않음)
  assign/<setId>.json      묶음 세트(7-8, 25-28) 문항의 강의 소속
  2026-1/                  빌드 산출물(매번 새로 만듦)
    index.json             강의 목록·문항 수·구획별 수·해설 수·답 없음·의심 수
    lectures/<eventId>.json  강의 하나 = 파일 하나 (jokbo-solve/1)
    figures/               문항 그림
```

## 강의 붙이기

- 세트의 강의 번호 = 시간표 「감염과 면역 N」. CBL·TBL·실습 세트는 세트 제목으로 대조한다.
- 강의 키는 시간표 칸 id(`eventId`)이고 `runId`(YYMMDD_NN)는 시작 시각에서 정한다
  (교시 = 시 − 8). amgi 필기 지도의 run_id와 다르면 빌드가 멈춘다.
- 패널의 「강의 16」(헤모필루스)은 시간표 「감염과 면역 18」이다 — 화면 번호가 아닌 `eventId`·`runId`로 찾는다.

## 같은 교수 / 다른 교수

- 올해 교수: 올해 필기 파일명 → (없으면) 시간표. CBL·TBL·실습은 분반이라 `none`.
- amgi 구획(연도별 출제 교수)을 올해 교수로 다시 판정한다.
  `same` 한 명 이상 겹침(공동 담당 포함) → `other` 겹치지 않는 알려진 교수 → `unknown` 미상.
- 구획 순서는 same → other → unknown, 각 안에서 최신 연도부터. 문항 배열도 이 순서다.

## 문항

| 필드 | 뜻 |
|---|---|
| `answers`, `answerMode`, `selectCount` | 답안지 답. `one_of` 인정 답 중 하나, `all_of` 전부 |
| `answerStatus` | `key` · `key-multiple`(복수 인정) · `all-correct`(전원 정답) · `missing`(채점 제외) |
| `verification` | 원천의 검수 상태 그대로(대부분 `pending` = 답안지 그대로) |
| `repeatYears` | 같은 문항이 다시 나온 해 |
| `figures` | `figures/` 안의 그림 |
| `explanation` | `text`, `choiceNotes`(선지별), `caution`, `basis`(`notes`+쪽 / `knowledge`), `answerCheck`(`agree`·`doubt`·`no-key`), `proposedAnswers`(답 없는 문항만), `source`(`studyez`·`amgi`) |

계약: `studyez_contracts/jokbo/solve.py`. 해설 작성 규칙: [explain-guide.md](explain-guide.md).

## 풀이 방식 — 사용자 결정(2026-11-13)

처음 의견은 「한 번에 풀고 끝에서 채점」이었으나 사용자가 **복습 퀴즈처럼 한 문제씩**으로 정했다.

> 족보를 한번에 다 풀면 처음에 헷갈렸던 게 뭔지 잘 기억이 안나서 맞기만 하면 그냥 넘어가게 되더라고.
> 어차피 실전연습이 아니라 족보문제를 다 외우는 게 목표라 별로 상관없을 거 같아.

- 고르면 바로 정답·선지별 해설·주의·교정 기록이 나온다. all_of 문항만 정한 개수를 고른 뒤 확인한다.
- 끝에서 맞힘·틀림·답 없음을 세고 「틀린 문제 다시」로 틀린 것만 한 문제씩 다시 푼다.
- **채점 기록 방식(복습 퀴즈와 같게 / 더 단순하게)은 아직 정하지 않았다.** 지금은 서버에 아무 기록도 남기지 않는다.

## 사이트

- 강의 패널 「복습」 아래 「족보」 칸: `▶ 족보 퀴즈 N`, 같은 교수·다른 교수 수. 시간표 칸에 붙어 필기가 없는 칸에도 선다
  (`web/src/calendar/JokboAction.tsx`). 족보가 없는 칸에서는 칸이 없다.
- 진입 화면 `/jokbo/<eventId>`(`web/src/jokbo/JokboPage.tsx`): 「같은 교수만」·「다른 교수까지」. 「다른 교수까지」면
  「전체」와 같은 교수가 아닌 연도 버튼(「2020 석승혁」, 교수를 모르면 「2020 교수 미상」)이 서고 하나씩 또는 전체로 고른다.
  같은 교수 문항이 없는 강의(교수 변경·CBL)는 처음부터 「다른 교수까지」·전체다. 고른 범위는 브라우저에 기억한다.
- 서버 `server/app/routes/jokbo.py`: R2 `jokbo-solve/<eventId>.json`·`jokbo-solve/figures/<이름>`. DB 표 없음.
  러너가 `python -m runner.jokbo_solve upload`로 올리고 서버가 계약·그림 존재를 다시 검사한다.
  기본 `--audience admin`(관리자에게만), 학생 공개는 `--audience all`로 다시 올린다.

## 중복·변형 — 사용자 결정(2026-11-13)

사용자 「둘 다 실행해줘」: 완전히 같은 문제는 합치고, 선지 한두 개만 바뀐 변형은 따로 두되 이어서 낸다.

- 강의 한 편 안에서 판정한다(`runner.jokbo_solve.merge_duplicates`). 발문 유사도는 공백을 뺀 글자 비교다.
  - **중복**: 유사도 ≥ 0.9, 선지 집합 같음(순서는 달라도 됨). 대표(답안지 답 있음 → 최신 연도) 하나만 남기고
    `years`(나온 해 전부)·`mergedFrom`(사본의 연도·번호·대표 선지 번호로 옮긴 답)을 단다. 사본 답이 대표와 다르면 `keyConflict`.
    같은 교수가 낸 해가 하나라도 있으면 같은 교수 구획에 둔다. 연도 버튼은 나온 해 어느 것을 골라도 들어간다.
  - **변형**: 유사도 ≥ 0.9, 공통 선지 ≥ 3, 다른 선지 ≤ 4(양쪽 합). 같은 `variantGroup`. 풀이 순서에서 처음 나온 자리에 모아
    이어서 내고, 둘째부터 앞 문제와 달라진 선지에 「바뀜」 표시.
  - **애매**: 유사도 0.8~0.9 또는 그 밖의 비슷한 쌍 → `2026-1/review-duplicates.json`.
- 사람·검토 세션의 쌍별 판정 `jokbo-solve/duplicates.json`(`duplicate`·`variant`·`distinct` + `note`)이 기계 판정보다 앞선다.

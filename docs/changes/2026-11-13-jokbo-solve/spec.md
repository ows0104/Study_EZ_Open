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

## 풀이 방식 의견

**권장: 강의별 세트를 한 번에 풀고 끝에서 채점하는 방식(amgi와 같음)을 기본으로 하고, 채점 뒤 틀린 문항만 한 문제씩 다시 푼다.**

- 족보는 「이 강의에서 무엇이 나오나」를 한 번에 보는 자료다. 강의당 5~34문항이라 한 화면에서 끝나고,
  같은 교수 → 다른 교수 구획이 한눈에 보여야 「올해 교수가 무엇을 물었나」가 드러난다.
  한 문제씩 넘기면 구획 경계와 반복 연도가 흐려진다.
- 실제 시험처럼 답을 미리 보지 않고 다 푼 뒤 맞춰 보는 것이 족보를 쓰는 목적(실전 점검)에 맞다.
  한 문제씩 즉시 정답을 보면 다음 문항이 앞 문항 해설에 기대 풀린다(같은 주제 연속 출제가 흔하다).
- 해설은 문항·선지가 길어 채점 뒤 펼쳐 읽는 쪽이 낫다. 복습 퀴즈의 한 문제씩 흐름은
  짧은 회상 카드에 맞춘 것이라 족보 해설 길이에는 맞지 않는다.
- 다만 복습 퀴즈의 장점(틀린 것 반복)은 살린다: 채점 뒤 「틀린 문항만 다시」를 한 문제씩으로.
  답 없음(`missing`)·전원 정답은 점수에서 빼고, `doubt` 문항은 채점 뒤에만 표시한다.

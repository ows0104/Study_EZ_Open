# 핸드오프: 「오늘 복습」 하루 목표를 문제 수로 환산

상태: **미착수 · 설계 결정 필요**. 2026-11-13 사용자 지시로 이번에는 문서만 남긴다(구현은 `2026-11-13-review-count-card`가 하지 않음).

## 사용자 지시 원문 (2026-11-13)
- 「남은 복습을 %p가 아니라 문제 수로 바꾸고 싶은데」
- 「이 바가 reviewDue를 의미하는 게 아니라, 시험까지 남은 날짜를 기준으로 하루에 풀어야 하는 문제의 수를 계산해서 보여주는 건데.
  문제 수로만 환산해서 나타내달라는 거야.」
- 「하루 목표 수를 문제 수로 바꾸는 것에 대해서 핸드오프 문서를 작성해줘. 우선 지금은 -로 안 뜨게 수정하고, 내가 푼 문제 수를 같이 표시해줘.」

**`reviewDue`(오늘 복습할 차례인 문항 수)로 바꾸는 것이 아니다.** 지금 칸의 하루 목표(시험까지 남은 날로 나눈 확보량)를 그대로 두고 단위만 문제로.

## 지금 상태
- 칸: `web/src/calendar/CalendarPage.tsx` `ReviewCard`. 큰 수 = `plans[0].remainingGain`(%p), 막대 = `progressPercent`,
  2026-11-13부터 「푼 문제 n」 = `reviewedToday`.
- 데이터: `GET /api/study-plan?target=` → `server/app/routes/study_plan.py` `build_study_plan` → `study_engine/planning.py` `daily_plan`.
  - `requiredGain`: 오늘 확보할 %p(아침 기준 고정). `remainingGain`: 남은 %p. `earnedGain`: 오늘 평가로 얻은 %p. `met`.
  - `reviewedToday`: 그 시험 강의들의 오늘(새벽 4시) `rate` 이벤트 수(Z로 되돌린 평가 제외, `content.events_for`).
- 경위: 11-11 `today-progress`(9e417996)가 칸을 「N문제」(Quiz Bank `reviewDue`)에서 %p로 바꾸며 `useTodayDue`를 지웠다.
  같은 날 `main-quiz-learning-rate`가 계획한 「`useTodayDue`를 Main-Quiz로」는 고칠 자리가 없어져 적용되지 않았다.
- 운영에서 칸이 「–」인 까닭은 별개: 11/20·11/27 시험 칸 제목이 「시험」뿐이라 `plans`가 비었다 → `2026-11-13-immunity-exam-titles`.

## 왜 어려운가
학습률은 문항 숙련도(지수 평균, Good 한 번 ≈ 목표치의 40%) → 망각 곡선 → 목표별 1−RMS → 강의별 1−RMS(`total_score`)로 쌓인다.
문제 하나가 주는 %p는 문항·강의의 현재 수준과 시각에 따라 다르다. 정확한 「N문제」는 없고 추정 방법을 골라야 한다.

## 후보
| 안 | 방법 | 장점 | 단점 |
|---|---|---|---|
| A. 내 지난 기록 비율 | 어제부터 최대 7학습일, 평가 ≥ 10회인 가장 최근 날의 (그날 확보 %p ÷ 그날 평가 수)로 나눈다. 없으면 오늘 값, 그것도 없으면 %p 유지 | 실제 기록 기반, 하루 동안 목표가 고정 | 날마다 값이 바뀜, 첫 사용자는 환산 불가 |
| B. 모의 평가 | 오늘 계획 과제를 계획 순서대로 Good 처리한 가상 이벤트로 점수를 다시 계산, 목표에 닿는 개수를 센다 | 모델에 가장 충실 | 가상 `rate` 페이로드(grade·policy·targetParameters·question_sha256 등)를 지어야 해 깨지기 쉽고, 매우 느림 |
| C. 모델 평균 | 1회 Good ≈ 목표치의 40% × (100 ÷ 시험 범위 문항 수)로 나눈다 | 빠르고 안정 | RMS를 무시한 거친 근사 |

2026-11-13 세션의 제안은 A였다. 초안: `gainPerQuestion` = 위 g, `goalQuestions` = ceil(`requiredGain` ÷ g),
`remainingQuestions` = `met`이면 0, 아니면 ceil(`remainingGain` ÷ g). 사용자 결정 전.

## API가 느려지나
- 「푼 문제 n」 표시: **아니다.** `reviewedToday`는 원래 계산되던 값이고, 웹이 그리기만 한다.
- 환산(A): **느려진다.** 지금 `daily_plan`은 강의마다 `lecture_score`(이벤트 전체 재생)를 4번 부른다(아침·아침 기준 하루 끝·현재·현재 기준 하루 끝).
  A는 조사하는 날마다 강의당 2번을 더한다 → 어제 기록이 있으면 약 +50%, 7일을 다 뒤지면 최대 약 +350%.
  `/api/root-learning`은 운영에서 이미 6.5–8.8 s(2026-11-12 기록)라 같은 무게의 계산을 늘리는 것은 조심해야 한다.
  - 줄이는 길: g를 (사용자·시험·학습일)마다 한 번 계산해 캐시, 또는 이미 계산되는 아침 값과 전날 계산값을 저장해 재사용.
- B는 문항 하나마다 재계산이라 훨씬 느리다. C는 거의 공짜다.

## 손댈 곳(예상)
- `server/app/study_engine/planning.py`, `server/app/routes/study_plan.py`(필드 `gainPerQuestion`·`goalQuestions`·`remainingQuestions`)
- `server/tests/test_study_plan.py`
- `web/src/types/studyPlan.ts`, `web/src/calendar/CalendarPage.tsx` `ReviewCard`(큰 수 = 남은 문제, 막대 = 푼 문제 ÷ 목표 문제), `web/src/notices/GuidePage.tsx`
- 같은 값을 쓰는 「시험까지 오늘의 학습 목표」판(`StudyPlanBoard`)도 문제 수로 맞출지 함께 정한다.

## 시작 전 결정할 것
1. 환산 방법(A·B·C).
2. 기록 부족 때 표시(%p 유지 / 「–」).
3. 응답 시간 허용치와 캐시 여부.

# 구현 계획

승인: 사용자 요청(2026-11-14) 자체가 이 범위의 구현 지시. master 병합(=자동 배포)은 별도 승인.

## 파일

1. `server/app/root_learning/score.py`: `lecture_score(..., target_scale=1.0)`, `DISPLAY_TARGET_SCALE = 0.5`.
2. `server/app/lecture_mastery.py`(시간표 학습률), `server/app/root_learning/state.py`(목록 요약): 보이는 값이므로 `DISPLAY_TARGET_SCALE`.
   `routes/study_plan.py`는 기본값 1 그대로.
3. `web/src/calendar/shownGoal.ts`: 계획의 requiredGain·netGain·forgettingLoss를 절반, endTarget은 아침 끝 + 절반 목표,
   남은 양·완료·진행률은 같은 확보량을 절반 목표에 대어 다시 계산. `useTodayPlan.ts`·`StudyPlanBoard.tsx`가 쓴다.
4. 안내 문구: GuidePage·LectureMastery·StudyPlanBoard 설명.
5. `server/tests/test_root_score.py`: 표시 기준 절반, 계획 기준 그대로.

## 위험·복원

- 병합 즉시 모든 사용자의 보이는 학습률이 오르고(100에서 자름) 오늘 목표가 절반으로 보인다.
- 복원은 두 상수(`DISPLAY_TARGET_SCALE`, `SHOWN_GOAL_SCALE`)를 1로 되돌리거나 `git revert`.

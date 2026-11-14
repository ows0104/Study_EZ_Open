import type { ExamPlan } from "../types/studyPlan";

/** 화면에 보이는 오늘 목표(%p)는 계획 값의 이 비율이다(2026-11-14 사용자 「표기되는 학습률 목표를 현재의 50%로」, 「보이는 것만」). */
export const SHOWN_GOAL_SCALE = 0.5;

const tenth = (value: number) => Math.round(value * 10) / 10;

/**
 * 서버 계획(`/api/study-plan`)은 그대로 두고 보이는 오늘 목표만 줄인다.
 * 확보량(requiredGain − remainingGain)은 같고, 목표가 절반이 되므로 진행률·완료 표시가 그만큼 빨리 찬다.
 * 학습률 값(morning·current·projected·target)은 바꾸지 않는다.
 */
export function shownGoal(plan: ExamPlan): ExamPlan {
  const goal = plan.requiredGain * SHOWN_GOAL_SCALE;
  const earned = Math.max(0, plan.requiredGain - plan.remainingGain);
  const remaining = Math.max(0, Math.ceil((goal - earned) * 10 - 1e-9) / 10);
  const met = plan.met || remaining <= 0;
  return {
    ...plan,
    requiredGain: tenth(goal),
    netGain: tenth(plan.netGain * SHOWN_GOAL_SCALE),
    forgettingLoss: tenth(plan.forgettingLoss * SHOWN_GOAL_SCALE),
    endTarget: tenth(plan.endTarget - plan.requiredGain * (1 - SHOWN_GOAL_SCALE)),
    remainingGain: met ? 0 : remaining,
    met,
    progressPercent: met ? 100 : goal > 0 ? Math.min(99, Math.max(0, Math.floor(earned / goal * 100))) : 0,
  };
}

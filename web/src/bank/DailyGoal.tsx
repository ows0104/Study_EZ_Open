import type { LectureGoal } from "../types/studyPlan";
import "../styles/mastery.css";

/** 현재 강의만의 마침점. 달력의 시험 전체 목표와 구별한다. */
export function DailyGoal({ plan, showMain = false, collapsible = false }: {
  plan?: LectureGoal | null; showMain?: boolean; collapsible?: boolean;
}) {
  if (!plan) return null;
  const heading = <div className="mastery-heading" role="status">
      {plan.met && showMain ? <h2>오늘 학습할 내용을 완료하였습니다!</h2>
        : <strong>{plan.met ? "✓ 오늘 학습할 내용을 완료하였습니다!" : `완료까지 ${plan.remaining}개 남았어요`}</strong>}
      <span>{plan.total}개 중 {plan.completed}개 완료</span>
    </div>;
  const contents = <>
    <progress className="daily-goal-progress" max={100} value={plan.progressPercent} aria-label="이 강의의 오늘 목표 진행률" />
    <p>{plan.met ? "수고하셨습니다. 오늘 쌓은 학습을 마무리하고 잠시 쉬어 가세요."
      : `처음 학습 ${plan.newRemaining}개 · 복습 ${plan.reviewRemaining}개 · 다시 확인 ${plan.relearningRemaining}개`}</p>
    <small>{plan.title} · 오늘 응답 {plan.reviewedToday}회 · {plan.scope === "core" ? "핵심·선행" : "전체"} 학습 단위 기준</small>
    <small>처음부터 한 번씩 확인한 범위 {plan.firstPassSeen} / {plan.firstPassTotal}개</small>
    {plan.met && showMain ? <p><a className="daily-goal-main" href="/">메인으로 돌아가기</a></p> : null}
    <details>
      <summary>이 강의의 완료 기준</summary>
      <p>핵심 개념과 회상 방향이 같으면 한 학습 단위로 셉니다. 필요한 선행 내용도 포함합니다.
        핵심 문항이 없는 강의는 전체 문항의 학습 단위를 사용합니다.</p>
      <p>처음에는 각 단위를 확인하고, 이후에는 오늘 복습 예정인 단위를 학습합니다.
        Good·Easy는 오늘 완료, Again·Hard는 잠시 뒤 다시 확인합니다. 다시 틀리면 남은 수가 늘 수 있습니다.</p>
      <p>모든 오늘 학습 단위를 처리하면 완료됩니다. 반복 응답 횟수와 남은 학습 단위 수는 다릅니다.
        숙련도와 시험 대비 계획은 별도 지표이며, 한국 자정을 기준으로 오늘 분량을 갱신합니다.</p>
    </details>
  </>;
  const className = `daily-goal${plan.met ? " is-complete" : ""}`;
  return collapsible ? <details className={`${className} daily-goal-collapsible`} aria-label="이 강의의 오늘 목표">
    <summary aria-label="오늘 학습 현황">
      {heading}
      <svg className="daily-goal-chevron" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true"><path d="m4 6 4 4 4-4" /></svg>
    </summary>
    {contents}
  </details> : <section className={className} aria-label="이 강의의 오늘 목표">
    {heading}{contents}
  </section>;
}

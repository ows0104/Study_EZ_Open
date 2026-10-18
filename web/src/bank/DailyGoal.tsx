import type { LectureGoal } from "../types/studyPlan";
import { Link } from "react-router-dom";
import "../styles/mastery.css";

/** 현재 강의만의 마침점. 달력의 시험 전체 목표와 구별한다. */
export function DailyGoal({ plan, showMain = false, collapsible = false, onContinue, busy = false }: {
  plan?: LectureGoal | null; showMain?: boolean; collapsible?: boolean;
  onContinue?: () => void; busy?: boolean;
}) {
  if (!plan) return null;
  const heading = <div className="mastery-heading" role="status">
      {plan.met && showMain ? <h2>새 카드와 오늘 복습 완료!</h2>
        : <strong>{plan.met ? "✓ 오늘 학습 완료" : `오늘 ${plan.remaining}문항 남았어요`}</strong>}
      <span>{plan.completed} / {plan.total} 완료</span>
    </div>;
  const contents = <>
    <progress className="daily-goal-progress" max={100} value={plan.progressPercent} aria-label="이 강의의 오늘 목표 진행률" />
    {plan.met && showMain ? <div className="daily-goal-celebration">
      <div className="daily-goal-check" aria-hidden="true">✓</div>
      <p>{plan.total > 0 ? `오늘 분량 ${plan.total}문항을 모두 해냈어요.` : "오늘 예정된 학습을 모두 마쳤어요."}</p>
      {plan.unlearnedRemaining ? <p className="daily-goal-message">미학습 {plan.unlearnedRemaining}문항은 다음날 학습하거나 지금 이어서 풀 수 있어요.</p> : null}
      <p className="daily-goal-message">다른 강의를 선택하거나 이 강의를 이어서 공부할 수 있어요.</p>
      <div className="daily-goal-actions">
        <Link className="daily-goal-main" to="/">다른 강의 학습하러 가기 <small>Main 캘린더로</small></Link>
        {onContinue ? <button className="daily-goal-continue" disabled={busy} onClick={onContinue}>
          {busy ? "여는 중…" : "이 강의 더 공부하기"}
        </button> : null}
      </div>
    </div> : null}
    <details>
      <summary>학습 현황 자세히</summary>
      <p>오늘 신규 {plan.newRemaining}문항 · 복습 {plan.reviewRemaining}문항</p>
      <small>오늘 응답 {plan.reviewedToday}회 · 한 번 이상 학습한 문항 {plan.firstPassSeen} / {plan.firstPassTotal}</small>
      <p>오늘 목표는 이 강의의 모든 미학습 문항과 예정된 복습 문항입니다. 신규 문항 수에는 제한이 없습니다.</p>
      <p>미학습 문항을 모두 먼저 제시하고, 그다음 예정된 복습 문항을 제시합니다.
        같은 개념의 변형·심화·선택 문항도 각각 셉니다.
        아직 학습하지 않은 선행 문제가 있으면 먼저 확인합니다.</p>
      <p>각 문항을 확인하고 평가하면 오늘 분량에 반영합니다. 오늘 마치지 못한 미학습 문항은 다음날 목표로 이어집니다.
        Again·Hard로 평가한 내용은 다음날부터 복습에 반영합니다.</p>
      <p>오늘 신규 분량과 복습할 문항을 모두 처리하면 완료됩니다. 같은 문항을 반복해도 다른 문항의 남은 수가 줄지는 않습니다.
        추가 학습에서 어려운 내용이 나와도 오늘 달성한 분량은 유지됩니다.
        숙련도와 시험 대비 계획은 별도 지표이며, 한국 시간 오전 4시를 기준으로 오늘 분량을 갱신합니다.</p>
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

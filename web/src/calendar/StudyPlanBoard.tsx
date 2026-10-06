import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "../api";
import type { StudyPlan } from "../types/studyPlan";
import { useStudyTarget } from "./useStudyTarget";
import "../styles/mastery.css";

export function StudyPlanBoard() {
  const [target, setTarget] = useStudyTarget();
  const [data, setData] = useState<StudyPlan | null>(null);
  const [error, setError] = useState("");
  const [unavailable, setUnavailable] = useState(false);
  const [refresh, setRefresh] = useState(0);
  const reload = useCallback(() => setRefresh(v => v + 1), []);
  useEffect(() => {
    let live = true;
    setData(null);
    setError("");
    api<StudyPlan>(`/api/study-plan?target=${target}`)
      .then(value => { if (live) { setData(value); setUnavailable(false); } })
      .catch((cause: Error) => {
        if (!live) return;
        if (cause instanceof ApiError && cause.status === 404) setUnavailable(true);
        else setError(cause.message);
      });
    return () => { live = false; };
  }, [target, refresh]);
  useEffect(() => {
    const tick = () => { if (document.visibilityState === "visible") reload(); };
    window.addEventListener("focus", reload);
    const timer = window.setInterval(tick, 5 * 60_000);
    return () => { window.removeEventListener("focus", reload); window.clearInterval(timer); };
  }, [reload]);
  if (unavailable) return null;
  return <section className="mastery-board study-plan-board" aria-label="시험까지 오늘의 학습 목표">
    <div className="mastery-heading">
      <h2>시험까지 오늘의 학습 목표</h2>
      <label>시험 목표 <select value={target} onChange={e => setTarget(Number(e.target.value))}>
        {[70, 80, 90, 95, 100].map(n => <option key={n} value={n}>{n}%</option>)}
      </select></label>
    </div>
    <p className="mastery-caption">예정 강의를 포함한 시험 범위 전체 기준 · 부족한 강의에 더 큰 비중 · 한국 시간</p>
    {error ? <p className="notice is-error">{error} <button onClick={reload}>다시 불러오기</button></p>
      : !data ? <p className="mastery-caption" role="status">오늘 목표를 계산하는 중…</p>
      : <>
        {data.plans.length ? data.plans.map(plan => <article className="exam-plan" key={plan.examId}>
          <div className="mastery-heading">
            <strong>{plan.title}</strong>
            <span className={`mastery-badge is-${plan.met ? "mastered" : "needs_review"}`}>
              {plan.met ? "오늘 목표 확보" : `오늘 더 확보할 학습량 +${plan.remainingGain.toFixed(1)}%p`}
            </span>
          </div>
          <progress className="daily-goal-progress" max={100} value={plan.progressPercent} aria-label={`${plan.title} 오늘 목표 진행률`} />
          <p className="mastery-caption">오늘 목표 {plan.progressPercent}% · 오늘 {plan.reviewedToday}문항 완료</p>
          <p className="mastery-caption">{plan.examDate} {plan.examTime} 시험
            · 전체 {plan.lectureCount}강의 · 오늘 신규 {plan.newToday} · 이후 예정 {plan.upcomingLectures}</p>
          <p className="mastery-caption">목표 도달일 {new Intl.DateTimeFormat("ko-KR", {
            timeZone: "Asia/Seoul", month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit", hourCycle: "h23",
          }).format(plan.studyDeadline)} · {plan.bufferPhase ? "복습·밀린 분량 보충 기간" : `목표일까지 ${plan.learningDaysLeft}일`}
            · 마지막 {plan.bufferDays}일은 여유 기간</p>
          <div className="study-plan-stats">
            <div><small>현재 전체 학습률</small><strong>{plan.currentScore.toFixed(1)}%</strong></div>
            <div><small>추가 학습 없이 {plan.horizon === plan.dayStart + 86_400_000 ? "자정" : plan.bufferPhase ? "시험 직전" : "목표 마감"}</small>
              <strong>{plan.projectedScore.toFixed(1)}%</strong></div>
            <div><small>오늘 끝 목표</small><strong>{plan.endTarget.toFixed(1)}%</strong></div>
          </div>
          <p className="mastery-caption">오늘 확보 목표 +{plan.requiredGain.toFixed(1)}%p
            ≈ 시험까지 순증가 +{plan.netGain.toFixed(1)}%p + 망각 보충 {plan.forgettingLoss.toFixed(1)}%p
            · 현재까지 확보 {plan.earnedGain >= 0 ? "+" : ""}{plan.earnedGain.toFixed(1)}%p</p>
          {plan.unassessedLectures ? <p className="mastery-caption">문제 미준비 {plan.unassessedLectures}강의는 계획상 0%로 가정한 예상치입니다.</p> : null}
          {plan.lateLectures > 0 ? <p className="study-plan-limit">목표 도달일 당일 또는 이후에 {plan.lateLectures}강의가 예정되어 있습니다.
            공개 시각에 따라 여유 기간에도 신규 학습이 필요할 수 있습니다.</p> : null}
          {plan.bufferPhase && plan.morningScore < plan.target ? <p className="study-plan-limit">목표일까지 확보하지 못한 분량이 남아 있습니다.
            남은 여유 기간에 나누어 보충하며, 오늘 목표가 평소보다 커질 수 있습니다.</p> : null}
          {plan.limitedByMaterials ? <p className="study-plan-limit">현재 공개된 문제만으로 가능한 상한은 {plan.availableCeiling.toFixed(1)}%입니다.
            미준비 강의가 있어 오늘 목표를 웹 풀이만으로 달성하기 어렵습니다.</p> : null}
        </article>) : <p className="mastery-caption">시간표에서 과목과 범위를 연결할 수 있는 예정 시험이 없습니다.</p>}
        {data.unmatchedExams.length ? <p className="mastery-caption">범위 확인 필요: {data.unmatchedExams.join(" · ")}</p> : null}
        <details className="study-plan-help"><summary>목표 계산 기준</summary>
          <p>같은 과목의 다음 시험까지를 범위로 자동 추정합니다. 실제 시험 범위가 다르면 목표도 달라집니다.
            예정 강의를 분량에 미리 포함하므로, 신규 강의가 공개되기 전에도 해야 할 학습량에 반영됩니다.</p>
          <p>시험 3일 전까지 목표에 도달하도록 계획합니다. 현재 기록에서 추정한 하루 학습률 유지 비율을 바탕으로,
            망각 보충까지 합친 하루 확보량이 고르게 되도록 초반 순증가 목표를 높입니다. 기록이 없으면 하루 90% 유지를 가정합니다.</p>
          <p>마지막 3일은 목표 수준 유지와 밀린 분량 보충에 씁니다. 목표는 한국 자정 기록으로 계산하고 현재 기록으로 남은 분량을 갱신합니다.
            목표 도달 시각부터는 복습 계획으로 전환하며, 시험 당일에는 시험 시작 시각이 마감입니다.</p>
          <p>‘확보’는 오늘 끝 시점에도 남을 것으로 추정되는 학습률 증가분입니다. 목표·자료·시간표가 바뀌면 다시 계산합니다.
            문제 수나 공부 시간의 보장치는 아니며, 앞으로의 복습에 따라 망각량도 달라집니다.</p>
        </details>
      </>}
  </section>;
}

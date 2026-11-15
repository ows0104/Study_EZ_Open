import type { LectureMastery as Mastery, MainQuizRate } from "../types/mastery";
import "../styles/mastery.css";

export const masteryLabels = {
  not_started: "미학습",
  needs_review: "복습 필요",
  mastered: "목표 달성",
};

export function MasteryBadge({ value }: { value: Mastery | MainQuizRate | null | undefined }) {
  return <span className={`mastery-badge is-${value?.status ?? "unavailable"}`}>
    {value ? `${masteryLabels[value.status]} · ${value.score}%` : "평가 준비 전"}
  </span>;
}

/** 강의 페이지의 학습률. 사이트 학습률은 Main-Quiz 하나다(2026-11-11). */
export function MainQuizMastery({ value }: { value: MainQuizRate | null | undefined }) {
  if (value === undefined) return null;
  return <section className="lecture-mastery" aria-label="내 강의 학습률">
    <div className="mastery-heading"><strong>내 강의 학습률</strong><MasteryBadge value={value} /></div>
    {value ? <>
      <progress max={100} value={value.score} aria-label={`강의 학습률 ${value.score}%`} />
      <p>지도 목표 {value.fullTargets}/{value.targetCount}개 목표 달성</p>
      <details className="mastery-details">
        <summary>학습률 자세히</summary>
        <small>Main-Quiz 평가 기준 · 평가한 목표 {value.ratedTargets}/{value.targetCount}개.
          문항마다 지금 숙련도를 목표치의 절반으로 나눈 부분 점수를 지도 목표별로 모읍니다.
          마지막 평가 이후 시간이 지나면 서서히 낮아지고, 덜 익힌 목표를 더 크게 반영합니다.</small>
      </details>
    </> : <p>Main-Quiz가 열리면 풀이 기록으로 평가합니다.</p>}
  </section>;
}

/** Legacy Quiz Bank 학습도. `?legacy=1` 은행 화면에서만 보인다. 사이트 학습률에 들어가지 않는다. */
export function LectureMastery({ value }: { value: Mastery | null | undefined }) {
  // 이전 API가 아직 배포되어 있는 경우에는 잘못된 준비 상태를 표시하지 않는다.
  if (value === undefined) return null;
  return <section className="lecture-mastery" aria-label="옛 Quiz Bank 학습도">
    <div className="mastery-heading"><strong>옛 Quiz Bank 학습도</strong><MasteryBadge value={value} /></div>
    {value ? <>
      <progress max={100} value={value.score} aria-label={`강의 학습도 ${value.score}%`} />
      <p>{value.scope === "core" ? "핵심" : "전체"} 개념 {value.masteredConcepts}/{value.conceptCount}개 목표 달성</p>
      <details className="mastery-details">
        <summary>학습도 자세히</summary>
        {value.weakest.length > 0 ? <p>먼저 복습할 개념: {value.weakest.map(c => c.title).join(" · ")}</p> : null}
        <small>옛 Quiz Bank 기록이며 사이트 학습률에는 포함되지 않습니다. Quiz Bank 회상 평가 기준 · 회상 방향 {value.assessedDirections}/{value.totalDirections}개 평가.
          마지막 학습 이후의 시간과 복습 이력을 반영한 추정 학습도이며, 시간이 지나면 감소합니다.
          학습이 부족한 개념을 더 크게 반영해, 여러 개념을 고르게 익힐수록 높아집니다.
          Anki·기존 카드 기록은 포함하지 않습니다.</small>
      </details>
    </> : <p>Quiz Bank 문제가 준비되면 풀이 기록으로 평가합니다.</p>}
  </section>;
}

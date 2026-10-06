import type { LectureMastery as Mastery } from "../types/mastery";
import "../styles/mastery.css";

export const masteryLabels = {
  not_started: "미학습",
  needs_review: "복습 필요",
  mastered: "목표 달성",
};

export function MasteryBadge({ value }: { value: Mastery | null | undefined }) {
  return <span className={`mastery-badge is-${value?.status ?? "unavailable"}`}>
    {value ? `${masteryLabels[value.status]} · ${value.score}%` : "평가 준비 전"}
  </span>;
}

export function LectureMastery({ value }: { value: Mastery | null | undefined }) {
  // 이전 API가 아직 배포되어 있는 경우에는 잘못된 준비 상태를 표시하지 않는다.
  if (value === undefined) return null;
  return <section className="lecture-mastery" aria-label="내 강의 학습도">
    <div className="mastery-heading"><strong>내 강의 학습도</strong><MasteryBadge value={value} /></div>
    {value ? <>
      <progress max={100} value={value.score} aria-label={`강의 학습도 ${value.score}%`} />
      <p>{value.scope === "core" ? "핵심" : "전체"} 개념 {value.masteredConcepts}/{value.conceptCount}개 목표 달성</p>
      <details className="mastery-details">
        <summary>학습도 자세히</summary>
        {value.weakest.length > 0 ? <p>먼저 복습할 개념: {value.weakest.map(c => c.title).join(" · ")}</p> : null}
        <small>Quiz Bank 회상 평가 기준 · 회상 방향 {value.assessedDirections}/{value.totalDirections}개 평가.
          마지막 학습 이후의 시간과 복습 이력을 반영한 추정 학습도이며, 시간이 지나면 감소합니다.
          학습이 부족한 개념을 더 크게 반영해, 여러 개념을 고르게 익힐수록 높아집니다.
          Anki·기존 카드 기록은 포함하지 않습니다.</small>
      </details>
    </> : <p>Quiz Bank 문제가 준비되면 풀이 기록으로 평가합니다.</p>}
  </section>;
}

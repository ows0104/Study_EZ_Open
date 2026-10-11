import type { LectureRef } from "../types/lectures";

const labels = {
  not_started: "미학습",
  needs_review: "복습 필요",
  mastered: "목표 달성",
};

type Phase = "pre" | "main";
type Progress = { score: number | null; description: string; unknown?: boolean };
const phaseLabels = { pre: "예습", main: "복습" };
const clampScore = (score: number) => Math.max(0, Math.min(100, score));

function progressFor(lecture: LectureRef, phase: Phase): Progress {
  if (phase === "pre") {
    const progress = lecture.prequizProgress;
    if (!lecture.marks.prequiz || !progress || progress.total <= 0) {
      return { score: null, description: "예습: 측정할 웹 문항 없음" };
    }
    const answered = Math.max(0, Math.min(progress.total, progress.answered));
    const score = clampScore(100 * answered / progress.total);
    return { score, description: `예습 ${formatScore(score)}% · ${answered}/${progress.total}문항 완료` };
  }
  if (!lecture.marks.quiz) return { score: null, description: "복습: 측정할 웹 문항 없음" };
  const learned = lecture.learningProgress;
  if (learned && learned.total > 0) return { score: clampScore(100 * learned.covered / learned.total),
    description: `학습 범위 ${learned.covered}/${learned.total}${learned.legacyObjectives ? "문항" : "요점"} · 지연 회상 ${learned.delayedRecall}요점` };
  const value = lecture.mastery;
  if (value === undefined) return { score: null, unknown: true, description: "복습: 학습도 정보 없음" };
  if (value === null) return { score: null, description: "복습: 평가 준비 전" };
  return { score: clampScore(value.score), description: `복습 학습도 ${value.score}% · ${labels[value.status]}` };
}

// 99.9%를 반올림해 100% 완료로 보이게 하지 않는다.
function formatScore(score: number) { return score >= 100 ? 100 : Math.floor(score); }
function progressClass(progress: Progress) {
  return progress.score === null ? progress.unknown ? "is-unknown" : "is-unavailable"
    : progress.score >= 100 ? "is-complete" : "is-progress";
}

export function learningDescription(lecture: LectureRef) {
  return `${lecture.title}: ${progressFor(lecture, "pre").description} · ${progressFor(lecture, "main").description}`;
}

/** 왼쪽 예습 풀이율 · 오른쪽 Quiz Bank 학습도. 두 영역은 항상 같은 폭이다. */
export function ChipLearning({ lectures }: { lectures: LectureRef[] }) {
  if (!lectures.length) return null;
  return <span className="chip-learning-pair">
    {(["pre", "main"] as const).map(phase => {
      const progress = lectures.map(lecture => progressFor(lecture, phase));
      const single = lectures.length === 1 ? progress[0] : null;
      const unavailable = progress.every(value => value.score === null && !value.unknown);
      const description = lectures.map((lecture, index) => `${lecture.title}: ${progress[index].description}`).join(" · ");
      return <span className={`chip-learning is-${phase}${unavailable ? " is-unavailable" : ""}`} key={phase} title={description} aria-label={description}>
        <span className="chip-learning-value" aria-hidden="true">
          <span className="chip-learning-label">{phase === "main" && lectures.some(l => l.learningProgress) ? "범위" : phaseLabels[phase]} </span>
          {single ? single.score === null ? "—" : `${formatScore(single.score)}%` : null}
        </span>
        <span className="chip-learning-bars" aria-hidden="true">
          {progress.map((value, index) => <span key={JSON.stringify([lectures[index].subject, lectures[index].runId])}
            className={`chip-learning-track ${progressClass(value)}`}>
            {value.score !== null ? <span className="chip-learning-fill" style={{ width: `${value.score}%` }} /> : null}
          </span>)}
        </span>
      </span>;
    })}
  </span>;
}

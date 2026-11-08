import type { LectureRef } from "../types/lectures";
import { rootRate, useRootCatalog, type RootCatalog } from "../bank/useRootCatalog";
import { prequizDone } from "./entries";

/**
 * 칸 아래 학습 표시(2026-11 개편).
 *
 *   위 = 회독 줄: 학습률 막대와 같은 두께의 점선. 예습 퀴즈를 끝까지 풀었을 때만 첫 토막을 옅은 예습 색으로 채운다
 *        (예습은 1회독까지만 센다). 강의록 회독 토막은 서버 저장과 함께 2단계에서 붙는다.
 *   아래 = 복습 학습률 막대: 0%여도 바탕이 보이고, 덜 채울수록 진하다(덜 공부한 강의가 더 중요하다).
 *          아직 복습이 열리지 않았거나 불러오는 중이면 회색 바탕만.
 * 예습 학습률 막대는 없앴다(사용자 지시).
 */
const labels = {
  not_started: "미학습",
  needs_review: "복습 필요",
  mastered: "목표 달성",
};

type Review = { score: number | null; description: string };

function reviewFor(lecture: LectureRef, roots?: RootCatalog): Review {
  if (lecture.studyLoaded === false) return { score: null, description: "복습: 학습률 불러오는 중" };
  // Main-Quiz만 있는 강의: 회상 가능 목표 비율. 요약을 아직 못 받았으면 0%로 열어 둔다(강의 목록과 같은 정의).
  if (!lecture.marks.quiz && lecture.marks.mainQuiz) {
    const summary = roots?.get(`${lecture.subject}/${lecture.runId}`);
    const score = rootRate(summary) ?? 0;
    return { score, description: summary ? `Main-Quiz 학습률 ${score}% · 회상 가능 ${summary.recalled}/${summary.total}` : `Main-Quiz 학습률 ${score}%` };
  }
  if (!lecture.marks.quiz) return { score: null, description: "복습: 측정할 웹 문항 없음" };
  const value = lecture.mastery;
  if (value === undefined) return { score: null, description: "복습: 학습도 정보 없음" };
  if (value === null) return { score: 0, description: "복습 학습률 0% · 평가 준비 전" };
  const score = Math.max(0, Math.min(100, value.score));
  return { score, description: `복습 학습률 ${score}% · ${labels[value.status]}` };
}

function preFor(lecture: LectureRef) {
  if (lecture.studyLoaded === false) return "예습: 불러오는 중";
  const progress = lecture.prequizProgress;
  if (!lecture.marks.prequiz || !progress || progress.total <= 0) return "예습: 웹 문항 없음";
  return prequizDone(lecture) ? "예습 퀴즈 완료" : `예습 퀴즈 ${Math.min(progress.answered, progress.total)}/${progress.total}`;
}

export function learningDescription(lecture: LectureRef, roots?: RootCatalog) {
  return `${lecture.title}: ${preFor(lecture)} · ${reviewFor(lecture, roots).description}`;
}

/** 채울수록 옅어지는 복습 막대. 채움 색 = 메인 색을 (100 − 학습률×62)%만큼 섞는다. */
export function ReviewMeter({ score, className = "" }: { score: number | null; className?: string }) {
  if (score === null) return <span className={`meter is-closed ${className}`} />;
  const strength = Math.round(100 - (score / 100) * 62);
  return (
    <span className={`meter ${className}`}>
      <span style={{ width: `${score}%`, background: `color-mix(in srgb, var(--accent) ${strength}%, var(--surface))` }} />
    </span>
  );
}

export function ChipLearning({ lectures }: { lectures: LectureRef[] }) {
  const roots = useRootCatalog(lectures.some(l => l.marks.mainQuiz && !l.marks.quiz));
  if (!lectures.length) return null;
  const reviews = lectures.map(l => reviewFor(l, roots));
  const description = lectures.map(l => learningDescription(l, roots)).join(" · ");
  const preOpen = lectures.some(l => l.marks.prequiz);
  const preDone = lectures.every(l => !l.marks.prequiz || prequizDone(l)) && preOpen;
  const single = lectures.length === 1 ? reviews[0] : null;
  return (
    <span className="chip-learning-pair" title={description} aria-label={description}>
      <span className="readline" aria-hidden="true">
        {preOpen ? <i className={`rl-pre${preDone ? " is-on" : ""}`} /> : null}
      </span>
      <span className="chip-learning is-main">
        {/* 화면에는 막대만 보이고, 숫자는 화면 낭독용으로 남긴다. */}
        <span className="chip-learning-value sr-only">
          복습 {single ? (single.score === null ? "—" : `${single.score}%`) : ""}
        </span>
        <span className="chip-learning-bars" aria-hidden="true">
          {reviews.map((review, index) => (
            <ReviewMeter key={`${lectures[index].subject}/${lectures[index].runId}`} score={review.score} />
          ))}
        </span>
      </span>
    </span>
  );
}

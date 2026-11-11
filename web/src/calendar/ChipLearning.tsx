import type { LectureRef } from "../types/lectures";
import { prequizDone } from "./entries";

/**
 * 칸 아래 학습 표시(2026-11 개편).
 *
 *   위 = 회독 줄: 학습률 막대와 같은 두께의 점선. 예습 퀴즈를 끝까지 풀었을 때만 첫 토막을 옅은 예습 색으로 채운다
 *        (예습은 1회독까지만 센다). 뒤에 강의록 회독 토막(2026-11-10 2단계)이 하나에 하나씩 붙는다.
 *   아래 = 복습 학습률 막대: 0%여도 바탕이 보이고, 덜 채울수록 진하다(덜 공부한 강의가 더 중요하다).
 *          Main-Quiz가 아직 없거나 불러오는 중이면 회색 바탕만.
 * 학습률은 Main-Quiz 하나다(2026-11-11). 서버가 시간표에 실어 준 `mastery`를 그대로 쓴다 — Quiz Bank는 legacy.
 * 예습 학습률 막대는 없앴다(사용자 지시).
 */
const labels = {
  not_started: "미학습",
  needs_review: "복습 필요",
  mastered: "목표 달성",
};

type Review = { score: number | null; description: string };

function reviewFor(lecture: LectureRef): Review {
  if (lecture.studyLoaded === false) return { score: null, description: "복습: 학습률 불러오는 중" };
  if (!lecture.marks.mainQuiz) return { score: null, description: "복습: Main-Quiz 없음" };
  const value = lecture.mastery;
  if (!value) return { score: 0, description: "Main-Quiz 학습률 0% · 평가 준비 전" };
  const score = Math.max(0, Math.min(100, value.score));
  return { score, description: `Main-Quiz 학습률 ${score}% · ${labels[value.status]} · 목표 ${value.fullTargets}/${value.targetCount}` };
}

function readsFor(lecture: LectureRef) {
  return lecture.noteReads ? ` · 강의록 ${lecture.noteReads}회독` : "";
}

function preFor(lecture: LectureRef) {
  if (lecture.studyLoaded === false) return "예습: 불러오는 중";
  const progress = lecture.prequizProgress;
  if (!lecture.marks.prequiz || !progress || progress.total <= 0) return "예습: 웹 문항 없음";
  return prequizDone(lecture) ? "예습 퀴즈 완료" : `예습 퀴즈 ${Math.min(progress.answered, progress.total)}/${progress.total}`;
}

export function learningDescription(lecture: LectureRef) {
  return `${lecture.title}: ${preFor(lecture)}${readsFor(lecture)} · ${reviewFor(lecture).description}`;
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
  if (!lectures.length) return null;
  const reviews = lectures.map(reviewFor);
  const description = lectures.map(learningDescription).join(" · ");
  const preOpen = lectures.some(l => l.marks.prequiz);
  const preDone = lectures.every(l => !l.marks.prequiz || prequizDone(l)) && preOpen;
  const single = lectures.length === 1 ? reviews[0] : null;
  // 강의록 회독은 앞에서부터 채운다(예습 퀴즈 완료 토막 다음). 둘 다 없을 때만 빈 테두리 칸 하나.
  const reads = Math.max(0, ...lectures.map(l => l.noteReads ?? 0));
  return (
    <span className="chip-learning-pair" title={description} aria-label={description}>
      <span className="readline" aria-hidden="true">
        {preDone ? <i className="rl-pre is-on" /> : null}
        {Array.from({ length: Math.min(reads, 8) }, (_, index) => <i key={index} className="rl-note" />)}
        {preOpen && !preDone && !reads ? <i className="rl-pre" /> : null}
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

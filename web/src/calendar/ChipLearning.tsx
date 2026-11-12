import type { LectureRef } from "../types/lectures";
import { prequizDone } from "./entries";

/**
 * 칸 아래 학습 표시(2026-11 개편).
 *
 *   위 = 회독 줄: 학습률 막대와 같은 두께의 점선. 예습 퀴즈 토막은 미완료면 회색 테두리, 끝까지 풀면 예습 색으로
 *        채운다(예습은 1회독까지만 센다). 뒤에 강의록 회독 토막(2026-11-10 2단계)이 하나에 하나씩 붙는다.
 *   아래 = 복습 학습률 막대: 회색 테두리만 있는 막대를 학습률만큼 연한 메인 색(--accent-line)으로 채운다(2026-11-12 사용자 지시 —
 *          옛 「덜 채울수록 진하다」는 없앴다). Main-Quiz가 없으면 막대가 없고, 불러오는 중이면 같은 회색 테두리만(채움만 나중에 생긴다).
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

/** 복습 막대: 회색 테두리 + 학습률만큼 연한 메인 색 채움(색은 CSS `.meter`·`.meter > span`). */
export function ReviewMeter({ score, className = "" }: { score: number | null; className?: string }) {
  if (score === null) return <span className={`meter is-closed ${className}`} />;
  return (
    <span className={`meter ${className}`}>
      <span style={{ width: `${score}%` }} />
    </span>
  );
}

/**
 * 복습 막대는 Main-Quiz가 있는 강의에만 그린다(2026-11-12 사용자: 「TBL 같이 시험에 안 나오는 경우는 복습바 없도록」,
 * 「복습퀴즈가 안 나온 경우에는 그냥 바를 보여주지 말자」). `mainQuiz` 표시는 첫 목록 응답에 이미 있어서,
 * 학습률을 불러오는 동안에는 회색 빈 막대로 자리만 잡는다.
 */
export function reviewShown(lecture: LectureRef) {
  return !!lecture.marks.mainQuiz;
}

/** 칸 아래 줄에 그릴 것이 있는가: 복습 막대, 예습 퀴즈 토막, 강의록 회독. */
export function hasLearningMarks(lectures: LectureRef[]) {
  return lectures.some(l => reviewShown(l) || l.marks.prequiz || (l.noteReads ?? 0) > 0);
}

export function ChipLearning({ lectures }: { lectures: LectureRef[] }) {
  if (!lectures.length) return null;
  const meters = lectures.filter(reviewShown);
  const reviews = meters.map(reviewFor);
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
        {meters.length ? <span className="chip-learning-bars" aria-hidden="true">
          {reviews.map((review, index) => (
            <ReviewMeter key={`${meters[index].subject}/${meters[index].runId}`} score={review.score} />
          ))}
        </span> : null}
      </span>
    </span>
  );
}

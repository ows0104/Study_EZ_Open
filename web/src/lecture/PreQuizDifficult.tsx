import { useEffect, useState } from "react";
import { api } from "../api";
import type { MissedItem, QuizItem, RevealResult } from "../types/quiz";
import { PreQuizText } from "./PreQuizText";
import { PreQuizCloze } from "./PreQuizCloze";
import { WhyAsked } from "./Quiz";
import { FeedbackButton } from "../feedback/FeedbackButton";

type Answer = Pick<RevealResult, "answer" | "explanation" | "lectureFocus" | "clozeParts">;

/** 마지막 선택이 '아직 헷갈려요'인 문제를 완료 직후 펼쳐 보여 준다. */
export function PreQuizDifficult({ base, items, answers, onReview, reportContext, studyTrack = "core" }: {
  base: string; items: QuizItem[]; answers: Record<string, Answer>; onReview: () => void;
  reportContext: { subject: string; runId: string; title: string };
  studyTrack?: "core" | "extra";
}) {
  const [saved, setSaved] = useState<Record<string, Answer>>({});
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);
  const ids = items.map((entry) => entry.itemId).join("|");

  useEffect(() => {
    // 방금 푼 문제는 이미 받아 둔 답을 즉시 보여 준다. 완료 화면을 다시 열면
    // 기존 강의 상세의 본인별 missed 응답 한 번으로 답과 설명을 복원한다.
    if (items.every((entry) => answers[entry.itemId])) return;
    let active = true;
    setError("");
    api<{ prequiz: { missed: MissedItem[]; extraMissed?: MissedItem[] } | null }>(base.replace(/\/prequiz$/, ""))
      .then((detail) => {
        const missed = studyTrack === "extra" ? detail.prequiz?.extraMissed : detail.prequiz?.missed;
        if (active) setSaved(Object.fromEntries((missed ?? []).map((entry) => [entry.itemId, entry])));
      }).catch((cause: Error) => { if (active) setError(cause.message); });
    return () => { active = false; };
  }, [base, ids, answers, retry, studyTrack]);

  return <section className="prequiz-difficult">
    <h3>어려웠던 문제 {items.length}개</h3>
    <p className="prequiz-review-note">‘아직 헷갈려요’를 고른 문제예요. 답과 설명을 한 번 더 살펴보세요.</p>
    <div className="prequiz-review-list">
      {items.map((entry, index) => {
        const answer = answers[entry.itemId] ?? saved[entry.itemId];
        return <article className="prequiz-review-card" key={entry.itemId}>
          <small className="prequiz-review-number">문제 {index + 1}</small>
          <WhyAsked item={entry} />
          <h4><PreQuizCloze text={entry.stem} parts={entry.qtype === "cloze" ? answer?.clozeParts : undefined} /></h4>
          {answer ? <>
            <p className="prequiz-review-answer"><b>답</b><PreQuizText text={answer.answer} /></p>
            {answer.explanation ? <p className="prequiz-review-explanation"><b>설명</b><PreQuizText text={answer.explanation} /></p> : null}
            {answer.lectureFocus ? <p className="prequiz-review-focus"><b>수업에서 확인할 내용</b><PreQuizText text={answer.lectureFocus} /></p> : null}
          </> : <p className="prequiz-review-note">답과 설명을 불러오는 중…</p>}
          <FeedbackButton prequiz={{ ...reportContext, itemId: entry.itemId, stem: entry.stem,
            ...(answer ? { answer: answer.answer, explanation: answer.explanation } : {}) }} />
        </article>;
      })}
    </div>
    {error ? <p role="alert" className="notice is-error">{error} <button onClick={() => setRetry((old) => old + 1)}>다시 불러오기</button></p> : null}
    <button className="prequiz-review-start" onClick={onReview}>어려웠던 문제만 다시 풀기</button>
  </section>;
}

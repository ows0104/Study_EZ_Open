import { useEffect, useState } from "react";
import { api } from "../api";
import { lectureHref } from "../links";
import { useMe } from "../useMe";
import { cardsHash } from "./LectureCards";
import type { GradeResult, QuizPayload, QuizSchedule, RevealResult, UndoResult } from "../types/quiz";
import { WhyAsked } from "./Quiz";
import { Stem } from "./Stem";
import { SlideImage } from "../SlideImage";
import { useQuizSlidePreload } from "./useQuizSlidePreload";

/** 예습은 한 번 이해를 확인하고, 수업에서 들을 질문을 남긴다. */
export function PreQuiz({ subject, runId, onDone }: {
  subject: string; runId: string; onDone: (done: boolean) => void;
}) {
  const base = `/api/lectures/${encodeURIComponent(subject)}/${encodeURIComponent(runId)}/prequiz`;
  const [payload, setPayload] = useState<QuizPayload | null>(null);
  const [revealed, setRevealed] = useState<RevealResult | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [forcedId, setForcedId] = useState("");
  const [mode, setMode] = useState<"core" | "reread">("core");
  const [seen, setSeen] = useState<Set<string>>(() => new Set());
  const isAdmin = Boolean(useMe()?.isAdmin);

  useEffect(() => {
    let active = true;
    api<QuizPayload>(base).then((result) => { if (active) setPayload(result); })
      .catch((cause: Error) => { if (active) setError(cause.message); });
    return () => { active = false; };
  }, [base]);

  const ordered = payload?.items ?? [];
  const completed = (itemId: string) => mode === "reread"
    ? seen.has(itemId) : Boolean(ordered.find((entry) => entry.itemId === itemId)?.attempt);
  const candidates = ordered.filter((entry) =>
    !completed(entry.itemId));
  const item = payload?.items.find((entry) => entry.itemId === forcedId)
    ?? candidates[0];
  const finished = Boolean(payload && !item);
  const slides = useQuizSlidePreload(base, item
    ? [item, ...candidates.filter((entry) => entry.itemId !== item.itemId)].slice(0, 3).map((entry) => entry.itemId)
    : []);
  useEffect(() => { onDone(finished); }, [finished, onDone]);

  function patch(itemId: string, attempt: QuizSchedule | null, feedback: RevealResult, undoable: boolean) {
    setPayload((old) => old && ({ ...old, undoable, items: old.items.map((entry) =>
      entry.itemId === itemId ? { ...entry, attempt, learningScope: feedback.learningScope,
        lectureFocus: feedback.lectureFocus } : entry) }));
  }
  async function reveal() {
    if (!item || busy) return;
    setBusy(true); setError("");
    try { setRevealed(await api<RevealResult>(`${base}/reveal`, {
      method: "POST", body: JSON.stringify({ itemId: item.itemId }),
    })); } catch (cause) { setError((cause as Error).message); }
    finally { setBusy(false); }
  }
  async function check(understood: boolean) {
    if (!item || !revealed || busy) return;
    setBusy(true); setError("");
    try {
      const result = await api<GradeResult>(`${base}/check`, {
        method: "POST", body: JSON.stringify({ itemId: item.itemId, understood }),
      });
      patch(item.itemId, result.attempt, revealed, result.undoable);
      setSeen((old) => new Set(old).add(item.itemId));
      setForcedId(""); setRevealed(null);
    } catch (cause) { setError((cause as Error).message); }
    finally { setBusy(false); }
  }
  async function undo() {
    if (!payload?.undoable || busy) return;
    setBusy(true); setError("");
    try {
      const result = await api<UndoResult>(`${base}/undo`, { method: "POST" });
      patch(result.itemId, result.attempt, result, result.undoable);
      setSeen((old) => { const next = new Set(old); next.delete(result.itemId); return next; });
      setForcedId(result.itemId); setRevealed(result);
    } catch (cause) { setError((cause as Error).message); }
    finally { setBusy(false); }
  }
  function start() {
    setMode("reread"); setSeen(new Set()); setForcedId(""); setRevealed(null); setError("");
  }
  const undoButton = payload?.undoable ? <button className="quiz-undo" disabled={busy} onClick={undo}>이전 선택 되돌리기</button> : null;
  if (!payload) return <p className={`notice${error ? " is-error" : ""}`}>{error || "예습 문항을 불러오는 중…"}</p>;
  const progress = <PreQuizProgress title={mode === "reread" ? "다시 훑어보기" : "예습"}
    done={ordered.filter((entry) => completed(entry.itemId)).length} total={ordered.length} />;
  if (!item) {
    const targets = ordered.filter((entry) => entry.attempt && !entry.attempt.correct);
    return <div className="quiz-done prequiz-narrow">
      {progress}
      <h2>{ordered.length ? `예습 ${ordered.length}문항 확인 완료` : "아직 예습 문항이 없습니다"}</h2>
      {ordered.length > 0 ? <p>수업을 들을 준비가 됐어요. 세부 내용은 수업에서 연결하면 됩니다.</p> : null}
      {targets.length ? <section className="quiz-takeaways">
        <h3>수업에서 확인할 질문 {targets.length}개</h3>
        <ul>{targets.map((entry) => <li key={entry.itemId}><Stem text={entry.lectureFocus || entry.stem} /></li>)}</ul>
      </section> : ordered.length > 0 ? <p className="quiz-done-note">모든 문항을 이해했어요. 수업에서 어떻게 확장되는지 들어보세요.</p> : null}
      {ordered.some((entry) => entry.learningScope) ? <details className="quiz-takeaways">
        <summary>오늘 챙긴 핵심</summary>
        <ul>{ordered.filter((entry) => entry.learningScope).map((entry) => <li key={entry.itemId}>{entry.learningScope}</li>)}</ul>
      </details> : null}
      <a className="resource" href={lectureHref({ subject, runId })}><strong>예습 마치기</strong></a>
      {ordered.length ? <button className="quiz-undo" onClick={start}>다시 훑어보기</button> : null}
      {undoButton}
      {error ? <p role="alert" className="notice is-error">{error}</p> : null}
    </div>;
  }
  const feedback = revealed?.itemId === item.itemId ? revealed : null;
  return <>
    <div className="quiz">
      {progress}
      <p className="quiz-progress">{undoButton}
        {isAdmin ? <a className="quiz-fix" href={lectureHref({ subject, runId }) + cardsHash("pre", item.itemId)} target="_blank" rel="noreferrer">이 카드 고치기</a> : null}
      </p>
      <p className="quiz-support-note prequiz-intro">떠오르는 만큼 생각해 보세요. 답을 읽고 이해하면 충분해요.</p>
      <WhyAsked item={item} />
      <p className="quiz-stem"><Stem text={item.stem} /></p>
      {!feedback && item.hint ? <details className="quiz-hint" key={item.itemId}>
        <summary>
          <svg className="quiz-hint-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M9 18h6m-5 3h4M9 15c0-2-3-3-3-7a6 6 0 0 1 12 0c0 4-3 5-3 7" />
          </svg>
          <span className="quiz-hint-closed">힌트 보기</span>
          <span className="quiz-hint-open">힌트 접기</span>
          <svg className="quiz-hint-chevron" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="m4 6 4 4 4-4" /></svg>
        </summary>
        <p>{item.hint}</p>
      </details> : null}
      {feedback ? <>
        <hr className="quiz-line" />
        <p className="quiz-answer"><Stem text={feedback.answer} /></p>
        {feedback.explanation ? <p className="quiz-explanation">{feedback.explanation}</p> : null}
        {feedback.whyAsked ? <p className="quiz-why-back"><span className="quiz-why-label">왜 냈나요?</span>{feedback.whyAsked}</p> : null}
        {feedback.learningScope ? <p className="quiz-support-note"><strong>지금은 여기까지</strong><br />{feedback.learningScope}</p> : null}
        {feedback.lectureFocus ? <p className="quiz-support-note"><strong>수업에서 들어볼 질문</strong><br />{feedback.lectureFocus}</p> : null}
        {feedback.slideUrl ? <SlideImage preload={slides} src={feedback.slideUrl} alt={`슬라이드 ${feedback.slideNo}`} /> : null}
      </> : null}
      {error ? <p role="alert" className="notice is-error">{error}</p> : null}
    </div>
    <div className="quiz-bar prequiz-bar">
      {!feedback ? <button className="quiz-submit" disabled={busy} onClick={reveal}>{busy ? "불러오는 중…" : "답과 설명 보기"}</button>
        : <><button className="quiz-grade prequiz-choice" disabled={busy} onClick={() => check(false)}><span className="quiz-grade-name">수업에서 확인할게요</span></button>
          <button className="quiz-grade prequiz-choice" disabled={busy} onClick={() => check(true)}><span className="quiz-grade-name">이해했어요</span></button></>}
    </div>
  </>;
}

function PreQuizProgress({ title, done, total }: {
  title: string; done: number; total: number;
}) {
  if (!total) return null;
  return <div className="prequiz-progress" aria-live="polite">
    <p><span>{title}</span><strong>{done} / {total}문항 완료</strong></p>
  </div>;
}

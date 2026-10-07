import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { lectureHref } from "../links";
import { useMe } from "../useMe";
import { cardsHash } from "./LectureCards";
import type { GradeResult, QuizPayload, QuizSchedule, RevealResult, UndoResult } from "../types/quiz";
import { WhyAsked } from "./Quiz";
import { PreQuizText } from "./PreQuizText";
import { SlideImage } from "../SlideImage";
import { useQuizSlidePreload } from "./useQuizSlidePreload";
import { PreQuizDifficult } from "./PreQuizDifficult";

/** 예습은 한 번 이해를 확인하고, 수업에서 들을 질문을 남긴다. */
export function PreQuiz({ subject, runId, onDone }: {
  subject: string; runId: string; onDone: (done: boolean) => void;
}) {
  const base = `/api/lectures/${encodeURIComponent(subject)}/${encodeURIComponent(runId)}/prequiz`;
  const [payload, setPayload] = useState<QuizPayload | null>(null);
  const [revealed, setRevealed] = useState<RevealResult | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const actionPending = useRef(false);
  const [forcedId, setForcedId] = useState("");
  const [mode, setMode] = useState<"core" | "reread" | "difficult">("core");
  const [seen, setSeen] = useState<Set<string>>(() => new Set());
  const [reviewIds, setReviewIds] = useState<string[]>([]);
  const [answers, setAnswers] = useState<Record<string, RevealResult>>({});
  const isAdmin = Boolean(useMe()?.isAdmin);

  useEffect(() => {
    let active = true;
    api<QuizPayload>(base).then((result) => { if (active) setPayload(result); })
      .catch((cause: Error) => { if (active) setError(cause.message); });
    return () => { active = false; };
  }, [base]);

  const ordered = payload?.items ?? [];
  const round = mode === "difficult" ? ordered.filter((entry) => reviewIds.includes(entry.itemId)) : ordered;
  const completed = (itemId: string) => mode !== "core"
    ? seen.has(itemId) : Boolean(ordered.find((entry) => entry.itemId === itemId)?.attempt);
  const candidates = round.filter((entry) =>
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
    if (!item || busy || actionPending.current) return;
    actionPending.current = true;
    setBusy(true); setError("");
    try {
      const result = await api<RevealResult>(`${base}/reveal`, {
        method: "POST", body: JSON.stringify({ itemId: item.itemId }),
      });
      setRevealed(result);
      setAnswers((old) => ({ ...old, [result.itemId]: result }));
    } catch (cause) { setError((cause as Error).message); }
    finally { actionPending.current = false; setBusy(false); }
  }
  async function check(understood: boolean) {
    if (!item || !revealed || busy || actionPending.current) return;
    actionPending.current = true;
    setBusy(true); setError("");
    try {
      const result = await api<GradeResult>(`${base}/check`, {
        method: "POST", body: JSON.stringify({ itemId: item.itemId, understood }),
      });
      patch(item.itemId, result.attempt, revealed, result.undoable);
      setSeen((old) => new Set(old).add(item.itemId));
      setForcedId(""); setRevealed(null);
    } catch (cause) { setError((cause as Error).message); }
    finally { actionPending.current = false; setBusy(false); }
  }
  async function undo() {
    if (!canUndo || busy || actionPending.current) return;
    actionPending.current = true;
    setBusy(true); setError("");
    try {
      const result = await api<UndoResult>(`${base}/undo`, { method: "POST" });
      patch(result.itemId, result.attempt, result, result.undoable);
      setSeen((old) => { const next = new Set(old); next.delete(result.itemId); return next; });
      setForcedId(result.itemId); setRevealed(result);
      setAnswers((old) => ({ ...old, [result.itemId]: result }));
    } catch (cause) { setError((cause as Error).message); }
    finally { actionPending.current = false; setBusy(false); }
  }
  function start(ids?: string[]) {
    setMode(ids ? "difficult" : "reread"); setReviewIds(ids ?? []);
    setSeen(new Set()); setForcedId(""); setRevealed(null); setError("");
  }
  const canUndo = Boolean(payload?.undoable && (mode !== "difficult" || seen.size > 0));
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.defaultPrevented || event.repeat || event.isComposing || event.metaKey || event.altKey
        || document.querySelector("dialog[open], [role='dialog'][aria-modal='true']")) return;
      const target = event.target instanceof HTMLElement ? event.target : null;
      if (target?.closest("input, textarea, select, [contenteditable]:not([contenteditable='false']), [role='textbox']")) return;
      const key = event.key.toLowerCase();
      if (key === "z" && !event.shiftKey && canUndo) {
        event.preventDefault();
        void undo();
        return;
      }
      if (event.ctrlKey || event.shiftKey || !item) return;
      const feedback = revealed?.itemId === item.itemId;
      if ((key === " " || key === "enter") && !target?.closest("button, a, summary, [role='button']")) {
        event.preventDefault();
        if (feedback) void check(true);
        else void reveal();
      } else if (feedback && (key === "1" || key === "2")) {
        event.preventDefault();
        void check(key === "2");
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [item, revealed, busy, canUndo]);
  const undoButton = canUndo
    ? <button className="quiz-undo" disabled={busy} onClick={undo}>이전 선택 되돌리기 <kbd>Z</kbd></button> : null;
  if (!payload) return <p className={`notice${error ? " is-error" : ""}`}>{error || "예습 문항을 불러오는 중…"}</p>;
  const progress = <PreQuizProgress title={mode === "difficult" ? "어려웠던 문제 다시 보기" : mode === "reread" ? "다시 훑어보기" : "예습"}
    done={round.filter((entry) => completed(entry.itemId)).length} total={round.length} />;
  if (!item) {
    const targets = ordered.filter((entry) => entry.attempt && !entry.attempt.correct);
    return <div className="quiz-done prequiz-narrow">
      {progress}
      <h2>{ordered.length ? mode === "difficult" ? `어려웠던 ${round.length}문항 다시 보기 완료` : `예습 ${ordered.length}문항 확인 완료` : "아직 예습 문항이 없습니다"}</h2>
      {ordered.length > 0 ? <p>수업을 들을 준비가 됐어요. 세부 내용은 수업에서 연결하면 됩니다.</p> : null}
      {targets.length ? <PreQuizDifficult base={base} items={targets} answers={answers}
        onReview={() => start(targets.map((entry) => entry.itemId))} />
        : ordered.length > 0 ? <p className="quiz-done-note">모든 문항을 이해했어요. 수업에서 어떻게 확장되는지 들어보세요.</p> : null}
      {ordered.some((entry) => entry.learningScope) ? <details className="quiz-takeaways">
        <summary>오늘 챙긴 핵심</summary>
        <ul>{ordered.filter((entry) => entry.learningScope).map((entry) => <li key={entry.itemId}><PreQuizText text={entry.learningScope!} /></li>)}</ul>
      </details> : null}
      <a className="resource" href="/"><strong>예습 마치기</strong></a>
      {ordered.length ? <button className="quiz-undo" onClick={() => start()}>전체 다시 훑어보기</button> : null}
      {undoButton}
      {error ? <p role="alert" className="notice is-error">{error}</p> : null}
    </div>;
  }
  const feedback = revealed?.itemId === item.itemId ? revealed : null;
  return <>
    <div className="quiz prequiz">
      <div className="prequiz-status">{progress}<WhyAsked item={item} /></div>
      <p className="quiz-stem"><PreQuizText text={item.stem} /></p>
      {!feedback && item.hint ? <details className="quiz-hint" key={item.itemId}>
        <summary>
          <svg className="quiz-hint-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M9 18h6m-5 3h4M9 15c0-2-3-3-3-7a6 6 0 0 1 12 0c0 4-3 5-3 7" />
          </svg>
          <span className="quiz-hint-closed">힌트 보기</span>
          <span className="quiz-hint-open">힌트 접기</span>
          <svg className="quiz-hint-chevron" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="m4 6 4 4 4-4" /></svg>
        </summary>
        <p><PreQuizText text={item.hint} /></p>
      </details> : null}
      {feedback ? <>
        <hr className="quiz-line" />
        <p className="quiz-answer"><PreQuizText text={feedback.answer} /></p>
        {feedback.explanation ? <p className="quiz-explanation"><PreQuizText text={feedback.explanation} /></p> : null}
        {feedback.whyAsked ? <p className="quiz-why-back"><span className="quiz-why-label">왜 냈나요?</span><PreQuizText text={feedback.whyAsked} /></p> : null}
        {feedback.learningScope ? <p className="quiz-support-note"><strong>지금은 여기까지</strong><PreQuizText text={feedback.learningScope} /></p> : null}
        {feedback.lectureFocus ? <p className="quiz-support-note"><strong>수업에서 들어볼 질문</strong><PreQuizText text={feedback.lectureFocus} /></p> : null}
        {feedback.slideUrl ? <SlideImage preload={slides} src={feedback.slideUrl} alt={`슬라이드 ${feedback.slideNo}`} /> : null}
      </> : null}
      {error ? <p role="alert" className="notice is-error">{error}</p> : null}
      <div className="prequiz-tools">
        {undoButton}
        {isAdmin ? <a className="quiz-fix" href={lectureHref({ subject, runId }) + cardsHash("pre", item.itemId)} target="_blank" rel="noreferrer">이 카드 고치기</a> : null}
      </div>
    </div>
    <div className="quiz-bar prequiz-bar">
      {!feedback ? <button className="quiz-submit" disabled={busy} onClick={reveal} aria-keyshortcuts="Space Enter">{busy ? "불러오는 중…" : <>답과 설명 보기 <kbd>Space</kbd></>}</button>
        : <><button className="quiz-grade prequiz-choice" disabled={busy} onClick={() => check(false)} aria-keyshortcuts="1"><span className="quiz-grade-name">아직 헷갈려요 <kbd>1</kbd></span></button>
          <button className="quiz-grade prequiz-choice" disabled={busy} onClick={() => check(true)} aria-keyshortcuts="2 Space Enter"><span className="quiz-grade-name">이해했어요 <kbd>2 / Space</kbd></span></button></>}
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

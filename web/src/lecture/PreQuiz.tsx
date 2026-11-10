import { useEffect, useRef, useState } from "react";
import "./prequiz.css";
import { api } from "../api";
import { lectureHref } from "../links";
import { useMe } from "../useMe";
import { cardsHash } from "./LectureCards";
import type { GradeResult, QuizPayload, QuizSchedule, RevealResult, UndoResult } from "../types/quiz";
import { WhyAsked } from "./Quiz";
import { PreQuizText } from "./PreQuizText";
import { PreQuizCloze } from "./PreQuizCloze";
import { SlideImage } from "../SlideImage";
import { useQuizSlidePreload } from "./useQuizSlidePreload";
import { PreQuizDifficult } from "./PreQuizDifficult";
import { FeedbackButton } from "../feedback/FeedbackButton";

/** 예습은 한 번 이해를 확인하고, 수업에서 들을 질문을 남긴다. */
export function PreQuiz({ subject, runId, title, onDone }: {
  subject: string; runId: string; title?: string; onDone: (done: boolean) => void;
}) {
  const base = `/api/lectures/${encodeURIComponent(subject)}/${encodeURIComponent(runId)}/prequiz`;
  const [payload, setPayload] = useState<QuizPayload | null>(null);
  const [revealed, setRevealed] = useState<RevealResult | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const actionPending = useRef(false);
  const [forcedId, setForcedId] = useState("");
  const [mode, setMode] = useState<"core" | "reread" | "difficult">("core");
  const [studyTrack, setStudyTrack] = useState<"core" | "extra">("core");
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

  const coreItems = (payload?.items ?? []).filter((entry) => entry.studyTrack !== "extra");
  const extraItems = (payload?.items ?? []).filter((entry) => entry.studyTrack === "extra");
  const ordered = studyTrack === "extra" ? extraItems : coreItems;
  const round = mode === "difficult" ? ordered.filter((entry) => reviewIds.includes(entry.itemId)) : ordered;
  const completed = (itemId: string) => mode !== "core"
    ? seen.has(itemId) : Boolean(ordered.find((entry) => entry.itemId === itemId)?.attempt);
  const candidates = round.filter((entry) =>
    !completed(entry.itemId));
  const item = ordered.find((entry) => entry.itemId === forcedId)
    ?? candidates[0];
  const finished = Boolean(payload && coreItems.length && coreItems.every((entry) => entry.attempt));
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
      const restoredTrack = payload?.items.find((entry) => entry.itemId === result.itemId)?.studyTrack === "extra" ? "extra" : "core";
      if (restoredTrack !== studyTrack) setMode("core");
      setStudyTrack(restoredTrack);
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
  function switchTrack(track: "core" | "extra") {
    setStudyTrack(track); setMode(track === "extra" && extraItems.every((entry) => entry.attempt) ? "reread" : "core"); setSeen(new Set());
    setForcedId(""); setRevealed(null); setError("");
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
  if (!payload) return <section className="prequiz-learning">
    <p className={`notice${error ? " is-error" : ""}`}>{error || "예습 문항을 불러오는 중…"}</p>
  </section>;
  const heading = title || payload.title;
  const trackName = mode === "difficult" ? "어려웠던 문제" : mode === "reread" ? "다시 훑어보기"
    : studyTrack === "extra" ? "추가 학습" : "예습";
  const doneCount = round.filter((entry) => completed(entry.itemId)).length;
  const head = <header className="pq-head">
    <p className="pq-kicker">
      <span className="pq-badge">Pre-Quiz</span>
      <a className="pq-title" href={lectureHref({ subject, runId })}>{heading}</a>
    </p>
    {item ? <span className="pq-tools">
      {studyTrack === "extra" ? <button className="pill-button" disabled={busy} onClick={() => switchTrack("core")}>추가 학습 그만하기</button> : null}
      <FeedbackButton key={item.itemId} launch={{ className: "pill-button", content: "문제 제보" }}
        prequiz={{ subject, runId, title: payload.title, itemId: item.itemId, stem: item.stem,
          ...(revealed?.itemId === item.itemId ? { answer: revealed.answer, explanation: revealed.explanation } : {}) }} />
      {isAdmin ? <a className="pill-button" href={lectureHref({ subject, runId }) + cardsHash("pre", item.itemId)} target="_blank" rel="noreferrer">이 카드 고치기</a> : null}
    </span> : null}
  </header>;
  if (!item) {
    const targets = ordered.filter((entry) => entry.attempt && !entry.attempt.correct);
    const extraDone = extraItems.filter((entry) => entry.attempt).length;
    const doneTitle = !ordered.length ? "예습 문항 없음"
      : mode === "difficult" ? "어려웠던 문제 다시 보기 완료" : `${studyTrack === "extra" ? "추가 학습" : "예습"} 완료`;
    return <section className="prequiz-learning pq-done">
      {head}
      <div className="pq-today">
        <div className="pq-today-text">
          <h2>{doneTitle}</h2>
          {ordered.length ? <p><b>{round.length}</b>문항 확인
            {targets.length ? <> · 헷갈림 <b className="pq-today-miss">{targets.length}</b></> : null}</p> : null}
        </div>
        <div className="pq-actions">
          <button className="pill-button" disabled={busy || !canUndo} onClick={undo} aria-keyshortcuts="Z">되돌리기 <kbd>Z</kbd></button>
          {ordered.length ? <button className="pill-button" disabled={busy} onClick={() => start()}>다시 훑어보기</button> : null}
          {studyTrack === "extra" ? <button className="pill-button" onClick={() => switchTrack("core")}>예습으로</button> : null}
          <a className="pq-start-button" href="/">예습 마치기</a>
        </div>
      </div>
      {studyTrack === "core" && finished && extraItems.length > 0 ? <div className="pq-extra">
        <div className="pq-today-text">
          <h2>추가 학습 · 선택</h2>
          <p><b>{extraDone}</b> / {extraItems.length}문항</p>
        </div>
        <button className="pill-button" onClick={() => switchTrack("extra")}>{extraItems.every((entry) => entry.attempt) ? "다시 보기" : "풀기"}</button>
      </div> : null}
      {targets.length ? <PreQuizDifficult base={base} studyTrack={studyTrack} items={targets} answers={answers}
        reportContext={{ subject, runId, title: payload.title }}
        onReview={() => start(targets.map((entry) => entry.itemId))} /> : null}
      {ordered.some((entry) => entry.learningScope) ? <details className="pq-takeaways">
        <summary>오늘 챙긴 핵심</summary>
        <ul>{ordered.filter((entry) => entry.learningScope).map((entry) => <li key={entry.itemId}><PreQuizText text={entry.learningScope!} /></li>)}</ul>
      </details> : null}
      {error ? <p role="alert" className="notice is-error">{error}</p> : null}
    </section>;
  }
  const feedback = revealed?.itemId === item.itemId ? revealed : null;
  return <section className="prequiz-learning quiz">
    {head}
    <div className="pq-progress" aria-live="polite">
      <h2 className="pq-count">{trackName} {doneCount} / {round.length}</h2>
      <span className="pq-track" aria-hidden="true"><i style={{ width: `${round.length ? doneCount / round.length * 100 : 0}%` }} /></span>
      <WhyAsked item={item} />
    </div>
    <div className="pq-card">
      <p className="quiz-stem"><PreQuizCloze text={item.stem} parts={item.qtype === "cloze" ? feedback?.clozeParts : undefined} /></p>
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
        {feedback.whyAsked ? <p className="quiz-support-note"><strong>왜 냈나요?</strong><PreQuizText text={feedback.whyAsked} /></p> : null}
        {feedback.learningScope ? <p className="quiz-support-note"><strong>지금은 여기까지</strong><PreQuizText text={feedback.learningScope} /></p> : null}
        {feedback.lectureFocus ? <p className="quiz-support-note is-focus"><strong>수업에서 들어볼 질문</strong><PreQuizText text={feedback.lectureFocus} /></p> : null}
        {feedback.slideUrl ? <SlideImage preload={slides} src={feedback.slideUrl} alt={`슬라이드 ${feedback.slideNo}`} /> : null}
      </> : null}
      {error ? <p role="alert" className="notice is-error">{error}</p> : null}
    </div>
    <div className="quiz-bar pq-dock" aria-label="이해 확인">
      <button className="quiz-undo" disabled={busy || !canUndo} onClick={undo} aria-keyshortcuts="Z">되돌리기 <kbd>Z</kbd></button>
      {!feedback ? <button className="quiz-submit pq-reveal" disabled={busy} onClick={reveal} aria-keyshortcuts="Space Enter">{busy ? "불러오는 중…" : <>답과 설명 보기 <kbd>Space</kbd></>}</button>
        : <><button className="quiz-grade pq-choice is-unsure" disabled={busy} onClick={() => check(false)} aria-keyshortcuts="1"><span className="quiz-grade-name">아직 헷갈려요 <kbd>1</kbd></span></button>
          <button className="quiz-grade pq-choice is-understood" disabled={busy} onClick={() => check(true)} aria-keyshortcuts="2 Space Enter"><span className="quiz-grade-name">이해했어요 <kbd>2 / Space</kbd></span></button></>}
    </div>
  </section>;
}

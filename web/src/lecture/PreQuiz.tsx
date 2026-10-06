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
  const [mode, setMode] = useState<"core" | "reread" | "challenge">("core");
  const [seen, setSeen] = useState<Set<string>>(() => new Set());
  const isAdmin = Boolean(useMe()?.isAdmin);

  useEffect(() => {
    let active = true;
    api<QuizPayload>(base).then((result) => { if (active) setPayload(result); })
      .catch((cause: Error) => { if (active) setError(cause.message); });
    return () => { active = false; };
  }, [base]);

  const core = payload?.items.filter((entry) => !entry.challenge) ?? [];
  const challenges = payload?.items.filter((entry) => entry.challenge) ?? [];
  const item = payload?.items.find((entry) => entry.itemId === forcedId)
    ?? (mode === "challenge" ? challenges.find((entry) => !seen.has(entry.itemId))
      : core.find((entry) => mode === "reread" ? !seen.has(entry.itemId) : !entry.attempt));
  const finished = Boolean(payload && !item);
  const candidates = (mode === "challenge" ? challenges : core).filter((entry) =>
    mode === "core" ? !entry.attempt : !seen.has(entry.itemId));
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
    if (!item || !revealed || busy || item.challenge) return;
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
      setForcedId(result.itemId); setRevealed(result); setMode("core");
    } catch (cause) { setError((cause as Error).message); }
    finally { setBusy(false); }
  }
  function start(next: "reread" | "challenge") {
    setMode(next); setSeen(new Set()); setForcedId(""); setRevealed(null); setError("");
  }
  const undoButton = payload?.undoable ? <button className="quiz-undo" disabled={busy} onClick={undo}>이전 선택 되돌리기</button> : null;
  if (!payload) return <p className={`notice${error ? " is-error" : ""}`}>{error || "예습 문항을 불러오는 중…"}</p>;
  if (!item) {
    const targets = core.filter((entry) => entry.attempt && !entry.attempt.correct);
    return <div className="quiz-done prequiz-narrow">
      <h2>{core.length ? `핵심 ${core.length}문항 확인 완료` : "아직 예습 문항이 없습니다"}</h2>
      {core.length > 0 ? <p>수업을 들을 준비가 됐어요. 세부 내용은 수업에서 연결하면 됩니다.</p> : null}
      {targets.length ? <section className="quiz-takeaways">
        <h3>수업에서 확인할 질문 {targets.length}개</h3>
        <ul>{targets.map((entry) => <li key={entry.itemId}><Stem text={entry.lectureFocus || entry.stem} /></li>)}</ul>
      </section> : core.length > 0 ? <p className="quiz-done-note">핵심을 모두 이해했어요. 수업에서 어떻게 확장되는지 들어보세요.</p> : null}
      {core.some((entry) => entry.learningScope) ? <details className="quiz-takeaways">
        <summary>오늘 챙긴 핵심</summary>
        <ul>{core.filter((entry) => entry.learningScope).map((entry) => <li key={entry.itemId}>{entry.learningScope}</li>)}</ul>
      </details> : null}
      {challenges.length ? <button className="resource" onClick={() => start("challenge")}>
        <strong>선택 도전 {challenges.length}문항 살펴보기</strong><small>수업에서 배울 내용을 미리 궁금해 보는 질문이에요.</small>
      </button> : null}
      <a className="resource" href={lectureHref({ subject, runId })}><strong>예습 마치기</strong></a>
      {core.length ? <button className="quiz-undo" onClick={() => start("reread")}>다시 훑어보기</button> : null}
      {undoButton}
      {error ? <p role="alert" className="notice is-error">{error}</p> : null}
    </div>;
  }
  const feedback = revealed?.itemId === item.itemId ? revealed : null;
  const position = (item.challenge ? challenges : core).findIndex((entry) => entry.itemId === item.itemId) + 1;
  return <>
    <div className="quiz">
      <p className="quiz-progress"><span>{item.challenge ? "선택 도전" : mode === "reread" ? "다시 훑어보기" : "핵심"} {position} / {item.challenge ? challenges.length : core.length}</span>{undoButton}
        {isAdmin ? <a className="quiz-fix" href={lectureHref({ subject, runId }) + cardsHash("pre", item.itemId)} target="_blank" rel="noreferrer">이 카드 고치기</a> : null}
      </p>
      <p className="quiz-support-note">{item.challenge ? "지금 맞히지 않아도 괜찮아요. 수업에서 답을 찾아보세요." : "떠오르는 만큼 생각해 보세요. 답을 읽고 이해하면 충분해요."}</p>
      <WhyAsked item={item} />
      <p className="quiz-stem"><Stem text={item.stem} /></p>
      {!feedback && item.hint ? <details className="quiz-hint" key={item.itemId}><summary>힌트</summary><p>{item.hint}</p></details> : null}
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
        : item.challenge ? <button className="quiz-submit" onClick={() => { setSeen((old) => new Set(old).add(item.itemId)); setRevealed(null); }}>확인했어요 →</button>
          : <><button className="quiz-grade is-good" disabled={busy} onClick={() => check(true)}>이해했어요 →</button>
            <button className="quiz-grade is-listen" disabled={busy} onClick={() => check(false)}>수업에서 확인할게요 →</button></>}
      {item.challenge ? <button className="quiz-undo" disabled={busy} onClick={() => { setMode("core"); setRevealed(null); }}>도전 마치기</button> : null}
    </div>
  </>;
}

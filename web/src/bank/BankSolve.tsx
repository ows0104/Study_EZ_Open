import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { useMe } from "../useMe";
import { invalidateTimetable } from "../firstScreen";
import type { BankAnswer, BankNext, BankRating, BankRead, BankSession, BankTier } from "../types/bank";
import { ConceptMap } from "./ConceptMap";
import { PersonalQuestionDialog } from "./PersonalQuestionDialog";
import { daysLabel, DIRECTION_LABEL } from "./labels";
import { QuestionBody, AnswerBody } from "./BankQuestion";
import { SlidePreloader } from "../slidePreload";
import { usePreparedBankAnswer } from "./usePreparedBankAnswer";
import { DailyGoal } from "./DailyGoal";
import { useBankUndo } from "./useBankUndo";
import { MatchingQuestion, type MatchingPicks } from "./MatchingQuestion";
import { SequenceQuestion, sequenceComplete } from "./SequenceQuestion";
import { SuspendedQuestions } from "./SuspendedQuestions";
import { splitSlides } from "./BankSlides";

const FORMAT_LABEL: Record<string, string> = {
  basic: "단답", cloze: "빈칸", list: "나열", ox: "O/X", mcq: "객관식", multi_select: "복수 선택",
  matching: "짝짓기", sequence: "순서",
};

const RATINGS: { rating: BankRating; grade: string }[] = [
  { rating: "Again", grade: "again" },
  { rating: "Hard", grade: "hard" },
  { rating: "Good", grade: "good" },
  { rating: "Easy", grade: "easy" },
];

export type BatchStudy = {
  lectures: { subject: string; runId: string }[];
  resumeLecture?: { subject: string; runId: string };
  onProgress: (next: BankNext) => void;
};

export function BankSolve({ base: initialBase, lecture: initialLecture, onFinished, batch }: {
  base: string; lecture: { subject: string; runId: string }; onFinished: (summary: BankSession | null) => void;
  batch?: BatchStudy;
}) {
  const isAdmin = Boolean(useMe()?.isAdmin);
  const [current, setCurrent] = useState<BankNext | null>(null);
  const activeLecture = useRef(batch ? batch.resumeLecture ?? null : initialLecture);
  const lecture = current?.lecture ?? initialLecture;
  const base = batch ? `/api/lectures/${encodeURIComponent(lecture.subject)}/${encodeURIComponent(lecture.runId)}/bank` : initialBase;
  const [answer, setAnswer] = useState<BankAnswer | null>(null);
  const [answerRevision, setAnswerRevision] = useState(0);
  const [picked, setPicked] = useState<Set<string>>(new Set());
  const [matches, setMatches] = useState<MatchingPicks>({});
  const [activeMatch, setActiveMatch] = useState(0);
  const [order, setOrder] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [reporting, setReporting] = useState(false);
  const [actionMessage, setActionMessage] = useState("");
  // 회차를 끝내지 않고 지도와 진행도를 본다. 열 때마다 새로 읽는다 — 방금 매긴 평가가 숙련도에 들어가 있다.
  const [peek, setPeek] = useState<BankRead | null>(null);
  const restore = useCallback((got: BankNext) => {
    if (got.lecture) activeLecture.current = got.lecture;
    batch?.onProgress(got);
    setCurrent(got); setAnswer(got.answer ?? null); setPicked(new Set()); setReporting(false); setActionMessage("");
    setMatches({}); setActiveMatch(0);
    setOrder([]);
    window.scrollTo(0, 0);
  }, [batch]);
  const batchUndo = useCallback((token: string) => api<BankNext>("/api/bank/batch/undo", {
    method: "POST", body: JSON.stringify({ lectures: batch?.lectures, reviewToken: token }),
  }), [batch]);
  const { undo, undoBusy, pending } = useBankUndo(base, current?.undoToken, restore, setError, busy || Boolean(peek), batch ? batchUndo : undefined);
  const slides = useMemo(() => new SlidePreloader(), [base]);
  const prepared = usePreparedBankAnswer(base, current?.reviewToken, slides, answerRevision);
  useEffect(() => { slides.warm(splitSlides(current?.preloadSlides ?? []).primary.map(slide => slide.url)); }, [current, slides]);

  const next = useCallback(async () => {
    if (pending.current) return;
    pending.current = true;
    setBusy(true);
    setError("");
    try {
      const got = await api<BankNext>(batch ? "/api/bank/batch/next" : `${initialBase}/next?choiceProtocol=true`, {
        method: "POST", ...(batch ? { body: JSON.stringify({ lectures: batch.lectures, resumeLecture: activeLecture.current }) } : {}),
      });
      if (got.lecture) activeLecture.current = got.lecture;
      batch?.onProgress(got);
      invalidateTimetable();
      if (!got.question && !got.waiting) {
        onFinished(got.summary ?? null);
        return;
      }
      setCurrent(got);
      setAnswer(got.answer ?? null);
      setPicked(new Set());
      setMatches({}); setActiveMatch(0);
      setOrder([]);
      setReporting(false);
      setActionMessage("");
      window.scrollTo(0, 0);
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      pending.current = false;
      setBusy(false);
    }
  }, [initialBase, batch, onFinished]);
  useEffect(() => void next(), [next]);

  const showChoices = useCallback(async () => {
    if (!current?.reviewToken || busy || pending.current) return;
    pending.current = true; setBusy(true); setError("");
    try {
      const got = await api<Pick<BankNext, "question" | "choicesShown">>(`${base}/options`, {
        method: "POST", body: JSON.stringify({ reviewToken: current.reviewToken }),
      });
      setCurrent(old => old ? { ...old, ...got } : old);
    } catch (cause) { setError((cause as Error).message); }
    finally { pending.current = false; setBusy(false); }
  }, [base, current, busy]);

  const reveal = useCallback(async () => {
    if (!current?.reviewToken || answer || busy || pending.current) return;
    if (current.question?.format === "matching"
      && !current.question.matching_left.every(left => current.question!.matching_right.includes(matches[left]))) return;
    if (current.question?.format === "sequence" && !sequenceComplete(current.question, order)) return;
    pending.current = true;
    setBusy(true);
    setError("");
    // Display immediately; grading stays disabled until the click is recorded.
    if (prepared.answer) setAnswer(prepared.answer);
    try {
      setAnswer(await api<BankAnswer>(`${base}/reveal`, {
        method: "POST", body: JSON.stringify({ reviewToken: current.reviewToken }),
      }));
    } catch (cause) {
      setAnswer(null);
      setError((cause as Error).message);
    } finally {
      pending.current = false;
      setBusy(false);
    }
  }, [base, current, answer, busy, prepared, matches, order]);

  const rate = useCallback(async (rating: BankRating) => {
    if (!current?.reviewToken || !answer || busy || pending.current) return;
    pending.current = true;
    setBusy(true);
    setError("");
    try {
      await api(`${base}/rate`, { method: "POST", body: JSON.stringify({ reviewToken: current.reviewToken, rating }) });
      invalidateTimetable();
    } catch (cause) {
      setError((cause as Error).message);
      pending.current = false;
      setBusy(false);
      return;
    }
    pending.current = false;
    await next();
  }, [base, current, answer, busy, next]);

  const suspend = useCallback(async () => {
    if (!current?.question || !current.reviewToken || busy || pending.current || peek) return;
    pending.current = true; setBusy(true); setError("");
    try {
      await api(`${base}/questions/${encodeURIComponent(current.question.question_id)}/suspension`, {
        method: "PUT", body: JSON.stringify({ suspended: true, reviewToken: current.reviewToken }),
      });
      invalidateTimetable();
      setCurrent(null); setAnswer(null);
    } catch (cause) {
      setError((cause as Error).message);
      return;
    } finally { pending.current = false; setBusy(false); }
    await next();
  }, [base, current, busy, peek, next]);

  async function changeTier(tier: BankTier | null) {
    if (!current?.question || !current.reviewToken || busy || undoBusy || pending.current) return;
    pending.current = true; setBusy(true); setError(""); setActionMessage("");
    try {
      const got = await api<Pick<BankNext, "question">>(`${base}/questions/${encodeURIComponent(current.question.question_id)}/priority`, {
        method: "PUT", body: JSON.stringify({ tier, reviewToken: current.reviewToken }),
      });
      setCurrent(old => old ? { ...old, question: got.question } : old);
      invalidateTimetable();
      setActionMessage(tier === null ? "원래 중요도로 되돌렸습니다." : `내 문제의 중요도를 ${tier}로 저장했습니다.`);
    } catch (cause) { setError((cause as Error).message); }
    finally { pending.current = false; setBusy(false); }
  }

  async function end() {
    if (!current?.session || busy || pending.current) return;
    pending.current = true;
    setBusy(true);
    try {
      if (batch) {
        await api("/api/bank/batch/session/end", { method: "POST", body: JSON.stringify({ lectures: batch.lectures }) });
        onFinished({ ...current.session, reason: "user_finished" });
        return;
      }
      const summary = await api<BankSession>(`${base}/session/end`, {
        method: "POST", body: JSON.stringify({ sessionId: current.session.session_id }),
      });
      onFinished(summary);
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      pending.current = false;
      setBusy(false);
    }
  }

  async function openPeek() {
    try {
      setPeek(await api<BankRead>(base));
      window.scrollTo(0, 0);
    } catch (cause) {
      setError((cause as Error).message);
    }
  }

  // 키보드 — 기존 웹 풀이와 같다. Space·Enter 로 펴고, 1–4 로 찍는다. 지도를 보는 동안은 안 받는다.
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.defaultPrevented || event.repeat || event.isComposing || event.ctrlKey || event.metaKey || event.altKey) return;
      if (document.querySelector("dialog[open], [role='dialog'][aria-modal='true']")) return;
      if (peek) return;
      if (event.target instanceof HTMLElement && event.target.closest("input, textarea, select, [role='textbox'], [contenteditable]:not([contenteditable='false'])")) return;
      if (event.key === "5" && !event.shiftKey) {
        event.preventDefault();
        void suspend();
        return;
      }
      if (event.target instanceof HTMLElement && event.target.closest("button, a, summary")) return;
      if ((event.key === " " || event.key === "Enter") && !answer) {
        event.preventDefault();
        if (current?.question?.mcq_mode === "recall_first" && !current.choicesShown) void showChoices();
        else void reveal();
      } else if (answer && ["1", "2", "3", "4"].includes(event.key)) {
        event.preventDefault();
        void rate(RATINGS[Number(event.key) - 1].rating);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [answer, reveal, rate, peek, current, showChoices, suspend]);

  if (current?.waiting) return <div className="quiz bank-start">
    <h2>지금 풀 수 있는 분량을 마쳤어요!</h2>
    <p>어려웠던 내용은 복습으로 이어갈게요. 수고했어요!</p>
    <Link className="daily-goal-main" to="/">다른 강의 학습하기</Link>{" "}
    <button className="is-quiet" disabled={busy} onClick={() => void end()}>학습 기록 보기</button>
    {current.undoToken ? <button className="quiz-undo" disabled={busy || undoBusy} onClick={() => void undo()} aria-keyshortcuts="Z Control+Z">되돌리기 <kbd>Z</kbd></button> : null}
    {error ? <p className="notice is-error">{error}</p> : null}
  </div>;
  if (!current?.question) return error ? <div className="quiz"><p className="notice is-error">{error}</p>
    <button onClick={() => void next()}>다시 시도</button></div> : <p className="notice">불러오는 중…</p>;
  const q = current.question;
  const hiddenChoices = q.mcq_mode === "recall_first" && !current.choicesShown && !answer;
  const session = current.session;

  if (peek) {
    const live = peek.session ?? session;
    return (
      <div className="quiz bank-start">
        <p className="quiz-progress bank-progress">
          <button className="is-quiet" onClick={() => setPeek(null)}>← 문제로 돌아가기</button>
          <span>{current.examDate ? daysLabel(current.examDate) : ""}</span>
        </p>
        <DailyGoal plan={current.batchGoal ?? peek.lectureGoal} />
        <SuspendedQuestions base={base} info={peek} onChanged={() => void openPeek()} />
        {peek.conceptMap?.length ? <ConceptMap concepts={peek.conceptMap} /> : null}
        {live ? (
          <details className="bank-session-details"><summary>이번 학습 기록 보기</summary>
          <p className="bank-note">
            이번 회차 {live.reviewed}{live.size == null ? "" : ` / ${live.size}`}문항 · Again {live.ratings.Again} · Hard {live.ratings.Hard} · Good{" "}
            {live.ratings.Good} · Easy {live.ratings.Easy} — Core 숙련 {Math.round(live.core_before * 100)}% →{" "}
            {Math.round(live.core_after * 100)}%
          </p>
          </details>
        ) : null}
      </div>
    );
  }

  return (
    <>
      <div className="quiz">
        <DailyGoal plan={current.batchGoal ?? current.lectureGoal} collapsible />
        <p className="quiz-progress bank-progress">
          <span>
            {session ? session.size == null ? `${session.reviewed}문항 완료` : `${session.reviewed + 1} / ${session.size}` : ""}
            {current.examDate ? ` · ${daysLabel(current.examDate)}` : ""}
          </span>
          <span className="bank-tags">
            <label className="bank-tier-control" title="내 계정의 이 문제에 적용됩니다. Core: 학습목표·기출 / Important: 강조·임상 중요 / Optional: 기타 세부사항">
              내 중요도{" "}
              <select aria-label="내 문제 중요도" value={q.tier} disabled={busy || undoBusy}
                onChange={event => void changeTier(event.target.value as BankTier)}>
                <option value="Core">Core</option>
                <option value="Important">Important</option>
                <option value="Optional">Optional</option>
              </select>
            </label>
            {q.targetMastery != null ? <span className="bank-target" title="현재 문제의 목표 숙련도이며 실제 기억률을 측정한 값은 아닙니다">
              {" · "}목표 {Math.round(q.targetMastery * 100)}%
            </span> : null}
            {q.personalTier ? <button className="is-quiet bank-tier-reset" disabled={busy || undoBusy}
              title={`원래 중요도: ${q.originalTier ?? ""}`} onClick={() => void changeTier(null)}>원래대로</button> : null}
            {q.advanced ? <span className="bank-source-badge" title="중요도와 독립된 추가 추론·개념 연계 문항">Advanced · 심화</span> : null}
            {" · "}{DIRECTION_LABEL[q.retrieval_direction] ?? q.retrieval_direction} ·{" "}
            {q.mcq_mode === "recall_first" ? "기억 확인형 객관식" : q.mcq_mode === "comparison" ? "구별·판단형 객관식" : FORMAT_LABEL[q.format] ?? q.format}
            {q.conflict_id ? <span className="bank-source-badge">자료 간 차이</span> : null}
          </span>
          <span className="bank-progress-actions">
            {current.undoToken ? <button className="quiz-undo" disabled={busy || undoBusy} onClick={() => void undo()} aria-keyshortcuts="Z Control+Z">되돌리기 <kbd>Z</kbd></button> : null}
            <button className="is-quiet" onClick={() => void openPeek()}>개념 지도</button>
            <button className="is-quiet" onClick={() => void end()}>{batch ? "쉬기" : "회차 마치기"}</button>
          </span>
        </p>

        <QuestionBody question={q} answer={answer} picked={picked} showOptions={!hiddenChoices} disabled={busy || undoBusy}
          sequence={q.format === "sequence" ? <SequenceQuestion question={q} answer={answer} order={order}
            disabled={busy || undoBusy} onSelect={item => {
              if (answer || busy || undoBusy) return;
              setOrder(old => old.includes(item) ? old : [...old, item]);
            }} onRemove={index => {
              if (answer || busy || undoBusy) return;
              setOrder(old => old.filter((_, position) => position !== index));
            }} onReset={() => { if (!answer && !busy && !undoBusy) setOrder([]); }} /> : undefined}
          matching={q.format === "matching" ? <MatchingQuestion question={q} answer={answer} picks={matches}
            active={activeMatch} disabled={busy || undoBusy} onActive={setActiveMatch} onMatch={(right) => {
              if (answer || busy || undoBusy) return;
              const fresh = { ...matches, [q.matching_left[activeMatch]]: right };
              setMatches(fresh);
              const following = q.matching_left.findIndex((left, index) => index > activeMatch && !fresh[left]);
              const unfilled = q.matching_left.findIndex(left => !fresh[left]);
              setActiveMatch(following >= 0 ? following : unfilled >= 0 ? unfilled : activeMatch);
            }} /> : undefined}
          onPick={(id) => {
          if (answer || busy || undoBusy) return;
          setPicked((old) => {
            const fresh = new Set(q.format === "mcq" ? [] : old);
            if (old.has(id) && q.format !== "mcq") fresh.delete(id);
            else fresh.add(id);
            return fresh;
          });
        }} />

        <div className="bank-question-actions">
          {q.personalEdited ? <span className="tag">내 수정본</span> : null}
          {actionMessage ? <span role="status">{actionMessage}</span> : null}
          {isAdmin ? <a className="quiz-fix"
            href={`/admin/bank-cards/${encodeURIComponent(lecture.subject)}/${encodeURIComponent(lecture.runId)}?question=${encodeURIComponent(q.question_id)}`}
            target="_blank" rel="noreferrer">공용 문제 수정</a> : null}
          <button className="is-quiet" onClick={() => setReporting(true)}>⚑ 수정·제보</button>
        </div>
        {reporting ? <PersonalQuestionDialog base={base} questionId={q.question_id} answerVisible={Boolean(answer)}
          onClose={() => setReporting(false)} onSaved={(result, reset) => {
            setCurrent(old => old ? { ...old, question: result.question } : old);
            setAnswerRevision(value => value + 1);
            if (answer) setAnswer(result.answer);
            setReporting(false);
            setActionMessage(reset ? "원본으로 되돌렸습니다." : result.reported
              ? (result.highlighted ? "강조 제보를 보냈습니다." : "관리자에게 전달했습니다.") + (result.question.personalEdited ? " 내 수정본을 저장했습니다." : "") : "내 수정본을 저장했습니다.");
          }} /> : null}

        {answer ? (
          <>
            <hr className="quiz-line" />
            <AnswerBody question={q} answer={answer} preload={slides} />
          </>
        ) : null}
        {error ? <p className="notice is-error">{error}</p> : null}
      </div>

      <div className="quiz-bar">
        {answer ? (
          RATINGS.map(({ rating, grade }, index) => (
            <button key={rating} className={`quiz-grade is-${grade}`} disabled={busy || undoBusy} onClick={() => void rate(rating)}>
              <span className="quiz-grade-name">
                {rating}
                <kbd>{index + 1}</kbd>
              </span>
            </button>
          ))
        ) : (
          <button className="quiz-submit" disabled={busy || undoBusy || (q.format === "matching"
            && !q.matching_left.every(left => q.matching_right.includes(matches[left])))
            || (q.format === "sequence" && !sequenceComplete(q, order))} onClick={() => void (hiddenChoices ? showChoices() : reveal())}>
            {busy ? "펴는 중…" : <>{hiddenChoices ? "선지 보기" : q.format === "matching" || q.format === "sequence" ? "채점하기" : "답 보기"} <kbd>space</kbd></>}
          </button>
        )}
        <button className="bank-suspend" disabled={busy || undoBusy} aria-keyshortcuts="5"
          title="내 학습에서 제외하고 다음 문제로 넘어갑니다" onClick={() => void suspend()}>
          <span className="quiz-grade-name">비활성화 <kbd>5</kbd></span>
        </button>
      </div>
    </>
  );
}

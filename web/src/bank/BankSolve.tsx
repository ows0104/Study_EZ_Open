import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { bankCatalogHref } from "../links";
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
import { usePreparedBankNext } from "./usePreparedBankNext";
import { DailyGoal } from "./DailyGoal";
import { useBankUndo } from "./useBankUndo";
import { MatchingQuestion, type MatchingPicks } from "./MatchingQuestion";
import { SequenceQuestion, sequenceComplete } from "./SequenceQuestion";
import { SuspendedQuestions } from "./SuspendedQuestions";
import { AddQuestionDialog } from "./PersonalQuestions";
import { splitSlides } from "./BankSlides";
import { matchingLayout } from "./presentation";
import { useBankBuffer } from "./useBankBuffer";
import { useStudyWrites } from "./useStudyWrites";

const FORMAT_LABEL: Record<string, string> = {
  basic: "단답", cloze: "빈칸", list: "나열", ox: "O/X", mcq: "객관식", multi_select: "복수 선택",
  matching: "짝짓기", sequence: "순서",
};

const CommonQuestionDialog = lazy(() => import("./CommonQuestionDialog").then(module => ({ default: module.CommonQuestionDialog })));

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
  onSavingChange?: (saving: boolean) => void;
};

export function BankSolve({ base: initialBase, lecture: initialLecture, onFinished, batch }: {
  base: string; lecture: { subject: string; runId: string }; onFinished: (summary: BankSession | null) => void;
  batch?: BatchStudy;
}) {
  const isAdmin = Boolean(useMe()?.isAdmin);
  const [current, setCurrent] = useState<BankNext | null>(null);
  const [transition, setTransition] = useState<BankNext | null>(null);
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
  const [commonEditing, setCommonEditing] = useState(false);
  const [addingQuestion, setAddingQuestion] = useState(false);
  const questionMenu = useRef<HTMLDetailsElement>(null);
  const [actionMessage, setActionMessage] = useState("");
  const presentedAt = useRef(Date.now());
  const visibleToken = useRef<string | undefined>(undefined);
  const { saving, enqueue, cancel, count: writeCount } = useStudyWrites();
  const [acknowledgement, setAcknowledgement] = useState(0);
  const onSavingChange = batch?.onSavingChange;
  useEffect(() => {
    onSavingChange?.(saving);
    return () => onSavingChange?.(false);
  }, [onSavingChange, saving]);
  // 회차를 끝내지 않고 지도와 진행도를 본다. 열 때마다 새로 읽는다 — 방금 매긴 평가가 숙련도에 들어가 있다.
  const [peek, setPeek] = useState<BankRead | null>(null);
  const restore = useCallback((got: BankNext) => {
    presentedAt.current = Date.now();
    visibleToken.current = got.reviewToken;
    setTransition(null);
    setCommonEditing(false);
    questionMenu.current?.removeAttribute("open");
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
  const undoRestore = useCallback((got: BankNext) => {
    cancel(); setAnswerRevision(value => value + 1); restore(got);
  }, [cancel, restore]);
  const { undo, undoBusy, pending } = useBankUndo(base, current?.undoToken, undoRestore, setError, busy || saving || Boolean(peek) || commonEditing, batch ? batchUndo : undefined);
  const slides = useMemo(() => new SlidePreloader(), []);
  const buffer = useBankBuffer(base, current?.reviewToken, slides, answerRevision, acknowledgement, batch?.lectures);
  const prepared = usePreparedBankAnswer(base, buffer.getFor(current) ? undefined : current?.reviewToken, slides, answerRevision);
  const preparedNext = usePreparedBankNext(base, current?.reviewToken, !!answer && !busy && !saving && !buffer.getFor(current), slides, answerRevision, batch?.lectures);
  useEffect(() => { slides.warm(splitSlides(current?.preloadSlides ?? []).primary.map(slide => slide.url)); }, [current, slides]);

  const acceptNext = useCallback((got: BankNext) => {
    setTransition(null);
    invalidateTimetable();
    if (!got.question && !got.waiting) {
      batch?.onProgress(got);
      onFinished(got.summary ?? null);
    } else restore(got);
  }, [batch, onFinished, restore]);

  const next = useCallback(async () => {
    if (pending.current) return;
    pending.current = true;
    setBusy(true);
    setError("");
    try {
      const got = await api<BankNext>(batch ? "/api/bank/batch/next" : `${initialBase}/next?choiceProtocol=true`, {
        method: "POST", ...(batch ? { body: JSON.stringify({ lectures: batch.lectures, resumeLecture: activeLecture.current }) } : {}),
      });
      acceptNext(got);
    } catch (cause) {
      setTransition(null);
      setError((cause as Error).message);
    } finally {
      pending.current = false;
      setBusy(false);
    }
  }, [initialBase, batch, acceptNext]);
  useEffect(() => void next(), [next]);

  const showChoices = useCallback(async () => {
    if (!current?.reviewToken || busy || pending.current) return;
    const frame = buffer.getFor(current);
    const rollback = () => { restore(current); setAnswer(answer); setPicked(picked); setMatches(matches); setOrder(order); };
    const accepted = enqueue(`${current.reviewToken}:options`, async () => {
      const got = await api<Pick<BankNext, "question" | "choicesShown">>(`${base}/options`, {
        method: "POST", body: JSON.stringify({ reviewToken: current.reviewToken }),
      });
      setCurrent(old => old?.reviewToken === current.reviewToken ? { ...old, ...got } : old);
      if (!frame) { pending.current = false; setBusy(false); }
    }, cause => { rollback(); pending.current = false; setBusy(false); setError(cause.message); });
    if (!accepted) return;
    setError("");
    if (frame) setCurrent({ ...current, question: frame.options, choicesShown: true });
    else { pending.current = true; setBusy(true); }
  }, [base, current, busy, buffer, enqueue, restore, answer, picked, matches, order]);

  const reveal = useCallback(async () => {
    if (!current?.reviewToken || answer || busy || pending.current) return;
    const frame = buffer.getFor(current);
    const responseTimeMs = Math.min(86_400_000, Math.max(0, Date.now() - presentedAt.current));
    const accepted = enqueue(`${current.reviewToken}:reveal`, async () => {
      const got = await api<BankAnswer>(`${base}/reveal`, {
        method: "POST", body: JSON.stringify({ reviewToken: current.reviewToken, responseTimeMs }),
      });
      // Acknowledging an earlier card must never replace the visible card's answer.
      if (!frame) { setAnswer(got); pending.current = false; setBusy(false); }
    }, cause => {
      restore(current); setAnswer(null); setPicked(picked); setMatches(matches); setOrder(order);
      pending.current = false; setBusy(false); setError(cause.message);
    });
    if (!accepted) return;
    setError("");
    setAnswer(frame?.answer ?? prepared.answer);
    if (!frame) { pending.current = true; setBusy(true); }
  }, [base, current, answer, busy, prepared, matches, order, picked, buffer, enqueue, restore]);

  const rate = useCallback(async (rating: BankRating) => {
    if (!current?.reviewToken || !answer || busy || pending.current) return;
    const preview = buffer.getFor(current)?.previews[rating];
    const optimistic = !!preview?.question && !!preview.reviewToken;
    const accepted = enqueue(`${current.reviewToken}:rate`, async () => {
      const result = await api<{ next?: BankNext; advanceFailed?: boolean }>(`${base}/rate`, {
        method: "POST", body: JSON.stringify({ reviewToken: current.reviewToken, rating, advance: true, retrySafe: true,
          selectionTicket: preview?.selectionTicket ?? preparedNext.previews[rating]?.selectionTicket,
          ...(batch ? { lectures: batch.lectures } : {}) }),
      });
      invalidateTimetable();
      // A committed review is never retried just because selecting /next failed.
      let got = result?.next;
      if (!got) {
        try {
          got = await api<BankNext>(batch ? "/api/bank/batch/next" : `${initialBase}/next?choiceProtocol=true`, {
            method: "POST", ...(batch ? { body: JSON.stringify({ lectures: batch.lectures }) } : {}),
          });
        } catch (cause) {
          cancel(); buffer.clear(); setCurrent(null); setAnswer(null);
          pending.current = false; setBusy(false); setError((cause as Error).message);
          return;
        }
      }
      const matchesPrediction = optimistic && got.reviewToken === preview.reviewToken
        && JSON.stringify(got.question) === JSON.stringify(preview.question)
        && got.lecture?.subject === preview.lecture?.subject && got.lecture?.runId === preview.lecture?.runId;
      if (matchesPrediction) {
        setCurrent(old => old && old.reviewToken === got.reviewToken ? { ...old,
          session: got.session, lectureGoal: got.lectureGoal, batchGoal: got.batchGoal,
          undoToken: got.undoToken, undoLecture: got.undoLecture } : old);
        if (visibleToken.current === got.reviewToken) batch?.onProgress(got);
      } else {
        cancel(); buffer.clear(); acceptNext(got);
        pending.current = false; setBusy(false);
        if (optimistic) setActionMessage("평가 결과에 맞춰 다음 문제를 갱신했습니다.");
      }
      setAcknowledgement(value => value + 1);
      if (!optimistic) { pending.current = false; setBusy(false); }
    }, cause => {
      buffer.clear(); restore(current); setAnswer(answer); setPicked(picked); setMatches(matches); setOrder(order);
      pending.current = false; setBusy(false); setError(cause.message);
      setAcknowledgement(value => value + 1);
    });
    if (!accepted) return;
    setError("");
    if (optimistic) restore(preview);
    else {
      pending.current = true; setBusy(true);
      const legacyPreview = preparedNext.previews[rating];
      if (legacyPreview?.question) { setTransition(legacyPreview); window.scrollTo(0, 0); }
    }
  }, [base, initialBase, current, answer, busy, batch, acceptNext, preparedNext, buffer, enqueue, cancel, restore, picked, matches, order]);

  const suspend = useCallback(async () => {
    if (!current?.question || !current.reviewToken || busy || pending.current || peek || writeCount.current) return;
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
    if (!current?.question || !current.reviewToken || busy || undoBusy || pending.current || writeCount.current) return;
    pending.current = true; setBusy(true); setError(""); setActionMessage("");
    try {
      const got = await api<Pick<BankNext, "question" | "lectureGoal"> & { rescheduled?: boolean }>(`${base}/questions/${encodeURIComponent(current.question.question_id)}/priority`, {
        method: "PUT", body: JSON.stringify({ tier, reviewToken: current.reviewToken }),
      });
      setCurrent(old => old ? { ...old, question: got.question, lectureGoal: got.lectureGoal ?? old.lectureGoal } : old);
      setAnswerRevision(value => value + 1);
      invalidateTimetable();
      setActionMessage((tier === null ? "원래 중요도로 되돌렸습니다." : `내 문제의 중요도를 ${tier}로 저장했습니다.`)
        + (got.rescheduled ? " 복습 예정일도 새 목표로 다시 계산했습니다." : ""));
    } catch (cause) { setError((cause as Error).message); }
    finally { pending.current = false; setBusy(false); }
  }

  async function end() {
    if (!current?.session || busy || pending.current || writeCount.current) return;
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
    if (writeCount.current) return;
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
      if (peek || commonEditing) return;
      if (event.target instanceof HTMLElement && event.target.closest("input, textarea, select, [role='textbox'], [contenteditable]:not([contenteditable='false'])")) return;
      if (event.key === "5" && !event.shiftKey) {
        event.preventDefault();
        void suspend();
        return;
      }
      const target = event.target instanceof HTMLElement ? event.target : null;
      const questionChoice = target?.closest(".bank-match, .bank-sequence, .bank-options");
      // Clicked choices retain focus. Space should submit the completed question,
      // rather than activate the last choice again (or silently do nothing).
      if (target?.closest("button, a, summary")) {
        if (!questionChoice) return;
        if (!answer) {
          const q = current?.question;
          const complete = q?.format === "matching" ? q.matching_left.every(left => q.matching_right.includes(matches[left]))
            : q?.format === "sequence" ? sequenceComplete(q, order) : picked.size > 0;
          if (event.key !== " " || !complete) return;
        }
      }
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
  }, [answer, reveal, rate, peek, current, showChoices, suspend, matches, order, picked, commonEditing]);

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
  const displayed = transition ?? current;
  const q = displayed.question!;
  const visibleAnswer = transition ? null : answer;
  const hiddenChoices = q.mcq_mode === "recall_first" && !displayed.choicesShown && !visibleAnswer;
  const session = displayed.session;

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
            {live.ratings.Good} · Easy {live.ratings.Easy} — 핵심·필수 숙련 {Math.round(live.core_before * 100)}% →{" "}
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
        <DailyGoal plan={displayed.batchGoal ?? displayed.lectureGoal} collapsible />
        <div className="quiz-progress bank-progress">
          <span>
            {session ? session.size == null ? `${session.reviewed}문항 완료` : `${session.reviewed + 1} / ${session.size}` : ""}
            {displayed.examDate ? ` · ${daysLabel(displayed.examDate)}` : ""}
          </span>
          <span className="bank-tags">
            <label className={`bank-tier-control${q.tier === "Essential" ? " is-essential" : ""}`} title="내 계정의 이 문제에 적용됩니다. Must-Know: 교수의 직접·간접적인 필수 지식 강조·출제 예고 / Core: 학습목표·기출 / Important: 강조·임상 중요 / Optional: 기타 세부사항">
              내 중요도{" "}
              <select aria-label="내 문제 중요도" value={q.tier} disabled={busy || undoBusy || saving}
                onChange={event => void changeTier(event.target.value as BankTier)}>
                <option value="Essential">★ Must-Know</option>
                <option value="Core">Core</option>
                <option value="Important">Important</option>
                <option value="Optional">Optional</option>
              </select>
            </label>
            {q.targetMastery != null ? <span className="bank-target" title="현재 문제의 목표 숙련도이며 실제 기억률을 측정한 값은 아닙니다">
              {" · "}목표 {Math.round(q.targetMastery * 100)}%
            </span> : null}
            {q.personalTier ? <button className="is-quiet bank-tier-reset" disabled={busy || undoBusy || saving}
              title={`원래 중요도: ${q.originalTier ?? ""}`} onClick={() => void changeTier(null)}>원래대로</button> : null}
            {q.advanced ? <span className="bank-source-badge" title="중요도와 독립된 추가 추론·개념 연계 문항">Advanced · 심화</span> : null}
            {" · "}{DIRECTION_LABEL[q.retrieval_direction] ?? q.retrieval_direction} ·{" "}
            {q.mcq_mode === "recall_first" ? "기억 확인형 객관식" : q.mcq_mode === "comparison" ? "구별·판단형 객관식" : FORMAT_LABEL[q.format] ?? q.format}
            {q.conflict_id ? <span className="bank-source-badge">자료 간 차이</span> : null}
          </span>
          <div className="bank-progress-actions">
            {saving ? <span role="status">저장 중…</span> : null}
            <button className="is-quiet" disabled={busy || undoBusy || saving} onClick={() => void openPeek()}>개념 지도</button>
            <button className="is-quiet" disabled={busy || undoBusy || saving} onClick={() => void end()}>쉬기</button>
            <details className="bank-question-menu" ref={questionMenu}>
              <summary>문제 변경/추가/삭제</summary>
              <div className="bank-question-menu-items" onClick={event => {
                if ((event.target as HTMLElement).closest("button, a")) questionMenu.current?.removeAttribute("open");
              }}>
                <button className="is-quiet" disabled={busy || undoBusy || saving} onClick={() => setAddingQuestion(true)}>＋ 문제 추가</button>
                <button className="is-quiet" disabled={busy || undoBusy || saving} onClick={() => setReporting(true)}>문제 수정·제보</button>
                {isAdmin && !transition ? <button className="is-quiet" disabled={busy || undoBusy || saving}
                  onClick={() => setCommonEditing(true)}>공용 문제 수정</button> : null}
                <button className="is-quiet bank-suspend" disabled={busy || undoBusy || saving} aria-keyshortcuts="5"
                  title="내 학습에서 제외하고 다음 문제로 넘어갑니다" onClick={() => void suspend()}>
                  비활성화 <kbd>5</kbd>
                </button>
                <Link to={bankCatalogHref(lecture)}>전체 문제</Link>
              </div>
            </details>
          </div>
        </div>

        <QuestionBody question={q} answer={visibleAnswer} picked={transition ? new Set() : picked} showOptions={!hiddenChoices} disabled={busy || undoBusy}
          sequence={q.format === "sequence" ? <SequenceQuestion question={q} answer={visibleAnswer} order={transition ? [] : order}
            disabled={busy || undoBusy} onSelect={item => {
              if (answer || busy || undoBusy) return;
              setOrder(old => old.includes(item) ? old : [...old, item]);
            }} onRemove={index => {
              if (answer || busy || undoBusy) return;
              setOrder(old => old.filter((_, position) => position !== index));
            }} onReset={() => { if (!answer && !busy && !undoBusy) setOrder([]); }} /> : undefined}
          matching={q.format === "matching" ? <MatchingQuestion question={q} answer={visibleAnswer} picks={transition ? {} : matches}
            active={transition ? 0 : activeMatch} disabled={busy || undoBusy} onActive={setActiveMatch} onMatch={(right) => {
              if (answer || busy || undoBusy) return;
              const left = matchingLayout(q).left;
              const fresh = { ...matches, [left[activeMatch]]: right };
              setMatches(fresh);
              const following = left.findIndex((item, index) => index > activeMatch && !fresh[item]);
              const unfilled = left.findIndex(item => !fresh[item]);
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
        </div>
        {commonEditing ? <Suspense fallback={<p role="status">수정창을 여는 중…</p>}>
          <CommonQuestionDialog subject={lecture.subject} runId={lecture.runId} questionId={q.question_id}
            onClose={() => setCommonEditing(false)} onSaved={() => {
              setCommonEditing(false);
              setAnswerRevision(value => value + 1);
              setCurrent(null); setAnswer(null);
              void next();
            }} />
        </Suspense> : null}
        {addingQuestion ? <AddQuestionDialog base={base} sourceQuestionId={q.question_id} onClose={() => setAddingQuestion(false)} onSaved={() => {
          setAddingQuestion(false); setAnswerRevision(value => value + 1);
          setActionMessage("내 문제를 추가했습니다.");
          void api<BankRead>(base).then(info => setCurrent(old => old ? { ...old, lectureGoal: info.lectureGoal } : old))
            .catch(cause => setError((cause as Error).message));
        }} /> : null}
        {reporting ? <PersonalQuestionDialog base={base} questionId={q.question_id} answerVisible={Boolean(answer)}
          onClose={() => setReporting(false)} onSaved={(result, reset) => {
            setCurrent(old => old ? { ...old, question: result.question } : old);
            setAnswerRevision(value => value + 1);
            if (answer) setAnswer(result.answer);
            setReporting(false);
            setActionMessage(reset ? "원본으로 되돌렸습니다." : result.reported
              ? (result.highlighted ? "강조 제보를 보냈습니다." : "관리자에게 전달했습니다.") + (result.question.personalEdited ? " 내 수정본을 저장했습니다." : "") : "내 수정본을 저장했습니다.");
          }} /> : null}

        {visibleAnswer ? (
          <>
            <hr className="quiz-line" />
            <AnswerBody question={q} answer={visibleAnswer} preload={slides} />
          </>
        ) : null}
        {error ? <p className="notice is-error">{error}</p> : null}
      </div>

      <div className="quiz-bar bank-solve-bar">
        <button className="quiz-undo" disabled={!current.undoToken || busy || undoBusy || saving}
          onClick={() => void undo()} aria-keyshortcuts="Z Control+Z">되돌리기 <kbd>Z</kbd></button>
        {visibleAnswer ? (
          RATINGS.map(({ rating, grade }, index) => (
            <button key={rating} className={`quiz-grade is-${grade}`} disabled={busy || undoBusy} onClick={() => void rate(rating)}>
              <span className="quiz-grade-name">
                {rating}
                <kbd>{index + 1}</kbd>
              </span>
            </button>
          ))
        ) : (
          <button className="quiz-submit" disabled={busy || undoBusy} onClick={() => void (hiddenChoices ? showChoices() : reveal())}>
            {busy && !transition ? "펴는 중…" : <>{hiddenChoices ? "선지 보기" : q.format === "matching" || q.format === "sequence" ? "채점하기" : "답 보기"} <kbd>space</kbd></>}
          </button>
        )}
      </div>
    </>
  );
}

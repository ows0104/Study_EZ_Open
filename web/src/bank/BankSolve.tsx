import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { useMe } from "../useMe";
import type { BankAnswer, BankNext, BankRating, BankRead, BankSession } from "../types/bank";
import { ConceptMap } from "./ConceptMap";
import { PersonalQuestionDialog } from "./PersonalQuestionDialog";
import { daysLabel, DIRECTION_LABEL } from "./labels";
import { QuestionBody, AnswerBody } from "./BankQuestion";
import { SlidePreloader } from "../slidePreload";
import { usePreparedBankAnswer } from "./usePreparedBankAnswer";
import { DailyGoal } from "./DailyGoal";
import { useBankUndo } from "./useBankUndo";
import { MatchingQuestion, matchingScore, type MatchingPicks } from "./MatchingQuestion";
import { SequenceQuestion, sequenceComplete, sequenceScore } from "./SequenceQuestion";

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

export function BankSolve({ base, lecture, onFinished }: {
  base: string; lecture: { subject: string; runId: string }; onFinished: (summary: BankSession | null) => void;
}) {
  const isAdmin = Boolean(useMe()?.isAdmin);
  const [current, setCurrent] = useState<BankNext | null>(null);
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
    setCurrent(got); setAnswer(got.answer ?? null); setPicked(new Set()); setReporting(false); setActionMessage("");
    setMatches({}); setActiveMatch(0);
    setOrder([]);
    window.scrollTo(0, 0);
  }, []);
  const { undo, undoBusy, pending } = useBankUndo(base, current?.undoToken, restore, setError, busy || Boolean(peek));
  const slides = useMemo(() => new SlidePreloader(), [base]);
  const prepared = usePreparedBankAnswer(base, current?.reviewToken, slides, answerRevision);
  useEffect(() => { slides.warm(current?.preloadSlides?.map((slide) => slide.url) ?? []); }, [current, slides]);

  const next = useCallback(async () => {
    if (pending.current) return;
    pending.current = true;
    setBusy(true);
    setError("");
    try {
      const got = await api<BankNext>(`${base}/next`, { method: "POST" });
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
  }, [base, onFinished]);
  useEffect(() => void next(), [next]);

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

  const autoResult = current?.question ? matchingScore(current.question, answer, matches)
    ?? sequenceScore(current.question, answer, order) : null;

  const rate = useCallback(async (rating: BankRating) => {
    if (!current?.reviewToken || !answer || busy || pending.current) return;
    pending.current = true;
    setBusy(true);
    setError("");
    try {
      await api(`${base}/rate`, { method: "POST", body: JSON.stringify({ reviewToken: current.reviewToken, rating }) });
    } catch (cause) {
      setError((cause as Error).message);
      pending.current = false;
      setBusy(false);
      return;
    }
    pending.current = false;
    await next();
  }, [base, current, answer, busy, next]);

  async function end() {
    if (!current?.session || busy || pending.current) return;
    pending.current = true;
    setBusy(true);
    try {
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
      if (document.querySelector("dialog[open]")) return;
      if (peek) return;
      if (event.target instanceof HTMLElement && event.target.closest("input, textarea, select, button, a, summary, [contenteditable]:not([contenteditable='false'])")) return;
      if ((event.key === " " || event.key === "Enter") && !answer) {
        event.preventDefault();
        void reveal();
      } else if (answer && autoResult && (event.key === " " || event.key === "Enter")) {
        event.preventDefault();
        void rate(autoResult.rating);
      } else if (answer && !autoResult && ["1", "2", "3", "4"].includes(event.key)) {
        event.preventDefault();
        void rate(RATINGS[Number(event.key) - 1].rating);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [answer, reveal, rate, peek, autoResult]);

  if (current?.waiting) return <div className="quiz bank-start">
    <h2>지금 풀 수 있는 분량을 마쳤어요!</h2>
    <p>어려웠던 내용은 복습으로 이어갈게요. 수고했어요!</p>
    <Link className="daily-goal-main" to="/">다른 강의 학습하기</Link>{" "}
    <button className="is-quiet" disabled={busy} onClick={() => void end()}>학습 기록 보기</button>
    {current.undoToken ? <button className="quiz-undo" disabled={busy || undoBusy} onClick={() => void undo()} aria-keyshortcuts="Z Control+Z">되돌리기 <kbd>Z</kbd></button> : null}
    {error ? <p className="notice is-error">{error}</p> : null}
  </div>;
  if (!current?.question) return error ? <p className="notice is-error">{error}</p> : <p className="notice">불러오는 중…</p>;
  const q = current.question;
  const session = current.session;

  if (peek) {
    const live = peek.session ?? session;
    return (
      <div className="quiz bank-start">
        <p className="quiz-progress bank-progress">
          <button className="is-quiet" onClick={() => setPeek(null)}>← 문제로 돌아가기</button>
          <span>{current.examDate ? daysLabel(current.examDate) : ""}</span>
        </p>
        <DailyGoal plan={peek.lectureGoal} />
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
        <DailyGoal plan={current.lectureGoal} collapsible />
        <p className="quiz-progress bank-progress">
          <span>
            {session ? session.size == null ? `${session.reviewed}문항 완료` : `${session.reviewed + 1} / ${session.size}` : ""}
            {current.examDate ? ` · ${daysLabel(current.examDate)}` : ""}
          </span>
          <span className="bank-tags">
            {q.tier} · {DIRECTION_LABEL[q.retrieval_direction] ?? q.retrieval_direction} ·{" "}
            {FORMAT_LABEL[q.format] ?? q.format}
          </span>
          <span className="bank-progress-actions">
            {current.undoToken ? <button className="quiz-undo" disabled={busy || undoBusy} onClick={() => void undo()} aria-keyshortcuts="Z Control+Z">되돌리기 <kbd>Z</kbd></button> : null}
            <button className="is-quiet" onClick={() => void openPeek()}>개념 지도</button>
            <button className="is-quiet" onClick={() => void end()}>회차 마치기</button>
          </span>
        </p>

        {q.conflict_id ? (
          <p className="bank-conflict">강의자료와 족보가 어긋나는 대목입니다. 답을 보면 무엇이 어떻게 다른지 나옵니다.</p>
        ) : null}

        <QuestionBody question={q} answer={answer} picked={picked}
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
          if (answer) return;
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
              ? "제보를 보냈습니다." + (result.question.personalEdited ? " 내 수정본을 저장했습니다." : "") : "내 수정본을 저장했습니다.");
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
        {answer && autoResult ? (
          <button className="quiz-submit" disabled={busy || undoBusy} onClick={() => void rate(autoResult.rating)}>
            {busy ? "기록 중…" : <>다음 문제 <kbd>space</kbd></>}
          </button>
        ) : answer ? (
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
            || (q.format === "sequence" && !sequenceComplete(q, order))} onClick={() => void reveal()}>
            {busy ? "펴는 중…" : <>{q.format === "matching" || q.format === "sequence" ? "채점하기" : "답 보기"} <kbd>space</kbd></>}
          </button>
        )}
      </div>
    </>
  );
}

import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import type { BankAnswer, BankNext, BankRating, BankRead, BankSession } from "../types/bank";
import { ConceptMap } from "./ConceptMap";
import { FEEDBACK } from "./feedback";
import { daysLabel, DIRECTION_LABEL } from "./labels";
import { QuestionBody, AnswerBody } from "./BankQuestion";
import { SlidePreloader } from "../slidePreload";
import { usePreparedBankAnswer } from "./usePreparedBankAnswer";
import { DailyGoal } from "./DailyGoal";
import { useBankUndo } from "./useBankUndo";

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

export function BankSolve({ base, onFinished }: { base: string; onFinished: (summary: BankSession | null) => void }) {
  const [current, setCurrent] = useState<BankNext | null>(null);
  const [answer, setAnswer] = useState<BankAnswer | null>(null);
  const [picked, setPicked] = useState<Set<string>>(new Set());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [reporting, setReporting] = useState(false);
  // 회차를 끝내지 않고 지도와 진행도를 본다. 열 때마다 새로 읽는다 — 방금 매긴 평가가 숙련도에 들어가 있다.
  const [peek, setPeek] = useState<BankRead | null>(null);
  const restore = useCallback((got: BankNext) => {
    setCurrent(got); setAnswer(got.answer ?? null); setPicked(new Set()); setReporting(false);
    window.scrollTo(0, 0);
  }, []);
  const { undo, undoBusy, pending } = useBankUndo(base, current?.undoToken, restore, setError, busy || Boolean(peek));
  const slides = useMemo(() => new SlidePreloader(), [base]);
  const prepared = usePreparedBankAnswer(base, current?.reviewToken, slides);
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
      setReporting(false);
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
  }, [base, current, answer, busy, prepared]);

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
      } else if (answer && ["1", "2", "3", "4"].includes(event.key)) {
        event.preventDefault();
        void rate(RATINGS[Number(event.key) - 1].rating);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [answer, reveal, rate, peek]);

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

        <QuestionBody question={q} answer={answer} picked={picked} onPick={(id) => {
          if (answer) return;
          setPicked((old) => {
            const fresh = new Set(q.format === "mcq" ? [] : old);
            if (old.has(id) && q.format !== "mcq") fresh.delete(id);
            else fresh.add(id);
            return fresh;
          });
        }} />

        {answer ? (
          <>
            <hr className="quiz-line" />
            <AnswerBody question={q} answer={answer} preload={slides} />
            <div className="bank-feedback">
              {reporting ? (
                <FeedbackForm base={base} questionId={q.question_id} onDone={() => setReporting(false)} />
              ) : (
                <button className="is-quiet" onClick={() => setReporting(true)}>⚑ 문제 있음</button>
              )}
            </div>
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
          <button className="quiz-submit" disabled={busy || undoBusy} onClick={() => void reveal()}>
            {busy ? "펴는 중…" : <>답 보기 <kbd>space</kbd></>}
          </button>
        )}
      </div>
    </>
  );
}

function FeedbackForm({ base, questionId, onDone }: { base: string; questionId: string; onDone: () => void }) {
  const [category, setCategory] = useState<string>("content");
  const [comment, setComment] = useState("");
  const [busy, setBusy] = useState(false);
  async function send() {
    setBusy(true);
    try {
      await api(`${base}/feedback`, { method: "POST", body: JSON.stringify({ questionId, category, comment }) });
      onDone();
    } finally {
      setBusy(false);
    }
  }
  return (
    <span className="bank-feedback-form">
      <select value={category} onChange={(event) => setCategory(event.target.value)}>
        {FEEDBACK.map(([key, label]) => <option key={key} value={key}>{label}</option>)}
      </select>
      <input value={comment} maxLength={2000} placeholder="메모 (선택)" onChange={(e) => setComment(e.target.value)} />
      <button disabled={busy} onClick={() => void send()}>보내기</button>
      <button className="is-quiet" onClick={onDone}>취소</button>
    </span>
  );
}

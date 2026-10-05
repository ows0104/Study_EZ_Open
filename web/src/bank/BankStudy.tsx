import { Fragment, useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../api";
import { ConceptMap } from "./ConceptMap";
import { FEEDBACK } from "./feedback";
import { DIRECTION_LABEL } from "./labels";
import { lectureHref } from "../links";
import { Stem } from "../lecture/Stem";
import type { BankAnswer, BankNext, BankQuestion, BankRating, BankRead, BankSession } from "../types";

/**
 * Quiz Bank 풀이 창(2026-10-04).
 *
 *   회차를 연다(10·20·25·30문항) → 서버가 고른 문항 → 「답 보기」 → Again·Hard·Good·Easy → 다음
 *
 * **고르는 것도 일정도 서버다**(`server/app/study_engine/`). 개념 × 회상 방향마다 숙련도를 두고
 * 중요도·약점·시험까지 남은 날·선행 문항으로 다음 문항을 정한다. 화면은 그리기만 한다 —
 * 두 곳에서 고르면 갈라진다(Main-Quiz 가 `srs.py` 를 화면에 안 두는 것과 같은 까닭).
 *
 * 채점은 스스로 한다(자유회상). 객관식은 골라 볼 수 있지만 그것도 채점이 아니라 회상을 돕는 것이다.
 */
export function BankStudyPage() {
  const { subject = "", runId = "" } = useParams();
  const base = `/api/lectures/${encodeURIComponent(subject)}/${encodeURIComponent(runId)}/bank`;
  const [info, setInfo] = useState<BankRead | null>(null);
  const [error, setError] = useState("");
  const [solving, setSolving] = useState(false);
  const [finished, setFinished] = useState<BankSession | null>(null);

  const load = useCallback(() => {
    api<BankRead>(base)
      .then((answer) => {
        setInfo(answer);
        setSolving(answer.session?.status === "active");
      })
      .catch((cause) => setError((cause as Error).message));
  }, [base]);
  useEffect(load, [load]);

  if (error) return <p className="notice is-error">{error}</p>;
  if (!info) return <p className="notice">불러오는 중…</p>;
  if (!info.summary.usable) return <p className="notice">이 강의의 Quiz Bank 는 아직 공부할 수 없습니다.</p>;

  if (solving) {
    return (
      <BankSolve
        base={base}
        onFinished={(summary) => {
          setFinished(summary);
          setSolving(false);
          load();
        }}
      />
    );
  }
  return (
    <BankStart
      base={base}
      info={info}
      finished={finished}
      lecture={{ subject, runId }}
      onStarted={() => {
        setFinished(null);
        setSolving(true);
      }}
    />
  );
}

function daysLabel(examDate: string) {
  const days = Math.round((Date.parse(`${examDate}T00:00:00+09:00`) - Date.now()) / 86_400_000);
  return days > 0 ? `시험까지 D-${days}` : days === 0 ? "오늘 시험" : "시험일 지남";
}

function BankStart({ base, info, finished, lecture, onStarted }: {
  base: string;
  info: BankRead;
  finished: BankSession | null;
  lecture: { subject: string; runId: string };
  onStarted: () => void;
}) {
  const [size, setSize] = useState(info.defaultSize);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function start() {
    setBusy(true);
    setError("");
    try {
      await api(`${base}/session/start`, { method: "POST", body: JSON.stringify({ size }) });
      onStarted();
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="quiz bank-start">
      <p className="quiz-progress bank-progress">
        <a href={lectureHref(lecture)} target="_blank" rel="noreferrer">강의로</a>
        <span>{daysLabel(info.examDate)} · {info.examDate}</span>
      </p>
      <h2>Quiz Bank</h2>
      <p className="bank-note">
        {info.summary.questionCount}문항 · 개념 {info.summary.conceptCount}개. 다음 문항은 지금의 숙련도와 시험까지
        남은 날로 고릅니다.
      </p>
      {finished ? <SessionSummary summary={finished} /> : null}
      <div className="bank-start-row">
        <label>
          이번 회차{" "}
          <select value={size} onChange={(event) => setSize(Number(event.target.value))}>
            {info.sizes.map((n) => (
              <option key={n} value={n}>{n}문항</option>
            ))}
          </select>
        </label>
        <button className="quiz-submit" disabled={busy} onClick={() => void start()}>
          {busy ? "여는 중…" : finished ? "한 회차 더" : "시작"}
        </button>
      </div>
      {!finished && info.previousSessions.length ? (
        <p className="bank-note">
          지난 회차 {info.previousSessions.length}번 ·
          마지막 Core 숙련 {Math.round((info.previousSessions.at(-1)?.core_after ?? 0) * 100)}%
        </p>
      ) : null}
      {error ? <p className="notice is-error">{error}</p> : null}
      {info.conceptMap?.length ? <ConceptMap concepts={info.conceptMap} /> : null}
    </div>
  );
}

const FORMAT_LABEL: Record<string, string> = {
  basic: "서술", cloze: "빈칸", list: "나열", ox: "O/X", mcq: "객관식", multi_select: "복수 선택",
  matching: "짝짓기", sequence: "순서",
};

const RATINGS: { rating: BankRating; grade: string }[] = [
  { rating: "Again", grade: "again" },
  { rating: "Hard", grade: "hard" },
  { rating: "Good", grade: "good" },
  { rating: "Easy", grade: "easy" },
];

function BankSolve({ base, onFinished }: { base: string; onFinished: (summary: BankSession | null) => void }) {
  const [current, setCurrent] = useState<BankNext | null>(null);
  const [answer, setAnswer] = useState<BankAnswer | null>(null);
  const [picked, setPicked] = useState<Set<string>>(new Set());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [reporting, setReporting] = useState(false);

  const next = useCallback(async () => {
    setBusy(true);
    setError("");
    try {
      const got = await api<BankNext>(`${base}/next`, { method: "POST" });
      if (!got.question) {
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
      setBusy(false);
    }
  }, [base, onFinished]);
  useEffect(() => void next(), [next]);

  const reveal = useCallback(async () => {
    if (!current?.reviewToken || answer) return;
    setBusy(true);
    try {
      setAnswer(await api<BankAnswer>(`${base}/reveal`, {
        method: "POST", body: JSON.stringify({ reviewToken: current.reviewToken }),
      }));
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setBusy(false);
    }
  }, [base, current, answer]);

  const rate = useCallback(async (rating: BankRating) => {
    if (!current?.reviewToken || !answer || busy) return;
    setBusy(true);
    try {
      await api(`${base}/rate`, { method: "POST", body: JSON.stringify({ reviewToken: current.reviewToken, rating }) });
    } catch (cause) {
      setError((cause as Error).message);
      setBusy(false);
      return;
    }
    setBusy(false);
    await next();
  }, [base, current, answer, busy, next]);

  async function end() {
    if (!current?.session) return;
    try {
      const summary = await api<BankSession>(`${base}/session/end`, {
        method: "POST", body: JSON.stringify({ sessionId: current.session.session_id }),
      });
      onFinished(summary);
    } catch (cause) {
      setError((cause as Error).message);
    }
  }

  // 키보드 — 기존 웹 풀이와 같다. Space·Enter 로 펴고, 1–4 로 찍는다.
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.target instanceof HTMLElement && ["INPUT", "TEXTAREA", "SELECT"].includes(event.target.tagName)) return;
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
  }, [answer, reveal, rate]);

  if (!current?.question) return error ? <p className="notice is-error">{error}</p> : <p className="notice">불러오는 중…</p>;
  const q = current.question;
  const session = current.session;

  return (
    <>
      <div className="quiz">
        <p className="quiz-progress bank-progress">
          <span>
            {session ? `${session.reviewed + 1} / ${session.size}` : ""}
            {current.examDate ? ` · ${daysLabel(current.examDate)}` : ""}
          </span>
          <span className="bank-tags">
            {q.tier} · {DIRECTION_LABEL[q.retrieval_direction] ?? q.retrieval_direction} ·{" "}
            {FORMAT_LABEL[q.format] ?? q.format}
          </span>
          <button className="is-quiet" onClick={() => void end()}>회차 마치기</button>
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
            <AnswerBody question={q} answer={answer} />
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
            <button key={rating} className={`quiz-grade is-${grade}`} disabled={busy} onClick={() => void rate(rating)}>
              <span className="quiz-grade-name">
                {rating}
                <kbd>{index + 1}</kbd>
              </span>
            </button>
          ))
        ) : (
          <button className="quiz-submit" disabled={busy} onClick={() => void reveal()}>
            {busy ? "펴는 중…" : <>답 보기 <kbd>space</kbd></>}
          </button>
        )}
      </div>
    </>
  );
}

/** 발문. cloze 빈칸은 답을 보면 채운다. */
function QuestionBody({ question: q, answer, picked, onPick }: {
  question: BankQuestion;
  answer: BankAnswer | null;
  picked: Set<string>;
  onPick: (id: string) => void;
}) {
  const parts = q.format === "cloze" ? q.question.split(/(\{\{c\d+\}\})/g) : [q.question];
  let blank = 0;
  return (
    <>
      <p className="quiz-stem">
        {parts.map((part, index) => {
          if (!/^\{\{c\d+\}\}$/.test(part)) return <Stem key={index} text={part} />;
          const unit = answer?.answerUnits[blank];
          blank += 1;
          return (
            <span key={index} className={`bank-blank${unit ? " is-filled" : ""}`}>
              {unit ?? `[ ${blank} ]`}
            </span>
          );
        })}
      </p>
      {q.format === "ox" && !answer ? <p className="bank-note">O 인가 X 인가, 그리고 왜인가</p> : null}
      {q.options.length ? (
        <ul className="bank-options">
          {q.options.map((option) => {
            const correct = answer?.correctOptionIds.includes(option.id);
            const cls = `${picked.has(option.id) ? " is-picked" : ""}${correct ? " is-correct" : ""}`;
            return (
              <li key={option.id}>
                <button className={`bank-option${cls}`} disabled={Boolean(answer)} onClick={() => onPick(option.id)}>
                  <b>{option.id}</b> {option.text}
                </button>
              </li>
            );
          })}
        </ul>
      ) : null}
      {q.format === "matching" ? (
        <div className="bank-match">
          <ul>{q.matching_left.map((item) => <li key={item}>{item}</li>)}</ul>
          <ul>{q.matching_right.map((item) => <li key={item}>{item}</li>)}</ul>
        </div>
      ) : null}
      {q.format === "sequence" ? (
        <ul className="bank-items">{q.sequence_items.map((item) => <li key={item}>{item}</li>)}</ul>
      ) : null}
    </>
  );
}

function AnswerBody({ question: q, answer }: { question: BankQuestion; answer: BankAnswer }) {
  const review = answer.medicalReview;
  return (
    <>
      <p className="quiz-answer">
        <Stem text={answer.answer} />
      </p>
      {/* 짝짓기·순서·빈칸은 채점 단위가 아래 짝·순서·빈칸과 같은 말이라 또 적지 않는다. */}
      {answer.answerUnits.length > 1 && !["cloze", "matching", "sequence"].includes(q.format) ? (
        <ul className="bank-units">{answer.answerUnits.map((unit) => <li key={unit}>{unit}</li>)}</ul>
      ) : null}
      {answer.answerPairs.length ? (
        <ul className="bank-units">
          {answer.answerPairs.map((pair) => (
            <li key={`${pair.left}-${pair.right}`}>{pair.left} → {pair.right}</li>
          ))}
        </ul>
      ) : null}
      {answer.correctOrder.length ? (
        <p className="bank-order">
          {answer.correctOrder.map((item, index) => (
            <Fragment key={item}>{index ? " → " : ""}{item}</Fragment>
          ))}
        </p>
      ) : null}
      {answer.conflict ? (
        <p className="bank-conflict">
          <b>자료 충돌</b> {answer.conflict}
        </p>
      ) : null}
      {answer.external ? (
        <p className="bank-note">이 문항에는 강의자료·족보에 없는 내용(외부 의학지식)이 들어 있습니다.</p>
      ) : null}
      {review && review.verdict !== "ok" ? (
        <p className={`bank-review is-${review.verdict}`}>
          <b>외부지식 검토 · {review.verdict === "wrong" ? "틀림" : "의심"}</b> {review.note}
          {review.suggested_answer ? <><br />맞는 답: {review.suggested_answer}</> : null}
        </p>
      ) : null}
      {answer.slides.map((slide) => (
        <img key={slide.page} className="quiz-slide" src={slide.url} alt={`필기 ${slide.page}쪽`} loading="lazy" />
      ))}
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

function SessionSummary({ summary }: { summary: BankSession }) {
  const pct = (n: number) => `${Math.round(n * 100)}%`;
  return (
    <section className="bank-summary">
      <h3>이번 회차 · {summary.reviewed}문항</h3>
      <p>
        Again {summary.ratings.Again} · Hard {summary.ratings.Hard} · Good {summary.ratings.Good} · Easy{" "}
        {summary.ratings.Easy} — Core 숙련 {pct(summary.core_before)} → {pct(summary.core_after)}
      </p>
      {summary.weaknesses.length ? (
        <>
          <h4>남은 약점</h4>
          <ul>
            {summary.weaknesses.map((d) => (
              <li key={`${d.concept_id}-${d.direction}`}>
                {d.title} · {DIRECTION_LABEL[d.direction] ?? d.direction} — {pct(d.after)} / 목표 {pct(d.target)}
              </li>
            ))}
          </ul>
        </>
      ) : null}
    </section>
  );
}

import { useState } from "react";
import { api } from "../api";
import { lectureHref } from "../links";
import type { BankRead, BankSession } from "../types/bank";
import { ConceptMap } from "./ConceptMap";
import { daysLabel, DIRECTION_LABEL } from "./labels";

export function BankStart({ base, info, finished, lecture, onStarted }: {
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
      <h2>Main-Quiz</h2>
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

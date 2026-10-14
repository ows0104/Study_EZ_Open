import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { lectureHref } from "../links";
import type { BankRead, BankSession } from "../types/bank";
import { ConceptMap } from "./ConceptMap";
import { DailyGoal } from "./DailyGoal";
import { BankCoverage } from "./BankCoverage";
import { LectureMastery } from "../lecture/LectureMastery";
import { daysLabel, DIRECTION_LABEL } from "./labels";

export function BankStart({ base, info, finished, lecture, onStarted, onUndo, undoBusy }: {
  base: string;
  info: BankRead;
  finished: BankSession | null;
  lecture: { subject: string; runId: string };
  onStarted: () => void;
  onUndo?: () => void;
  undoBusy?: boolean;
}) {
  const [size, setSize] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function start() {
    setBusy(true);
    setError("");
    try {
      await api(`${base}/session/start`, { method: "POST", body: JSON.stringify({
        size, continueAfterGoal: info.lectureGoal?.met === true,
      }) });
      onStarted();
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className={`quiz bank-start${info.lectureGoal?.met ? " bank-complete" : ""}`}>
      <p className="quiz-progress bank-progress">
        <Link to={lectureHref(lecture)}>강의로</Link>
        <span>{daysLabel(info.examDate)}</span>
      </p>
      <header className="bank-start-heading">
        <h2>Main-Quiz</h2>
        {!info.lectureGoal?.met ? <button className="quiz-submit" disabled={busy} onClick={() => void start()}>
          {busy ? "여는 중…" : finished ? "계속 공부하기" : "학습 시작"}
        </button> : null}
      </header>
      <p className="bank-note">이 강의의 새 카드를 먼저 보고 예정된 복습을 이어갑니다. <Link to="/study">여러 강의 모아 풀기</Link></p>
      <DailyGoal plan={info.lectureGoal} showMain={info.lectureGoal?.met}
        onContinue={() => void start()} busy={busy} />
      <BankCoverage value={info.summary.coverage} />
      {info.summary.publicationWarning ? <p className="bank-note">{info.summary.publicationWarning}</p> : null}
      {error ? <p className="notice is-error">{error}</p> : null}
      {info.conceptMap?.length ? <ConceptMap concepts={info.conceptMap} /> : <LectureMastery value={info.mastery} />}
      <div className="bank-start-row bank-secondary-actions">
        {onUndo ? <button className="quiz-undo" disabled={busy || undoBusy} onClick={onUndo} aria-keyshortcuts="Z Control+Z">마지막 평가 되돌리기 <kbd>Z</kbd></button> : null}
        <details className="bank-options">
          <summary>학습 설정</summary>
          <label>
            문항 수 제한{" "}
            <select value={size ?? ""} onChange={(event) => setSize(event.target.value ? Number(event.target.value) : null)}>
              <option value="">제한 없음</option>
              {info.sizes.map((n) => (
                <option key={n} value={n}>{n}문항</option>
              ))}
            </select>
          </label>
        </details>
      </div>
      {finished ? <details className="bank-session-details"><summary>이번 학습 기록 보기</summary><SessionSummary summary={finished} /></details> : null}
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

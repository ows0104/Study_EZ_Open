import { useEffect, useState } from "react";
import { api } from "../api";
import type { GradeResult, QuizPayload } from "../types";
import { Stem } from "./Stem";

/**
 * Pre-Quiz 웹 풀이.
 *
 * 정답은 서버에만 있다. 한 문항을 내면 그때 채점 결과가 오고, 그 결과가
 * `quiz_attempt`에 남는다. 남지 않으면 apkg로 충분했을 것이므로 이 화면의
 * 존재 이유가 바로 그 기록이다.
 */
export function PreQuiz({ subject, runId, onFinished }: { subject: string; runId: string; onFinished: () => void }) {
  const base = `/api/lectures/${encodeURIComponent(subject)}/${encodeURIComponent(runId)}/prequiz`;
  const [payload, setPayload] = useState<QuizPayload | null>(null);
  const [index, setIndex] = useState(0);
  const [answered, setAnswered] = useState("");
  const [result, setResult] = useState<GradeResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    api<QuizPayload>(base)
      .then((next) => {
        setPayload(next);
        // 이어서 푼다. 이미 낸 문항 다음부터 시작한다.
        const firstUnanswered = next.items.findIndex((item) => !item.attempt);
        setIndex(firstUnanswered < 0 ? next.items.length : firstUnanswered);
      })
      .catch((cause: Error) => setError(cause.message));
  }, [base]);

  if (error) return <p className="notice is-error">{error}</p>;
  if (!payload) return <p className="notice">문항을 불러오는 중…</p>;

  const total = payload.items.length;
  const item = payload.items[index];

  if (!item) {
    const correct = payload.items.filter((entry) => entry.attempt?.correct).length;
    return (
      <div className="quiz-done">
        <p>
          <strong>
            {total}문항 중 {correct}개 정답
          </strong>
        </p>
        <div className="row">
          <button onClick={onFinished}>결과 보기</button>
          <button
            className="is-quiet"
            onClick={async () => {
              await api(`${base}/attempts`, { method: "DELETE" });
              const next = await api<QuizPayload>(base);
              setPayload(next);
              setIndex(0);
              setResult(null);
              setAnswered("");
            }}
          >
            처음부터 다시
          </button>
        </div>
      </div>
    );
  }

  async function submit() {
    if (!item || busy) return;
    setBusy(true);
    setError("");
    try {
      const graded = await api<GradeResult>(`${base}/grade`, {
        method: "POST",
        body: JSON.stringify({ itemId: item.itemId, answered }),
      });
      setResult(graded);
      setPayload((current) =>
        current
          ? {
              ...current,
              items: current.items.map((entry) =>
                entry.itemId === item.itemId ? { ...entry, attempt: { answered, correct: graded.correct } } : entry,
              ),
            }
          : current,
      );
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setBusy(false);
    }
  }

  function next() {
    setResult(null);
    setAnswered("");
    setIndex((current) => current + 1);
  }

  return (
    <div className="quiz">
      <p className="quiz-progress">
        {index + 1} / {total}
      </p>
      <p className="quiz-stem">
        <Stem text={item.stem} />
      </p>

      {item.qtype === "mcq" ? (
        <ol className="quiz-choices">
          {(item.choices ?? []).map((choice, choiceIndex) => {
            const value = String(choiceIndex + 1);
            return (
              <li key={value}>
                <label className={result && result.answer === value ? "is-answer" : ""}>
                  <input
                    type="radio"
                    name={item.itemId}
                    value={value}
                    checked={answered === value}
                    disabled={Boolean(result)}
                    onChange={() => setAnswered(value)}
                  />
                  <span>{choice}</span>
                </label>
              </li>
            );
          })}
        </ol>
      ) : item.qtype === "ox" ? (
        <div className="quiz-ox">
          {["O", "X"].map((value) => (
            <button
              key={value}
              className={answered === value ? "is-active" : ""}
              disabled={Boolean(result)}
              onClick={() => setAnswered(value)}
            >
              {value}
            </button>
          ))}
        </div>
      ) : (
        <input
          className="quiz-short"
          value={answered}
          disabled={Boolean(result)}
          placeholder="답을 입력하세요"
          onChange={(event) => setAnswered(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") void submit();
          }}
        />
      )}

      {result ? (
        <div className={`quiz-result ${result.correct ? "is-correct" : "is-wrong"}`}>
          <p className="quiz-verdict">{result.correct ? "정답" : `오답 — 정답은 ${result.answer}`}</p>
          {result.explanation ? <p className="quiz-explanation">{result.explanation}</p> : null}
          {result.sourceAnchor ? <p className="quiz-anchor">근거: {result.sourceAnchor}</p> : null}
          {/* 틀렸을 때만 슬라이드를 띄운다. 맞은 문항에 그림을 붙이면 넘기는 데
              시간이 걸리고, 이 퀴즈는 강의 직전에 푸는 것이다. */}
          {!result.correct && result.slideUrl ? (
            <img className="quiz-slide" src={result.slideUrl} alt={`슬라이드 ${result.slideNo}`} loading="lazy" />
          ) : null}
          <button onClick={next}>{index + 1 >= total ? "결과 보기" : "다음"}</button>
        </div>
      ) : (
        <button className="quiz-submit" disabled={!answered || busy} onClick={submit}>
          {busy ? "채점 중…" : "제출"}
        </button>
      )}

      {error ? <p className="notice is-error">{error}</p> : null}
    </div>
  );
}

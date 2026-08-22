import { useEffect, useState } from "react";
import { api } from "../api";
import type { QuizItem, QuizPayload, RevealResult } from "../types";
import { Stem } from "./Stem";

/**
 * Pre-Quiz 웹 풀이 — 자기채점 플래시카드.
 *
 *   질문을 본다 → 「답 보기」 → 답과 해설이 펴진다 → 「알았다 / 몰랐다」를 찍는다
 *
 * 채점을 서버가 하지 않는 이유는 카드가 자유회상이기 때문이다. 답이 여러 줄 산문일
 * 때가 많아 문자열로 재면 전원이 틀린다. Anki가 하는 방식이 이것이고, 이 덱이
 * 실제로 쓰이는 방식도 이것이다.
 *
 * 그래도 답은 문항과 함께 안 받는다. 편 사람만 `reveal`로 받아 가고, 그래야
 * `quiz_attempt`에 남는 「알았다」가 무언가를 뜻한다.
 */
export function PreQuiz({ subject, runId, onFinished }: { subject: string; runId: string; onFinished: () => void }) {
  const base = `/api/lectures/${encodeURIComponent(subject)}/${encodeURIComponent(runId)}/prequiz`;
  const [payload, setPayload] = useState<QuizPayload | null>(null);
  const [index, setIndex] = useState(0);
  const [revealed, setRevealed] = useState<RevealResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    api<QuizPayload>(base)
      .then((next) => {
        setPayload(next);
        // 이어서 푼다. 이미 찍은 카드 다음부터 시작한다.
        const firstUnanswered = next.items.findIndex((item) => !item.attempt);
        setIndex(firstUnanswered < 0 ? next.items.length : firstUnanswered);
      })
      .catch((cause: Error) => setError(cause.message));
  }, [base]);

  if (error) return <p className="notice is-error">{error}</p>;
  if (!payload) return <p className="notice">카드를 불러오는 중…</p>;

  const total = payload.items.length;
  const item = payload.items[index];

  if (!item) {
    const known = payload.items.filter((entry) => entry.attempt?.correct).length;
    return (
      <div className="quiz-done">
        <p>
          <strong>
            {total}장 중 {known}장을 알고 있었습니다
          </strong>
        </p>
        <div className="row">
          <button onClick={onFinished}>결과 보기</button>
          <button
            className="is-quiet"
            onClick={async () => {
              await api(`${base}/attempts`, { method: "DELETE" });
              setPayload(await api<QuizPayload>(base));
              setIndex(0);
              setRevealed(null);
            }}
          >
            처음부터 다시
          </button>
        </div>
      </div>
    );
  }

  async function reveal() {
    if (!item || busy) return;
    setBusy(true);
    setError("");
    try {
      setRevealed(await api<RevealResult>(`${base}/reveal`, {
        method: "POST",
        body: JSON.stringify({ itemId: item.itemId }),
      }));
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function mark(correct: boolean) {
    if (!item || busy) return;
    setBusy(true);
    setError("");
    try {
      await api(`${base}/grade`, {
        method: "POST",
        body: JSON.stringify({ itemId: item.itemId, correct }),
      });
      setPayload((current) =>
        current
          ? {
              ...current,
              items: current.items.map((entry) =>
                entry.itemId === item.itemId ? { ...entry, attempt: { correct } } : entry,
              ),
            }
          : current,
      );
      setRevealed(null);
      setIndex((current) => current + 1);
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="quiz">
      <p className="quiz-progress">
        {index + 1} / {total}
        <FocusBadge item={item} />
      </p>
      <p className="quiz-stem">
        <Stem text={item.stem} />
      </p>

      {revealed ? (
        <div className="quiz-result">
          <p className="quiz-answer">
            <Stem text={revealed.answer} />
          </p>
          {revealed.explanation ? <p className="quiz-explanation">{revealed.explanation}</p> : null}
          {revealed.slideUrl ? (
            <img
              className="quiz-slide"
              src={revealed.slideUrl}
              alt={`슬라이드 ${revealed.slideNo}`}
              loading="lazy"
            />
          ) : null}
          {/* 서버가 판정하지 않는다. 이 두 버튼이 남기는 것이 전부다. */}
          <div className="row">
            <button disabled={busy} onClick={() => mark(true)}>
              알고 있었다
            </button>
            <button className="is-quiet" disabled={busy} onClick={() => mark(false)}>
              몰랐다
            </button>
          </div>
        </div>
      ) : (
        <button className="quiz-submit" disabled={busy} onClick={reveal}>
          {busy ? "펴는 중…" : "답 보기"}
        </button>
      )}

      {error ? <p className="notice is-error">{error}</p> : null}
    </div>
  );
}

/**
 * 이 카드가 왜 「꼭 반드시」인가. 등급이 아니라 이유다 — 예습 덱은 전부 꼭
 * 반드시이고, 등급을 두면 그 축이 흐려진다.
 */
const FOCUS_LABEL: Record<string, string> = {
  spine: "강의의 뼈대",
  vocabulary: "용어·약어",
  mechanism: "핵심 기전",
  clinical: "임상적 의미",
  repeated: "여러 해 반복 출제",
};

function FocusBadge({ item }: { item: QuizItem }) {
  const label = FOCUS_LABEL[item.focus];
  if (!label && !item.examHit) return null;
  return (
    <span className="quiz-focus">
      {label}
      {item.examHit ? <span className="badge">기출</span> : null}
    </span>
  );
}

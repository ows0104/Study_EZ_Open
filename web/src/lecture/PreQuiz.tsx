import { useEffect, useState } from "react";
import { api } from "../api";
import type { QuizItem, QuizPayload, RevealResult } from "../types";
import { Stem } from "./Stem";

/**
 * Pre-Quiz 웹 풀이 — 자기채점 플래시카드.
 *
 *   질문을 본다 → 「답 보기」 → 답과 해설이 펴진다 → 「Again / Pass」를 찍는다
 *
 * 채점을 서버가 하지 않는 이유는 카드가 자유회상이기 때문이다. 답이 여러 줄 산문일
 * 때가 많아 문자열로 재면 전원이 틀린다. Anki가 하는 방식이 이것이고, 이 덱이
 * 실제로 쓰이는 방식도 이것이다.
 *
 * 그래도 답은 문항과 함께 안 받는다. 편 사람만 `reveal`로 받아 가고, 그래야
 * `quiz_attempt`에 남는 「알았다」가 무언가를 뜻한다.
 *
 * **카드만 그린다.** 강의가 무엇인지, 다 풀고 나서 무엇을 할지는 이 컴포넌트를
 * 세운 화면(`PreQuizPage`)이 말한다.
 */
export function PreQuiz({
  subject,
  runId,
  onDone,
}: {
  subject: string;
  runId: string;
  /** 다 찍었는지를 화면 밖에 알린다. 놓친 것 목록이 그 신호로 붙는다. */
  onDone: (done: boolean) => void;
}) {
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

  // 다 찍었는가. 화면이 이 신호를 받아 놓친 것을 부른다 — 그 목록은 서버가
  // 고르는 것이라 마지막 카드를 찍기 전에는 채워지지 않는다.
  const finished = payload !== null && index >= payload.items.length;
  useEffect(() => {
    onDone(finished);
  }, [finished, onDone]);

  const total = payload?.items.length ?? 0;
  const item = payload?.items[index];

  /**
   * 손이 자판에서 안 떠나게 한다. 안키에서 하던 그대로다 —
   * `space`로 펴고, 편 뒤에는 `1`이 `Again`, `2`가 `Pass`다. 안키에서 쓰던
   * `space`(= Good)도 `Pass`로 받는다 — 버튼에 적는 것은 `1`·`2`뿐이다.
   *
   * `preventDefault`를 빼면 안 된다. 눌러서 편 버튼에 초점이 남아 있어서,
   * 막지 않으면 같은 `space`가 우리 처리와 버튼 누름 둘 다를 일으킨다.
   */
  useEffect(() => {
    if (!item) return;
    function onKey(event: KeyboardEvent) {
      if (event.repeat || event.metaKey || event.ctrlKey || event.altKey) return;
      const key = event.key;
      if (!revealed) {
        if (key === " " || key === "Enter") {
          event.preventDefault();
          void reveal();
        }
        return;
      }
      if (key === " " || key === "Enter" || key === "2") {
        event.preventDefault();
        void mark(true);
      } else if (key === "1") {
        event.preventDefault();
        void mark(false);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [item, revealed, busy]); // eslint-disable-line react-hooks/exhaustive-deps

  if (error) return <p className="notice is-error">{error}</p>;
  if (!payload) return <p className="notice">카드를 불러오는 중…</p>;

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
    <>
      {/* 안키의 복습 화면을 그대로 옮긴다 — 앞면이 위에 남고, 가로줄 아래로 답이
          붙고, 찍는 버튼은 화면 맨 아래에 못 박혀 있다. 카드 상자를 그리지 않는
          이유도 같다: 창 전체가 카드다. */}
      <div className="quiz">
        <p className="quiz-progress">
          {index + 1} / {total}
          <FocusBadge item={item} />
        </p>

        <p className="quiz-stem">
          <Stem text={item.stem} />
        </p>

        {revealed ? (
          <>
            {/* 안키의 `hr id=answer` 자리다. */}
            <hr className="quiz-line" />
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
          </>
        ) : null}

        {error ? <p className="notice is-error">{error}</p> : null}
      </div>

      {/* 찍는 자리. **화면 아래에 못 박는다** — 그림이 길어도 버튼을 찾아 내려갈
          일이 없고, 손은 늘 같은 자리를 누른다. 순서도 안키다: 왼쪽이 못 한 쪽,
          오른쪽이 아는 쪽. 서버가 판정하지 않으므로 이 둘이 남기는 것이 전부다. */}
      <div className="quiz-bar">
        {revealed ? (
          <>
            <button className="is-quiet" disabled={busy} onClick={() => mark(false)}>
              Again <kbd>1</kbd>
            </button>
            <button disabled={busy} onClick={() => mark(true)}>
              Pass <kbd>2</kbd>
            </button>
          </>
        ) : (
          <button className="quiz-submit" disabled={busy} onClick={reveal}>
            {busy ? (
              "펴는 중…"
            ) : (
              <>
                답 보기 <kbd>space</kbd>
              </>
            )}
          </button>
        )}
      </div>
    </>
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

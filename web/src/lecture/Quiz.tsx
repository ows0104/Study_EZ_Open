import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { lectureHref, quizPath } from "../links";
import { useMe } from "../useMe";
import { cardsHash } from "./LectureCards";
import { quizGrades, type GradeResult, type QuizGrade, type QuizItem, type QuizKind, type QuizPayload, type QuizSchedule, type RevealResult, type UndoResult } from "../types/quiz";
import { counts, dayLabel, daysFromNow, intervalLabel, pick, stateOf } from "./queue";
import { Stem } from "./Stem";

/**
 * 웹 풀이 — 자기채점 플래시카드. 기존 Main 카드의 반복 학습. 예습은 PreQuiz.tsx를 쓴다.
 *
 *   질문을 본다 → 「답 보기」 → 답과 해설이 펴진다 → 넷 중 하나를 찍는다
 *
 * 채점을 서버가 하지 않는 이유는 카드가 자유회상이기 때문이다. 답이 여러 줄 산문일
 * 때가 많아 문자열로 재면 전원이 틀린다. Anki가 하는 방식이 이것이고, 이 덱이
 * 실제로 쓰이는 방식도 이것이다.
 *
 * 그래도 답은 문항과 함께 안 받는다. 편 사람만 `reveal`로 받아 가고, 그래야
 * 시도 기록에 남는 「알았다」가 무언가를 뜻한다.
 *
 * ## 반복이 여기서 돈다 (2026-09-18)
 *
 * **관리자 지시** — 「웹 퀴즈를 안키처럼 해줘. 망각곡선에 기반해서. 그리고
 * 이전으로 돌아가는 기능도 만들어줘.」
 *
 * 그 전까지 이 화면은 카드를 처음부터 끝까지 한 줄로 훑고(`index + 1 / total`)
 * 반복은 apkg를 받아 간 사람의 안키가 들었다. 지금은 큐가 있다.
 *
 *   Again·Hard·Good·Easy  →  서버(`app/srs.py`)가 다음 때를 정한다
 *   때가 된 카드만 낸다      →  때를 고르는 것은 `queue.ts`
 *   되돌리기                →  찍기 전으로. 서버가 적어 둔 값으로 돌아간다
 *
 * **간격을 이 화면이 계산하지 않는다.** 버튼에 적는 「1분·10분·4일」까지 서버가
 * `reveal`에 실어 보낸다(`next`). 두 곳에서 계산하면 두 곳이 갈라진다.
 *
 * **카드만 그린다.** 강의가 무엇인지, 다 풀고 나서 무엇을 할지는 이 컴포넌트를
 * 세운 화면(`QuizPage`)이 말한다.
 */
export function Quiz({
  kind,
  subject,
  runId,
  onDone,
}: {
  kind: QuizKind;
  subject: string;
  runId: string;
  /** 지금 낼 카드가 없는지를 화면 밖에 알린다. 놓친 것 목록이 그 신호로 붙는다. */
  onDone: (done: boolean) => void;
}) {
  const base = `/api/lectures/${encodeURIComponent(subject)}/${encodeURIComponent(runId)}/${quizPath(kind)}`;
  const [payload, setPayload] = useState<QuizPayload | null>(null);
  const [revealed, setRevealed] = useState<RevealResult | null>(null);
  const [undoable, setUndoable] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const isAdmin = Boolean(useMe()?.isAdmin);

  /**
   * 되돌리기가 세운 카드. 순서를 무시하고 이것을 먼저 낸다.
   *
   * 되돌린 카드가 화면에 안 서면 무엇이 되돌아갔는지 볼 수가 없다. 찍으면
   * 바로 비운다 — 안 비우면 그 카드에 갇힌다.
   */
  const [forcedId, setForcedId] = useState("");

  /**
   * 몰아보기. 때를 무시하고 전부 한 바퀴 돈다.
   *
   * **없으면 시험 전날에 할 수 있는 일이 없다.** 일정대로만 내면 「오늘 몫
   * 끝」이 「더 볼 수 없음」이 되는데, 이 제품이 쓰이는 자리가 시험 기간이다.
   * 안키의 「미리 공부하기」와 같은 자리고, 찍은 것은 똑같이 일정에 들어간다.
   */
  const [cram, setCram] = useState(false);
  const [crammed, setCrammed] = useState<Set<string>>(() => new Set());

  /**
   * 서버 시각과 이 기계 시각의 차. **익히는 단계가 분 단위라 필요하다.**
   *
   * 기계 시계가 5분 빠르면 「1분 뒤」가 이미 지난 일이 되어 Again을 누른
   * 카드가 그 자리에서 다시 나온다. 5분 느리면 그 카드가 세션 안에 안 나온다.
   */
  const skewRef = useRef(0);
  const serverNow = () => Date.now() + skewRef.current;

  /** 이번에 찍은 장수. 다 끝낸 화면에 적는다 — 서버가 세는 값이 아니다. */
  const [done, setDone] = useState(0);

  useEffect(() => {
    api<QuizPayload>(base)
      .then((next) => {
        skewRef.current = Date.parse(next.now) - Date.now();
        setPayload(next);
        setUndoable(next.undoable);
      })
      .catch((cause: Error) => setError(cause.message));
  }, [base]);

  const now = serverNow();
  const tally = payload ? counts(payload.items, now) : null;
  const next = payload
    ? pick(payload.items, now, { forcedId, cram, seen: crammed })
    : null;
  const item = next?.kind === "card" ? next.item : undefined;

  // 지금 낼 카드가 없는가. 화면이 이 신호를 받아 놓친 것을 부른다 — 그 목록은
  // 서버가 고르는 것이라 마지막 카드를 찍기 전에는 채워지지 않는다.
  const finished = next?.kind === "empty";
  useEffect(() => {
    onDone(finished);
  }, [finished, onDone]);

  /**
   * 손이 자판에서 안 떠나게 한다. 안키에서 하던 그대로다 —
   * `space`로 펴고, 편 뒤에는 `1`~`4`가 네 버튼이다. 안키에서 쓰던
   * `space`(= Good)도 그대로 받는다.
   *
   * 되돌리기는 안키와 같이 `Ctrl+Z`이고, 자판 하나만 누르는 `z`도 받는다 —
   * 푸는 동안 두 손이 자판에 있지 않을 때가 많다.
   *
   * `preventDefault`를 빼면 안 된다. 눌러서 편 버튼에 초점이 남아 있어서,
   * 막지 않으면 같은 `space`가 우리 처리와 버튼 누름 둘 다를 일으킨다.
   */
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.repeat || event.metaKey || event.altKey) return;
      const key = event.key.toLowerCase();
      if (key === "z") {
        event.preventDefault();
        void undo();
        return;
      }
      if (event.ctrlKey) return;
      if (!item) return;
      if (!revealed) {
        if (key === " " || key === "enter") {
          event.preventDefault();
          void reveal();
        }
        return;
      }
      const index = ["1", "2", "3", "4"].indexOf(key);
      if (index >= 0) {
        event.preventDefault();
        void mark(quizGrades[index]);
      } else if (key === " " || key === "enter") {
        event.preventDefault();
        void mark("good");
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [item, revealed, busy, undoable]); // eslint-disable-line react-hooks/exhaustive-deps

  if (error && !payload) return <p className="notice is-error">{error}</p>;
  if (!payload || !next || !tally) return <p className="notice">카드를 불러오는 중…</p>;

  /** 표의 한 줄을 서버가 돌려준 것으로 맞춘다. 다시 받아 오지 않는다. */
  function patch(itemId: string, attempt: QuizSchedule | null) {
    setPayload((current) =>
      current
        ? {
            ...current,
            items: current.items.map((entry) =>
              entry.itemId === itemId ? { ...entry, attempt } : entry,
            ),
          }
        : current,
    );
  }

  async function reveal() {
    if (!item || busy) return;
    setBusy(true);
    setError("");
    try {
      setRevealed(
        await api<RevealResult>(`${base}/reveal`, {
          method: "POST",
          body: JSON.stringify({ itemId: item.itemId }),
        }),
      );
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function mark(grade: QuizGrade) {
    if (!item || busy) return;
    setBusy(true);
    setError("");
    try {
      const result = await api<GradeResult>(`${base}/grade`, {
        method: "POST",
        body: JSON.stringify({ itemId: item.itemId, grade }),
      });
      skewRef.current = Date.parse(result.now) - Date.now();
      patch(result.itemId, result.attempt);
      if (cram) setCrammed((seen) => new Set(seen).add(result.itemId));
      setForcedId("");
      setRevealed(null);
      setUndoable(true);
      setDone((count) => count + 1);
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setBusy(false);
    }
  }

  /**
   * 마지막으로 찍은 것을 되돌린다. **한 번에 한 장이고, 몇 번이든 된다.**
   *
   * 되돌릴 값은 서버가 찍을 때 적어 둔 것이다 — 간격을 거꾸로 계산해서는
   * 안 돌아온다(`app/srs.py`는 한쪽으로만 간다). 되돌린 카드는 답이 펴진
   * 채로 다시 서므로, 눌러 보고 다시 찍을 수 있다.
   */
  async function undo() {
    if (busy || !undoable) return;
    setBusy(true);
    setError("");
    try {
      const result = await api<UndoResult>(`${base}/undo`, { method: "POST" });
      skewRef.current = Date.parse(result.now) - Date.now();
      patch(result.itemId, result.attempt);
      // 몰아보기 중이었으면 「이미 봤다」에서도 빼야 그 카드가 다시 선다.
      setCrammed((seen) => {
        if (!seen.has(result.itemId)) return seen;
        const rest = new Set(seen);
        rest.delete(result.itemId);
        return rest;
      });
      setForcedId(result.itemId);
      setRevealed(result);
      setUndoable(result.undoable);
      setDone((count) => Math.max(0, count - 1));
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function reset() {
    setBusy(true);
    try {
      await api(`${base}/attempts`, { method: "DELETE" });
      const fresh = await api<QuizPayload>(base);
      skewRef.current = Date.parse(fresh.now) - Date.now();
      setPayload(fresh);
      setUndoable(fresh.undoable);
      setRevealed(null);
      setForcedId("");
      setCram(false);
      setCrammed(new Set());
      setDone(0);
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setBusy(false);
    }
  }

  if (!item) {
    return (
      <Empty
        reason={next.kind === "empty" ? next.reason : "done-today"}
        nextDueAt={next.kind === "empty" ? next.nextDueAt : null}
        now={now}
        tally={tally}
        done={done}
        busy={busy}
        error={error}
        onCram={() => {
          setCram(true);
          setCrammed(new Set());
        }}
        onReset={reset}
      />
    );
  }

  return (
    <>
      {/* 안키의 복습 화면을 그대로 옮긴다 — 앞면이 위에 남고, 가로줄 아래로 답이
          붙고, 찍는 버튼은 화면 맨 아래에 못 박혀 있다. 카드 상자를 그리지 않는
          이유도 같다: 창 전체가 카드다. */}
      <div className="quiz">
        <p className="quiz-progress">
          {/* **남은 장수를 갈래별로 적는다.** 안키의 그 줄이다. 한 숫자로 합치면
              「새로 배울 것이 열둘」과 「잊어서 돌아온 것이 열둘」이 같아 보인다. */}
          <QueueCounts tally={tally} cram={cram} crammed={crammed.size} />
          <FocusBadge item={item} />
          <UndoButton busy={busy} undoable={undoable} onUndo={undo} />
          {/* 관리자만. 풀다가 이상한 카드를 만나면 그 자리에서 고치기로 간다
              (2026-09-23 관리자 지시). 새 탭이라 풀던 자리는 그대로 남는다. */}
          {isAdmin ? (
            <a
              className="quiz-fix"
              href={lectureHref({ subject, runId }) + cardsHash(kind, item.itemId)}
              target="_blank"
              rel="noreferrer"
              title="강의 화면에서 이 카드를 고친다 — 웹 풀이는 바로, 덱은 다음 publish 에서 바뀐다"
            >
              이 카드 고치기
            </a>
          ) : null}
        </p>

        <WhyAsked item={item} />

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
            {revealed.whyAsked?.trim() ? (
              <p className="quiz-why-back">
                <span className="quiz-why-label">왜 냈나</span>
                {revealed.whyAsked}
              </p>
            ) : null}
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
          오른쪽이 아는 쪽. 서버가 판정하지 않으므로 이 넷이 남기는 것이 전부다. */}
      <div className="quiz-bar">
        {revealed ? (
          GRADE_LOOK.map((look, index) => (
            <button
              key={look.grade}
              className={`quiz-grade is-${look.grade}`}
              disabled={busy}
              onClick={() => mark(look.grade)}
            >
              <span className="quiz-grade-name">
                {look.label}
                <kbd>{index + 1}</kbd>
              </span>
              {/* 언제 다시 나오는가. **서버가 잰 값이다.** */}
              <span className="quiz-grade-when">{intervalLabel(revealed.next[look.grade])}</span>
            </button>
          ))
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

/** 네 버튼. 순서가 안키다 — 왼쪽이 못 한 쪽, 오른쪽이 아는 쪽. */
const GRADE_LOOK: { grade: QuizGrade; label: string }[] = [
  { grade: "again", label: "Again" },
  { grade: "hard", label: "Hard" },
  { grade: "good", label: "Good" },
  { grade: "easy", label: "Easy" },
];

/**
 * 남은 것을 갈래별로. 안키 아래쪽의 그 숫자 셋이다.
 *
 * 0인 갈래는 안 적는다 — 셋 다 적으면 어느 것이 남은 것인지 세어야 한다.
 */
function QueueCounts({
  tally,
  cram,
  crammed,
}: {
  tally: ReturnType<typeof counts>;
  cram: boolean;
  crammed: number;
}) {
  if (cram) {
    return (
      <span className="quiz-queue">
        <span className="is-cram">몰아보기</span> {crammed + 1}장째
      </span>
    );
  }
  const shown = [
    { key: "new", label: "새 카드", value: tally.new },
    { key: "learning", label: "익히는 중", value: tally.learning },
    { key: "review", label: "복습", value: tally.review },
  ].filter((row) => row.value > 0);
  return (
    <span className="quiz-queue">
      {shown.map((row) => (
        <span key={row.key} className={`is-${row.key}`}>
          {row.label} {row.value}
        </span>
      ))}
    </span>
  );
}

/**
 * 되돌리기. **찍는 줄에 두지 않는다** — 그 줄은 넷으로 이미 꽉 차 있고,
 * 되돌리기는 답을 편 뒤에만 쓰는 것이 아니다.
 */
function UndoButton({
  busy,
  undoable,
  onUndo,
}: {
  busy: boolean;
  undoable: boolean;
  onUndo: () => void;
}) {
  if (!undoable) return null;
  return (
    <button className="quiz-undo" disabled={busy} onClick={onUndo} title="마지막으로 찍은 것을 되돌린다">
      되돌리기 <kbd>Z</kbd>
    </button>
  );
}

/**
 * 낼 카드가 없는 화면. **0이 왜 0인지를 갈라서 말한다.**
 *
 * 재료가 없어서 0인 것과, 오늘 몫을 끝내서 0인 것과, 몰아보기를 한 바퀴 돌아
 * 0인 것은 다음에 할 일이 서로 다르다. 한 문구로 덮으면 「고장」으로 읽힌다
 * (`../../CLAUDE.md` 함정 ③).
 */
function Empty({
  reason,
  nextDueAt,
  now,
  tally,
  done,
  busy,
  error,
  onCram,
  onReset,
}: {
  reason: "no-cards" | "done-today" | "cram-done";
  nextDueAt: number | null;
  now: number;
  tally: ReturnType<typeof counts>;
  done: number;
  busy: boolean;
  error: string;
  onCram: () => void;
  onReset: () => void;
}) {
  if (reason === "no-cards") {
    return (
      <div className="quiz-done">
        <p>
          <strong>이 편에는 웹에서 풀 카드가 없습니다</strong>
        </p>
        <p className="quiz-done-note">덱은 아래에서 받을 수 있습니다.</p>
      </div>
    );
  }

  const later = nextDueAt === null ? null : daysFromNow(nextDueAt, now);
  return (
    <div className="quiz-done">
      <p>
        <strong>
          {reason === "cram-done" ? "몰아보기를 한 바퀴 돌았습니다" : "오늘 몫을 다 했습니다"}
        </strong>
      </p>
      {done ? <p className="quiz-done-note">이번에 {done}장을 찍었습니다.</p> : null}

      {/* **다음 때를 적는다.** 안 적으면 「오늘 몫」이 「더 볼 것 없음」으로 읽힌다. */}
      {nextDueAt !== null ? (
        <p className="quiz-done-next">
          다음 복습 <strong>{dayLabel(nextDueAt)}</strong>
          {later !== null ? ` · ${later === 0 ? "오늘 안에" : `${later}일 뒤`}` : ""} · {tally.later}장
        </p>
      ) : null}

      {error ? <p className="notice is-error">{error}</p> : null}

      <div className="row">
        {/* 시험 전날에 할 수 있는 일. 찍은 것은 똑같이 일정에 들어간다. */}
        {tally.later > 0 ? (
          <button disabled={busy} onClick={onCram}>
            지금 몰아서 보기
          </button>
        ) : null}
        <button className="is-quiet" disabled={busy} onClick={onReset}>
          일정을 지우고 처음부터
        </button>
      </div>
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

/**
 * 왜 이 문제를 냈나 — 앞면에는 **유형 배지만** 질문 위에 선다(2026-10-04 관리자).
 *
 * 생소한 문제를 본 학생이 「이것까지 알아야 하나? 과한 거 아니야?」 싶지 않게
 * 한다. 이유를 적은 글은 답을 편 뒤에 답 아래로 온다(`quiz-why-back`) — 도전
 * 문제의 「강의의 ‘○○’ 대목에서 풀린다」가 앞면에 있으면 답의 절반을 알려 줬다.
 * 도전 문제 표시도 여기 붙는다 — 어렵다는 것을 풀기 전에 알아야 못 풀어도 덜 꺾인다.
 */
export function WhyAsked({ item }: { item: QuizItem }) {
  const tags = whyTags(item);
  if (!item.challenge && !tags.length) return null;
  return (
    <p className="quiz-why">
      {item.challenge ? <span className="badge is-challenge">도전 문제</span> : null}
      {tags.map((tag) => (
        <span key={tag} className={`badge why-${tag}`}>
          {WHY_TAG_LABEL[tag]}
        </span>
      ))}
    </p>
  );
}

/**
 * 「왜 냈나」의 유형 배지(2026-10-04 관리자 — 「유형별로 정리해서 뱃지를」).
 *
 * **파이프라인의 `quizgen/prequiz/schema.py` 의 `WHY_TAG_LABEL` 과 같아야 한다** —
 * 화면은 그 폴더를 모른다. 바꾸면 둘 다 바꾼다. 모르는 값은 그리지 않는다.
 */
const WHY_TAG_LABEL: Record<string, string> = {
  exam: "기출",
  clinical: "임상",
  later: "연결 개념",
  annotation: "필기 강조",
  basis: "기본 개념",
};

function whyTags(item: QuizItem): string[] {
  return (item.whyTags ?? []).filter((tag) => tag in WHY_TAG_LABEL);
}

function FocusBadge({ item }: { item: QuizItem }) {
  // 「왜 냈나」 배지가 있는 카드는 그쪽이 이유를 말한다. 여기서 또 말하면 이유가
  // 진행 줄과 질문 위 두 곳에 갈라져 선다.
  const label = whyTags(item).length ? undefined : FOCUS_LABEL[item.focus];
  const state = stateOf(item);
  // 잊어서 돌아온 카드는 그것을 말한다. 안키가 빨강으로 말하는 자리다 —
  // 같은 카드가 왜 또 나왔는지 알 수 있어야 한다.
  const relearn = state === "relearn" ? <span className="badge is-relearn">다시</span> : null;
  if (!label && !item.examHit && !relearn) return null;
  return (
    <span className="quiz-focus">
      {label}
      {item.examHit ? <span className="badge">기출</span> : null}
      {relearn}
    </span>
  );
}

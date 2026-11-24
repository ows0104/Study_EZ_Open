import { useCallback, useRef, useState } from "react";
import { api } from "../api";
import type { JokboAnswerMark, JokboBand, JokboMark, JokboMarkBefore, JokboResult } from "../types/jokbo";
import type { Verdict } from "./selection";

/**
 * 족보 오답노트 표시(2026-11-14 개편). 예습 퀴즈의 헷갈려요/이해했어요처럼 답을 본 뒤 하나를 고른다.
 *
 * 모르겠음 high · 주의 mid(맞혔지만 나중에 볼 수도 있음) · 괜찮음 null(오답노트에서 뺌).
 * 저장 값은 그대로다. 예전의 low(하 헷갈림)는 고치지 않고 **주의로 보인다** — 사람이 누를 때만 바뀐다.
 */
export type Shown = "high" | "mid" | null;

export const RATINGS: { key: Shown; label: string; tone: string }[] = [
  { key: "high", label: "모르겠음", tone: "unknown" },
  { key: "mid", label: "주의", tone: "caution" },
  { key: null, label: "괜찮음", tone: "fine" },
];

/** 화면에 보이는 표시. low는 주의로 합친다. */
export function shownBand(band: JokboBand | null | undefined): Shown {
  if (band === "high") return "high";
  if (band === "mid" || band === "low") return "mid";
  return null;
}

function itemPath(eventId: string, itemId: string) {
  return `/api/jokbo/events/${encodeURIComponent(eventId)}/items/${encodeURIComponent(itemId)}`;
}

export function postAnswer(eventId: string, itemId: string, result: JokboResult) {
  return api<JokboAnswerMark>(`${itemPath(eventId, itemId)}/answer`, { method: "POST", body: JSON.stringify({ result }) });
}

export function putBand(eventId: string, itemId: string, band: JokboBand | null) {
  return api<JokboMark>(`${itemPath(eventId, itemId)}/mark`, { method: "PUT", body: JSON.stringify({ band }) });
}

/** Z로 고른 답 취소(2026-11-24). `before`는 그 답을 기록한 `postAnswer`가 돌려준 값이다. */
export function undoAnswer(eventId: string, itemId: string, result: JokboResult, before: JokboMarkBefore) {
  return api<JokboMark>(`${itemPath(eventId, itemId)}/answer/undo`, { method: "POST", body: JSON.stringify({ result, before }) });
}

/**
 * 족보 풀이의 오답노트 표시와 서버 쓰기(강의 하나 족보·모아풀기 공용).
 *
 * 같은 문항의 쓰기는 보낸 순서대로 간다 — 답 기록 → 표시 → 답 취소.
 * 순서가 뒤집히면 고른 표시가 채점의 high로 덮이고, 답 취소는 답 기록이 준 `before`가 있어야 보낼 수 있다.
 * 쓰기 실패는 풀이를 막지 않는다. 다음 불러오기에서 서버 값으로 돌아간다.
 */
export function useMarkWriter(split: (key: string) => { eventId: string; itemId: string }) {
  const [bands, setBands] = useState<Record<string, JokboBand | null>>({});
  const bandsRef = useRef(bands);
  bandsRef.current = bands;
  const queue = useRef<Record<string, Promise<unknown>>>({});
  // 문항마다 아직 취소하지 않은 답 기록과, 답 기록 직전의 화면 표시(없었으면 undefined).
  const answers = useRef<Record<string, { mark: Promise<JokboAnswerMark | null>; shown: JokboBand | null | undefined }[]>>({});

  const run = useCallback(<T,>(key: string, step: () => Promise<T>): Promise<T | null> => {
    const next = (queue.current[key] ?? Promise.resolve()).then(step).catch(() => null);
    queue.current[key] = next;
    return next;
  }, []);

  const answered = useCallback((key: string, verdict: Verdict) => {
    const { eventId, itemId } = split(key);
    const shown = key in bandsRef.current ? bandsRef.current[key] : undefined;
    if (verdict === "wrong") setBands(prev => ({ ...prev, [key]: "high" }));
    const mark = run(key, () => postAnswer(eventId, itemId, verdict));
    (answers.current[key] ??= []).push({ mark, shown });
  }, [split, run]);

  const rate = useCallback((key: string, band: JokboBand | null) => {
    if ((bandsRef.current[key] ?? null) === band) return; // 틀려서 서버가 이미 high, 또는 원래 표시 그대로
    const { eventId, itemId } = split(key);
    setBands(prev => ({ ...prev, [key]: band }));
    void run(key, () => putBand(eventId, itemId, band));
  }, [split, run]);

  const unanswer = useCallback((key: string, verdict: Verdict) => {
    const last = answers.current[key]?.pop();
    if (!last) return;
    const { eventId, itemId } = split(key);
    setBands(prev => {
      const next = { ...prev };
      if (last.shown === undefined) delete next[key]; else next[key] = last.shown;
      return next;
    });
    void run(key, async () => {
      const got = await last.mark;
      return got?.before ? undoAnswer(eventId, itemId, verdict, got.before) : null; // 기록이 실패했으면 취소할 것도 없다
    });
  }, [split, run]);

  return { bands, setBands, answered, rate, unanswer };
}

/** 오답노트 카드 아래 세 버튼. 지금 표시가 눌려 있다. */
export function RatingButtons({ band, onChange }: { band: JokboBand | null; onChange: (next: Shown) => void }) {
  const now = shownBand(band);
  return (
    <div className="jokbo-ratings" role="radiogroup" aria-label="오답노트">
      {RATINGS.map(r => (
        <button key={r.tone} type="button" role="radio" className={`jokbo-rating is-${r.tone}`}
          aria-checked={now === r.key} onClick={() => { if (now !== r.key) onChange(r.key); }}>
          {r.label}
        </button>
      ))}
    </div>
  );
}

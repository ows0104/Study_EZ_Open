import { api } from "../api";
import type { JokboBand, JokboMark } from "../types/jokbo";

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

export function postAnswer(eventId: string, itemId: string, result: "correct" | "wrong" | "ungraded") {
  return api<JokboMark>(`${itemPath(eventId, itemId)}/answer`, { method: "POST", body: JSON.stringify({ result }) });
}

export function putBand(eventId: string, itemId: string, band: JokboBand | null) {
  return api<JokboMark>(`${itemPath(eventId, itemId)}/mark`, { method: "PUT", body: JSON.stringify({ band }) });
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

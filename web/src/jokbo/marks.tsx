import { api } from "../api";
import type { JokboBand, JokboMark } from "../types/jokbo";

/**
 * 족보 오답노트 표시(2026-11-14). amgi 족보 오답노트의 상·중·하를 그대로 쓴다.
 * 족보 퀴즈에서 틀리면 서버가 「상 틀림」을 붙이고, 사람이 바꾸거나 뗀다.
 */
export const BANDS: { key: JokboBand; label: string; word: string }[] = [
  { key: "high", label: "상", word: "틀림" },
  { key: "mid", label: "중", word: "좁혀서" },
  { key: "low", label: "하", word: "헷갈림" },
];

function itemPath(eventId: string, itemId: string) {
  return `/api/jokbo/events/${encodeURIComponent(eventId)}/items/${encodeURIComponent(itemId)}`;
}

export function postAnswer(eventId: string, itemId: string, result: "correct" | "wrong" | "ungraded") {
  return api<JokboMark>(`${itemPath(eventId, itemId)}/answer`, { method: "POST", body: JSON.stringify({ result }) });
}

export function putBand(eventId: string, itemId: string, band: JokboBand | null) {
  return api<JokboMark>(`${itemPath(eventId, itemId)}/mark`, { method: "PUT", body: JSON.stringify({ band }) });
}

/** 상·중·하 세 버튼. 켜진 것을 다시 누르면 뗀다. */
export function BandButtons({ band, onChange, disabled }: {
  band: JokboBand | null;
  onChange: (next: JokboBand | null) => void;
  disabled?: boolean;
}) {
  return (
    <div className="jokbo-bands" role="group" aria-label="오답노트">
      <span className="jokbo-bands-label">오답노트</span>
      {BANDS.map(b => (
        <button key={b.key} type="button" className={`jokbo-band is-${b.key}`} aria-pressed={band === b.key} disabled={disabled}
          onClick={() => onChange(band === b.key ? null : b.key)}>
          {b.label} {b.word}
        </button>
      ))}
    </div>
  );
}

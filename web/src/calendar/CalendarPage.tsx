import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import type { TimetableEvent } from "../types";
import { CalendarGrid } from "./CalendarGrid";
import { EventChip } from "./EventChip";
import { addDays, formatWeekTitle, startOfWeek, toCalendarEntries, type CalendarMode } from "./entries";

/**
 * 캘린더가 홈이다.
 *
 * 시간표만으로 완성된 화면이고, 파이프라인 산출물은 나중에 점으로 붙는다.
 * 그래서 첫 배포에 강의 자료가 하나도 없어도 쓸모가 있다.
 */
export function CalendarPage() {
  const [events, setEvents] = useState<TimetableEvent[] | null>(null);
  const [error, setError] = useState("");
  const [mode, setMode] = useState<CalendarMode>("week");
  const [anchorDate, setAnchorDate] = useState(() => new Date());

  useEffect(() => {
    api<{ events: TimetableEvent[] }>("/api/timetable")
      .then((payload) => setEvents(payload.events))
      .catch((cause: Error) => setError(cause.message));
  }, []);

  const entries = useMemo(() => toCalendarEntries(events ?? []), [events]);

  const heading =
    mode === "week"
      ? formatWeekTitle(startOfWeek(anchorDate))
      : `${anchorDate.getFullYear()}년 ${anchorDate.getMonth() + 1}월`;

  function step(direction: -1 | 1) {
    setAnchorDate((current) =>
      mode === "week"
        ? addDays(current, 7 * direction)
        : new Date(current.getFullYear(), current.getMonth() + direction, 1),
    );
  }

  if (error) return <p className="notice is-error">{error}</p>;
  if (!events) return <p className="notice">시간표를 불러오는 중…</p>;

  return (
    <div className="calendar-page">
      <div className="calendar-toolbar">
        <div className="calendar-mode" role="group" aria-label="보기 전환">
          <button className={mode === "week" ? "is-active" : ""} onClick={() => setMode("week")}>
            주
          </button>
          <button className={mode === "month" ? "is-active" : ""} onClick={() => setMode("month")}>
            월
          </button>
        </div>
        <h1>{heading}</h1>
        <div className="calendar-actions">
          <button onClick={() => step(-1)} aria-label="이전">
            ‹
          </button>
          <button onClick={() => setAnchorDate(new Date())}>오늘</button>
          <button onClick={() => step(1)} aria-label="다음">
            ›
          </button>
        </div>
      </div>

      <CalendarGrid
        mode={mode}
        anchorDate={anchorDate}
        entries={entries}
        renderEntry={(entry, compact) => <EventChip key={entry.id} entry={entry} compact={compact} />}
      />

      <p className="calendar-legend">
        <span>
          <i className="chip-dot is-notes" /> 강의록
        </span>
        <span>
          <i className="chip-dot is-quiz" /> 퀴즈
        </span>
        <span>
          <i className="chip-dot is-preview" /> 예습
        </span>
        <small>강의를 누르면 새 창에서 열립니다.</small>
      </p>
    </div>
  );
}

import { useEffect, useState, type CSSProperties, type ReactNode } from "react";
import {
  addDays,
  defaultHourSlots,
  entryRowSpan,
  startOfWeek,
  toDateKey,
  weekDayLabels,
  type CalendarEntry,
  type CalendarMode,
} from "./entries";

/** 지금 몇 시인가. 1분마다 다시 그린다 — 현재 시각 선이 멈춰 있으면 거짓말이 된다. */
function useNow() {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), 60_000);
    return () => window.clearInterval(timer);
  }, []);
  return now;
}

/**
 * 주간·월간 격자.
 *
 * 표시만 담당한다. 칸 내용은 `renderEntry`가 만들고, 클릭으로 무엇이 열리는지는
 * 부모가 정한다. 개인 일정이 없으므로 빈 칸은 누를 대상이 아니고, 그래서
 * 버튼이 아니라 그냥 칸이다.
 */
export function CalendarGrid({
  mode,
  anchorDate,
  entries,
  renderEntry,
}: {
  mode: CalendarMode;
  anchorDate: Date;
  entries: CalendarEntry[];
  renderEntry: (entry: CalendarEntry, compact: boolean) => ReactNode;
}) {
  const now = useNow();
  const todayKey = toDateKey(now);

  if (mode === "week") {
    const weekStart = startOfWeek(anchorDate);
    const weekDates = Array.from({ length: 5 }, (_, index) => addDays(weekStart, index));
    const weekStartKey = toDateKey(weekDates[0]);
    const weekEndKey = toDateKey(weekDates[4]);
    const weekEntries = entries.filter((entry) => entry.date >= weekStartKey && entry.date <= weekEndKey);
    // 시간표에 09:40처럼 정각이 아닌 칸이 섞여 있다. 그 시각도 줄로 만들어야
    // 강의가 통째로 사라지지 않는다.
    const activeHours = weekEntries.map((entry) => Number(entry.startTime.slice(0, 2))).filter(Number.isFinite);
    const hourSlots = [...new Set([...defaultHourSlots, ...activeHours])].sort((left, right) => left - right);

    // 현재 시각 선. 보고 있는 주에 오늘이 없거나, 지금 시각에 해당하는 줄이
    // 없으면(점심시간처럼) 긋지 않는다.
    const nowRow = todayKey >= weekStartKey && todayKey <= weekEndKey ? hourSlots.indexOf(now.getHours()) : -1;

    return (
      <section className="week-calendar" aria-label="주간 캘린더">
        <div className="week-head is-spacer" style={{ gridColumn: 1, gridRow: 1 }} />
        {weekDates.map((day, index) => {
          const key = toDateKey(day);
          return (
            <div
              className={`week-head ${key === todayKey ? "is-today" : ""}`}
              key={key}
              style={{ gridColumn: index + 2, gridRow: 1 }}
            >
              <span>{weekDayLabels[index]}</span>
              <strong>{day.getDate()}</strong>
            </div>
          );
        })}
        {hourSlots.map((hour, rowIndex) => (
          <div className="week-row" key={hour}>
            {/* 첫 줄만 라벨을 안 올린다. 위에 그을 경계선이 없어서 올려 봐야
                머리줄 뒤로 숨는다. */}
            <div
              className={`calendar-time ${rowIndex === 0 ? "is-first" : ""}`}
              style={{ gridColumn: 1, gridRow: rowIndex + 2 }}
            >
              <strong>{String(hour).padStart(2, "0")}:00</strong>
            </div>
            {weekDates.map((day, dayIndex) => (
              <div
                className={`week-cell ${toDateKey(day) === todayKey ? "is-today" : ""}`}
                key={`${toDateKey(day)}-${hour}`}
                style={{ gridColumn: dayIndex + 2, gridRow: rowIndex + 2 }}
              />
            ))}
          </div>
        ))}
        {hourSlots.includes(13) ? (
          <div
            className="calendar-lunch-divider"
            style={{ gridColumn: "1 / -1", gridRow: hourSlots.indexOf(13) + 2 }}
            aria-hidden="true"
          />
        ) : null}
        {nowRow >= 0 ? (
          <div
            className="calendar-now"
            style={
              {
                gridColumn: "1 / -1",
                gridRow: nowRow + 2,
                "--at": now.getMinutes() / 60,
              } as CSSProperties
            }
            aria-hidden="true"
          />
        ) : null}
        {weekEntries.map((entry) => {
          const dayIndex = weekDates.findIndex((day) => toDateKey(day) === entry.date);
          const startIndex = hourSlots.indexOf(Number(entry.startTime.slice(0, 2)));
          if (dayIndex < 0 || startIndex < 0) return null;
          return (
            <div
              className="week-event-span"
              key={entry.id}
              style={{
                gridColumn: dayIndex + 2,
                gridRow: `${startIndex + 2} / span ${entryRowSpan(entry, hourSlots, startIndex)}`,
              }}
            >
              {renderEntry(entry, false)}
            </div>
          );
        })}
      </section>
    );
  }

  const monthStart = new Date(anchorDate.getFullYear(), anchorDate.getMonth(), 1);
  const monthGridStart = startOfWeek(monthStart);
  // 주 6개 × 평일 5일. 주말은 그리지 않는다 — 수업이 없다.
  const monthDates = Array.from({ length: 30 }, (_, index) =>
    addDays(monthGridStart, Math.floor(index / 5) * 7 + (index % 5)),
  );

  return (
    <section className="month-calendar" aria-label="월간 캘린더">
      {weekDayLabels.map((day) => (
        <div className="month-weekday" key={day}>
          {day}
        </div>
      ))}
      {monthDates.map((day) => {
        const key = toDateKey(day);
        const cellEntries = entries.filter((entry) => entry.date === key);
        const outside = day.getMonth() !== anchorDate.getMonth();
        return (
          <div className={`month-day ${outside ? "is-outside" : ""} ${key === todayKey ? "is-today" : ""}`} key={key}>
            <span className="month-date">{day.getDate()}</span>
            <span className="month-events">{cellEntries.map((entry) => renderEntry(entry, true))}</span>
          </div>
        );
      })}
    </section>
  );
}

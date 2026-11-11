import { useEffect, useState, type ReactNode } from "react";
import {
  addDays,
  defaultHourSlots,
  entryRowSpan,
  startOfWeek,
  studyDayKey,
  toDateKey,
  weekDayLabels,
  type CalendarEntry,
  type CalendarMode,
} from "./entries";

/** 오늘이 며칠인가. 새벽 4시를 넘기면 "오늘" 표시가 어제 칸에 남지 않도록 1분마다 다시 본다. */
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
  renderDay,
  onStep,
}: {
  mode: CalendarMode;
  anchorDate: Date;
  entries: CalendarEntry[];
  renderEntry: (entry: CalendarEntry, compact: boolean) => ReactNode;
  /**
   * 격자 **맨 아랫줄**에 날짜마다 붙는 것. 하루치 모아받기가 여기 선다.
   *
   * 처음에는 날짜 머리에 알약으로 달았는데 안 예쁘다는 판정이 나왔다
   * (2026-09-16 관리자 지시 — 시간표 제일 아래에 네모로 넣어라). 자리를 옮기니
   * 둘이 같이 나아졌다 — 머리줄은 sticky 라 알약이 늘 따라다녔고, 아랫줄은
   * **다 보고 나서 받는 자리**라 하는 일의 순서와도 맞는다.
   *
   * 교시 줄과 같은 열에 서므로 어느 날 것인지는 자리가 말한다. 그래서 이 줄은
   * 날짜를 다시 안 적는다.
   *
   * **주간에만 부른다.** 월간은 날짜 칸이 딱지로 이미 차고, 아랫줄을 붙여 봐야
   * 그 줄이 어느 날 것인지 가리킬 열이 없다. 무엇을 그릴지는 여전히 부모가
   * 정한다(`renderEntry` 와 같은 규칙이다).
   */
  renderDay?: (dateKey: string) => ReactNode;
  /** 주 넘기기. 날짜 줄 양끝(시각 칸 위 ‹, 금요일 오른쪽 ›)에 선다(2026-11-07 사용자 지시). */
  onStep?: (direction: -1 | 1) => void;
}) {
  const now = useNow();
  const todayKey = studyDayKey(now);

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

    // 교시 줄은 남는 높이를 나눠 갖고(`1fr`), 맨 아랫줄은 **든 것만큼만** 선다.
    // CSS 의 `grid-auto-rows` 는 줄마다 다르게 못 주므로 여기서 통째로 적는다 —
    // 안 그러면 모아받기 줄이 교시 한 칸만큼 부풀어 빈 자리를 든다.
    const footRow = hourSlots.length + 2;
    const rows = renderDay
      ? { gridTemplateRows: `46px repeat(${hourSlots.length}, minmax(var(--row-min), 1fr)) auto` }
      : undefined;

    return (
      <section className="week-calendar" aria-label="주간 캘린더" style={rows}>
        <div className="week-head is-spacer" style={{ gridColumn: 1, gridRow: 1 }}>
          {onStep ? <button type="button" className="week-step" onClick={() => onStep(-1)} aria-label="이전">‹</button> : null}
        </div>
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
              {onStep && index === 4 ? (
                <button type="button" className="week-step is-next" onClick={() => onStep(1)} aria-label="다음">›</button>
              ) : null}
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
        {renderDay ? (
          <>
            {/* 시각 열 자리. 교시 줄의 시각처럼 **이 줄이 무엇인지**를 왼쪽이 적는다. */}
            <div className="week-foot is-label" style={{ gridColumn: 1, gridRow: footRow }}>
              <strong>모아받기</strong>
            </div>
            {weekDates.map((day, index) => (
              <div
                className={`week-foot ${toDateKey(day) === todayKey ? "is-today" : ""}`}
                key={`foot-${toDateKey(day)}`}
                style={{ gridColumn: index + 2, gridRow: footRow }}
              >
                {renderDay(toDateKey(day))}
              </div>
            ))}
          </>
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

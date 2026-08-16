import type { LectureRef } from "../types";
import type { CalendarEntry } from "./entries";

/** 강의 상세는 새 창이다. 캘린더를 잃지 않고 자료를 여닫으라는 뜻이다. */
export function lectureHref(lecture: Pick<LectureRef, "subject" | "runId">) {
  return `/lectures/${encodeURIComponent(lecture.subject)}/${encodeURIComponent(lecture.runId)}`;
}

/**
 * 점 세 개.
 *
 * 강조색은 "네가 열어 볼 것이 있다"는 뜻으로만 쓴다. 나머지 화면이 전부
 * 무채색인 이유가 이것이다 — 색이 여러 뜻을 가지면 아무 뜻도 없어진다.
 */
function Marks({ marks }: { marks: LectureRef["marks"] }) {
  const dots: [keyof LectureRef["marks"], string][] = [
    ["notes", "강의록"],
    ["quiz", "퀴즈"],
    ["preview", "예습"],
  ];
  const on = dots.filter(([key]) => marks[key]);
  if (!on.length) return null;
  return (
    <span className="chip-marks" aria-label={`${on.map(([, label]) => label).join("·")} 있음`}>
      {on.map(([key]) => (
        <i key={key} className={`chip-dot is-${key}`} />
      ))}
    </span>
  );
}

export function EventChip({ entry, compact }: { entry: CalendarEntry; compact: boolean }) {
  const primary = entry.detail || entry.title;
  const className = [
    "calendar-event",
    `is-${entry.category}`,
    compact ? "is-compact" : "",
    entry.lectures.length ? "has-lecture" : "",
  ]
    .filter(Boolean)
    .join(" ");

  const body = (
    <>
      <strong className="calendar-event-primary">{primary}</strong>
      {!compact && entry.professor ? <small className="calendar-event-professor">{entry.professor}</small> : null}
      {!compact && entry.detail && entry.course ? (
        <small className="calendar-event-series">{entry.course}</small>
      ) : null}
    </>
  );

  if (entry.lectures.length === 1) {
    const [lecture] = entry.lectures;
    return (
      <a className={className} href={lectureHref(lecture)} target="_blank" rel="noreferrer" title={primary}>
        {body}
        <Marks marks={lecture.marks} />
      </a>
    );
  }

  // 한 교시에 여러 강의가 열릴 때. 어느 것을 열지 사용자가 고른다 —
  // 자동으로 하나를 고르면 다른 강의는 화면에서 사라진다.
  if (entry.lectures.length > 1) {
    return (
      <div className={className} title={primary}>
        {body}
        <span className="calendar-event-choices">
          {entry.lectures.map((lecture) => (
            <a key={lecture.runId} href={lectureHref(lecture)} target="_blank" rel="noreferrer">
              {lecture.title}
              <Marks marks={lecture.marks} />
            </a>
          ))}
        </span>
      </div>
    );
  }

  return (
    <div className={className} title={primary}>
      {body}
    </div>
  );
}

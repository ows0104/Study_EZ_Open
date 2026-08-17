import type { LectureRef } from "../types";
import { chipState, type CalendarEntry } from "./entries";

/** 강의 상세는 새 창이다. 캘린더를 잃지 않고 자료를 여닫으라는 뜻이다. */
export function lectureHref(lecture: Pick<LectureRef, "subject" | "runId">) {
  return `/lectures/${encodeURIComponent(lecture.subject)}/${encodeURIComponent(lecture.runId)}`;
}

const markLabels: [keyof LectureRef["marks"], string][] = [
  ["notes", "필기"],
  ["quiz", "퀴즈"],
  ["preview", "예습"],
];

/**
 * 점 세 개.
 *
 * 강조색은 "네가 열어 볼 것이 있다"는 뜻으로만 쓴다. 나머지 화면이 전부
 * 무채색인 이유가 이것이다 — 색이 여러 뜻을 가지면 아무 뜻도 없어진다.
 *
 * 칸에서는 점만 찍고, 자리가 있는 패널에서는 `labelled`로 이름을 붙인다.
 */
export function Marks({ marks, labelled = false }: { marks: LectureRef["marks"]; labelled?: boolean }) {
  const on = markLabels.filter(([key]) => marks[key]);
  if (!on.length) return null;
  if (labelled) {
    return (
      <span className="chip-marks is-labelled">
        {on.map(([key, label]) => (
          <span className="chip-mark" key={key}>
            <i className={`chip-dot is-${key}`} />
            {label}
          </span>
        ))}
      </span>
    );
  }
  return (
    <span className="chip-marks" aria-label={`${on.map(([, label]) => label).join("·")} 있음`}>
      {on.map(([key]) => (
        <i key={key} className={`chip-dot is-${key}`} />
      ))}
    </span>
  );
}

/**
 * 캘린더 한 칸.
 *
 * **자료가 있든 없든 버튼이다.** 어느 칸을 눌러도 패널이 열리고, 거기서 자료를
 * 주거나 아직 없다고 말한다. 자료 있는 칸만 누를 수 있게 두면 화면 대부분이
 * 죽은 사각형이 되고, 사용자는 그것을 "고장"으로 읽는다.
 */
export function EventChip({
  entry,
  compact,
  onOpen,
  active,
}: {
  entry: CalendarEntry;
  compact: boolean;
  onOpen: (entry: CalendarEntry) => void;
  active: boolean;
}) {
  const primary = entry.detail || entry.title;
  const marks = entry.lectures[0]?.marks;
  // 계열은 범주가, 진하기는 학습 상태가 정한다. 두 축을 색상 하나에 겹치지
  // 않고 색상과 명도로 나눠 실었다는 뜻이다.
  const className = [
    "calendar-event",
    `is-${entry.category}`,
    `state-${chipState(entry)}`,
    compact ? "is-compact" : "",
    // `is-active`가 아니다 — base.css의 `button.is-active`가 토글 버튼용으로 그
    // 이름을 이미 쓰고 있어서, 칸에 붙이면 계열과 무관하게 강조색 배경·글자색이
    // 딸려 온다. 눌린 칸이 전부 파래지던 것이 그것이었다.
    active ? "is-open" : "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <button type="button" className={className} title={primary} onClick={() => onOpen(entry)}>
      <strong className="calendar-event-primary">{primary}</strong>
      {!compact && entry.professor ? <small className="calendar-event-professor">{entry.professor}</small> : null}
      {!compact && entry.detail && entry.course ? (
        <small className="calendar-event-series">{entry.course}</small>
      ) : null}
      {/* 한 교시에 여러 강의가 열릴 때(선택형 과목)는 몇 개인지만 찍는다.
          어느 것을 열지는 패널에서 고른다 — 칸이 그것을 담기에는 좁다. */}
      {entry.lectures.length > 1 ? (
        <span className="chip-count">{entry.lectures.length}</span>
      ) : marks ? (
        <Marks marks={marks} />
      ) : null}
    </button>
  );
}

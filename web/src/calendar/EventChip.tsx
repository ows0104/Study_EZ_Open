import { ChipLearning, hasLearningMarks, learningDescription } from "./ChipLearning";
import { type CalendarEntry } from "./entries";
import { splitSubject, type DisplayInfo } from "./kinds";
import { ProfTag, professorDescription } from "./ProfessorInfo";

/**
 * 캘린더 한 칸(2026-11 개편).
 *
 * **자료가 있든 없든 버튼이다.** 어느 칸을 눌러도 패널이 열리고, 거기서 자료를
 * 주거나 아직 없다고 말한다.
 *
 * 강의·실습·TBL·CBL은 같은 모양이다(옅게 하니 쉬는 시간처럼 보였다 — 사용자 지시). 시험만 빨강.
 * 제목 앞 번호는 흐린 회색, 아래 줄은 「교수 + 변경 표시 · 분야」(날짜·시각 없음).
 */
export function EventChip({
  entry,
  info,
  compact,
  onOpen,
  active,
  showLearning = true,
}: {
  entry: CalendarEntry;
  info?: DisplayInfo;
  compact: boolean;
  onOpen: (entry: CalendarEntry) => void;
  active: boolean;
  showLearning?: boolean;
}) {
  const { subject, title } = splitSubject(entry.detail);
  const primary = (info?.kind === "exam" && info.label) || title || entry.title;
  const sources = entry.lectures.map(lecture => lecture.previewSource);
  const professorInfo = sources.flatMap(source => (source ? [professorDescription(source)] : [])).join("\n");
  // 그릴 것(복습 막대·예습 퀴즈·회독)이 있을 때만 아래 줄을 둔다 — Main-Quiz 없는 TBL 칸 등은 줄이 없다.
  const hasLearning = showLearning && hasLearningMarks(entry.lectures);
  const learning = showLearning ? entry.lectures.map(learningDescription).filter(Boolean).join(" · ") : "";
  // 번호는 시간표에 실제 강의 제목이 있을 때만 붙인다(「임상의학입문 1」처럼 제목뿐인 칸에는 안 붙인다).
  const code = info && entry.detail && info.kind !== "exam" && info.kind !== "other" ? info.code : "";
  const className = [
    "calendar-event",
    hasLearning ? "has-learning" : "",
    `is-${entry.category}`,
    info ? `kind-${info.kind}` : "",
    compact ? "is-compact" : "",
    // `is-active`가 아니다 — base.css의 `button.is-active`가 토글 버튼용으로 그 이름을 쓴다.
    active ? "is-open" : "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <button
      type="button"
      className={className}
      title={[code ? `${code} ${primary}` : primary, professorInfo, learning].filter(Boolean).join("\n")}
      onClick={() => onOpen(entry)}
    >
      <strong className="calendar-event-primary">
        {code ? <span className="chip-code">{code}</span> : null}
        {primary}
        {/* 월간처럼 아래 줄이 없는 칸에서도 교수 변경 표시는 남긴다. */}
        {compact ? <ProfTag values={sources} /> : null}
      </strong>
      {!compact && (entry.professor || subject) ? (
        <small className="calendar-event-meta">
          {entry.professor ? <span className="calendar-event-professor">{entry.professor}<ProfTag values={sources} /></span> : null}
          {subject ? <span className="calendar-event-series">{subject}</span> : null}
        </small>
      ) : null}
      {hasLearning && !compact ? (
        <span className="calendar-event-footer">
          <ChipLearning lectures={entry.lectures} />
        </span>
      ) : null}
    </button>
  );
}

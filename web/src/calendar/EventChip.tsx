import { ChipLearning, learningDescription } from "./ChipLearning";
import { hasTodo, type CalendarEntry } from "./entries";

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
  const hasLearning = entry.lectures.length > 0;
  const learning = entry.lectures.map(learningDescription).filter(Boolean).join(" · ");
  // 왼쪽 띠는 범주만 진다. 할 일이 남았는지는 제목의 무게로만 말하고,
  // 아래 막대는 왼쪽 예습 풀이율, 오른쪽 복습 학습도다.
  const className = [
    "calendar-event",
    hasLearning ? "has-learning" : "",
    `is-${entry.category}`,
    hasTodo(entry) ? "state-todo" : "",
    compact ? "is-compact" : "",
    // `is-active`가 아니다 — base.css의 `button.is-active`가 토글 버튼용으로 그
    // 이름을 이미 쓰고 있어서, 칸에 붙이면 계열과 무관하게 강조색 배경·글자색이
    // 딸려 온다. 눌린 칸이 전부 파래지던 것이 그것이었다.
    active ? "is-open" : "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <button type="button" className={className} title={learning ? `${primary}\n${learning}` : primary} onClick={() => onOpen(entry)}>
      <strong className="calendar-event-primary">{primary}</strong>
      {/* 교수와 과목은 한 겹으로 싼다. 칸이 낮으면 CSS가 이 겹을 한 줄로 눕히고
          넉넉하면 `display: contents`로 풀어 예전처럼 두 줄로 편다. 합치면 줄
          하나(13px)가 예산에서 빠져서, 같은 칸 높이에서 과목이 더 오래 산다. */}
      {!compact && (entry.professor || (entry.detail && entry.course)) ? (
        <small className="calendar-event-meta">
          {entry.professor ? <span className="calendar-event-professor">{entry.professor}</span> : null}
          {entry.detail && entry.course ? <span className="calendar-event-series">{entry.course}</span> : null}
        </small>
      ) : null}
      {hasLearning ? <span className="calendar-event-footer">
        <ChipLearning lectures={entry.lectures} />
      </span> : null}
    </button>
  );
}

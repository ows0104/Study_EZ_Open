import type { LectureRef } from "../types";
import { hasSlots, hasTodo, lectureSlots, type CalendarEntry, type SlotState } from "./entries";

const stateLabels: Record<SlotState, string> = {
  none: "아직 없음",
  ready: "받을 것 있음",
  done: "했음",
};

/**
 * 자리 둘.
 *
 * **자리는 늘 서 있다.** 아무것도 없는 자리는 작은 점으로 쉬고, 자료가 올라오면
 * 빈 도형이 되고, 하고 나면 채워진다. 도형이 생겼다 사라지면서 폭이 변하면
 * 강의끼리 점 위치가 어긋나는데, 그러면 여러 칸을 훑을 때 자리로 뜻을 읽을 수
 * 없게 된다. 왼쪽이 예습, 오른쪽이 복습이고 순서는 절대 안 바뀐다.
 *
 * **모양이 나타나는 것 자체가 소식이다.** 그래서 둘 다 같은 점으로 쉰다 —
 * 쉬는 자리를 미리 원과 네모로 갈라 두면 "생겼다"가 약해지고, 어차피 3px에서는
 * 네모도 점으로 보인다. 어느 자리인지는 위치가 늘 말한다.
 *
 * **강조색은 "네가 열어 볼 것이 있다"는 뜻으로만 쓴다.** 빈 도형만 계열색을
 * 받고, 채운 것은 무채색으로 가라앉고, 쉬는 점은 더 옅다. 끝낸 것을 색으로
 * 두면 다 한 칸이 제일 시끄러워져서 남은 할 일이 묻힌다.
 */
export function ChipSlots({ lecture }: { lecture: LectureRef }) {
  const slots = lectureSlots(lecture);
  const progress = lecture.prequizProgress;
  const preLabel =
    slots.pre === "ready" && progress
      ? `예습 ${progress.answered}/${progress.total}`
      : `예습 ${stateLabels[slots.pre]}`;

  return (
    <span className="chip-slots" aria-label={`${preLabel} · 복습 ${stateLabels[slots.main]}`}>
      <i
        className={`chip-slot is-pre is-${slots.pre}`}
        // 채움 비율은 빈 도형 위에만 얹는다. 없으면 0%로 떨어지고, 그건 아직
        // 아무것도 안 푼 것과 같은 그림이라 맞다.
        style={slots.preFill === null ? undefined : { ["--fill" as string]: `${Math.round(slots.preFill * 100)}%` }}
      />
      <i className={`chip-slot is-main is-${slots.main}`} />
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
  // 왼쪽 띠는 범주만 진다. 할 일이 남았는지는 제목의 무게로만 말하고,
  // 무엇이 얼마나 남았는지는 아래 자리 둘이 말한다.
  const className = [
    "calendar-event",
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
    <button type="button" className={className} title={primary} onClick={() => onOpen(entry)}>
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
      {/* 한 교시에 여러 강의가 열릴 때(선택형 과목)는 몇 개인지만 찍는다.
          어느 것을 열지는 패널에서 고른다 — 칸이 그것을 담기에는 좁다. */}
      {entry.lectures.length > 1 ? (
        <span className="chip-count">{entry.lectures.length}</span>
      ) : hasSlots(entry) ? (
        <ChipSlots lecture={entry.lectures[0]} />
      ) : null}
    </button>
  );
}

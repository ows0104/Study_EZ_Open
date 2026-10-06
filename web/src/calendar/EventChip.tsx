import type { LectureRef } from "../types/lectures";
import {
  adminLectureSlots,
  hasSlots,
  hasTodo,
  lectureSlots,
  type AdminSlotState,
  type CalendarEntry,
  type SlotState,
} from "./entries";

const stateLabels: Record<SlotState, string> = {
  none: "아직 없음",
  ready: "학습 가능",
  done: "했음",
};

/** 관리자가 읽는 말. 「내가 받을 것」이 아니라 「내가 올려 둔 것」을 센다. */
const adminPreLabels: Record<AdminSlotState, string> = {
  absent: "작년 필기 없음",
  none: "예습 링크 없음",
  ready: "Pre-Quiz 없음",
  done: "Pre-Quiz까지 있음",
};

const adminMainLabels: Record<AdminSlotState, string> = {
  absent: "올해 필기 없음",
  none: "올해 필기 없음",
  ready: "Main-Quiz 없음",
  done: "Main-Quiz까지 있음",
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
 * **여기까지가 모양의 문법이고, 무엇을 세는가는 보는 사람에 따라 갈린다**
 * (2026-09-02 관리자 지시). 학생에게는 「네가 열어 볼 것이 있는가 · 네가
 * 했는가」이고 관리자에게는 「내가 어디까지 올려 놨는가」다. 모양을 같이 쓰는
 * 것은 일부러다 — 관리자도 학생 화면을 매일 보는 같은 사람이라, 문법이 둘이면
 * 어느 쪽을 보고 있는지부터 헷갈린다.
 */
export function ChipSlots({ lecture, isAdmin }: { lecture: LectureRef; isAdmin: boolean }) {
  if (isAdmin) return <AdminChipSlots lecture={lecture} />;
  return <UserChipSlots lecture={lecture} />;
}

/**
 * 관리자가 보는 자리 둘. 세는 것은 `adminLectureSlots`에 적혀 있다.
 *
 * 관리자에게 자기 진도를 **주 단위로** 보여 주는 자리는 여기뿐이다 — `/admin`
 * 표는 편을 세로로 늘어놓아서 「이번 주가 통째로 비었다」가 안 보인다.
 *
 * **빈칸이 한 단계 는다.** 작년 필기가 없으면 관리자가 예습으로 할 수 있는 일이
 * 없으므로 점도 안 찍는다. 그래도 자리는 잡는다(`.chip-slot.is-absent`).
 *
 * 웹 예습 문항이 있는 칸의 동그라미는 관리자도 자신의 풀이 진행률을 본다.
 * 웹 문항이 없는 칸과 복습 네모는 자료 준비 상태를 표시한다.
 */
function AdminChipSlots({ lecture }: { lecture: LectureRef }) {
  const slots = adminLectureSlots(lecture);
  const progress = lecture.marks.prequiz && lecture.prequizProgress?.total
    ? lecture.prequizProgress : null;
  return (
    <span
      className="chip-slots"
      aria-label={`${progress ? `예습 ${progress.answered}/${progress.total}문항 완료` : `예습 ${adminPreLabels[slots.pre]}`} · 복습 ${adminMainLabels[slots.main]}`}
    >
      {progress ? <PreQuizMoon answered={progress.answered} total={progress.total} />
        : <i className={`chip-slot is-pre is-${slots.pre}`} />}
      <i className={`chip-slot is-main is-${slots.main}`} />
    </span>
  );
}

/**
 * 학생이 보는 자리 둘.
 *
 * 예습 달은 내 풀이 비율을 표시하고, 완료 뒤에도 파란색을 유지한다.
 */
function UserChipSlots({ lecture }: { lecture: LectureRef }) {
  const slots = lectureSlots(lecture);
  const progress = lecture.prequizProgress;
  const preLabel =
    lecture.marks.prequiz && progress && progress.total > 0
      ? `예습 ${progress.answered}/${progress.total}문항 완료`
      : `예습 ${stateLabels[slots.pre]}`;

  return (
    <span className="chip-slots" aria-label={`${preLabel} · 복습 ${stateLabels[slots.main]}`}>
      {slots.preFill !== null && progress ? <PreQuizMoon answered={progress.answered} total={progress.total} />
        : <i className={`chip-slot is-pre is-${slots.pre}`} />}
      <i className={`chip-slot is-main is-${slots.main}`} />
    </span>
  );
}

/** 왼쪽 초승달 → 반달 → 보름달. 밝은 면적이 완료 비율과 같다. */
function PreQuizMoon({ answered, total }: { answered: number; total: number }) {
  const fill = Math.max(0, Math.min(1, answered / total));
  const terminator = Math.abs(1 - 2 * fill) * 4.5;
  const path = `M 5 .5 A 4.5 4.5 0 0 0 5 9.5 A ${terminator} 4.5 0 0 ${fill <= .5 ? 1 : 0} 5 .5 Z`;
  return <svg className={`chip-slot is-pre is-moon is-${fill >= 1 ? "done" : "ready"}`}
    viewBox="0 0 10 10" aria-hidden="true">
    <title>Pre-Quiz {answered}/{total}문항 완료</title>
    <circle cx="5" cy="5" r="4.5" fill={fill >= 1 ? "currentColor" : "none"} stroke="currentColor" />
    {fill > 0 && fill < 1 ? <path d={path} fill="currentColor" /> : null}
  </svg>;
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
  isAdmin,
}: {
  entry: CalendarEntry;
  compact: boolean;
  onOpen: (entry: CalendarEntry) => void;
  active: boolean;
  /** 자리 둘이 무엇을 세는가가 이것으로 갈린다 — `ChipSlots` 주석을 보라. */
  isAdmin: boolean;
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
        <ChipSlots lecture={entry.lectures[0]} isAdmin={isAdmin} />
      ) : null}
    </button>
  );
}

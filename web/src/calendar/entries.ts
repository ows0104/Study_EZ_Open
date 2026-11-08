import type { LectureRef, TimetableEvent } from "../types/lectures";

export type CalendarMode = "week" | "month";

/** 캘린더 한 칸. 서버가 내려준 공식 시간표만 그린다. */
export type CalendarEntry = {
  id: string;
  title: string;
  date: string;
  startTime: string;
  endTime: string;
  /** 시간표의 세부 항목 — 실제 강의 제목이다. 있으면 이것을 크게 보여 준다. */
  detail: string;
  professor: string;
  category: TimetableEvent["category"];
  course: string;
  lectures: LectureRef[];
};

export const weekDayLabels = ["월", "화", "수", "목", "금"];
export const defaultHourSlots = [9, 10, 11, 13, 14, 15, 16];

const categoryLabels: Record<TimetableEvent["category"], string> = {
  lecture: "강의",
  practice: "실습",
  exam: "시험",
  holiday: "휴일",
  elective: "선택",
  study: "자율학습",
};

/** 패널 머리에 붙는 이름. 칸에서는 테두리로만 갈리던 것을 여기서는 말로 적는다. */
export function categoryLabel(category: TimetableEvent["category"]) {
  return categoryLabels[category] ?? category;
}

/**
 * 자리 하나의 세 단계.
 *
 * `none`은 아직 아무것도 안 올라온 것이고, 자리는 그래도 잡는다 — 도형이 생기고
 * 사라지는 대로 점이 좌우로 흔들리면 강의끼리 위치가 안 맞는다.
 */
export type SlotState = "none" | "ready" | "done";

/**
 * 칸에 서는 자리 둘. 왼쪽이 예습, 오른쪽이 복습이고 순서는 절대 안 바뀐다.
 *
 * **시점으로 가르지 않는다.** 전에는 강의 전에 예습 점을, 후에 복습 점을 그려서
 * 한 번에 최대 둘이었는데, 그러면 강의가 끝나는 순간 다 푼 예습의 흔적이
 * 사라졌다. 채운 점은 "할 일"이 아니라 "한 일"이라 지울 이유가 없다.
 */
export type Slots = {
  pre: SlotState;
  /**
   * 웹 예습퀴즈를 푼 비율(0~1). 잴 것이 없으면 `null`이고, 그때는 채움을 아예
   * 안 그린다 — 0%로 그리면 "안 풀었다"로 읽히는데 실은 풀 자리가 없는 것이다.
   */
  preFill: number | null;
  main: SlotState;
};

/** 웹 예습퀴즈를 끝까지 풀었는가. 잴 것이 없으면 "끝냈다"고 하지 않는다. */
export function prequizDone(lecture: LectureRef) {
  const progress = lecture.prequizProgress;
  return Boolean(progress && progress.total > 0 && progress.answered >= progress.total);
}

/**
 * 강의 하나 → 자리 둘.
 *
 * **퀴즈가 문이다**(2026-09-18 관리자 지시 — 「예습 퀴즈가 올라왔을 때만 동그라미,
 * 복습 퀴즈가 올라왔을 때만 네모」). 예습은 `marks.prequiz`, 복습은 `marks.quiz`
 * 하나씩만 본다.
 *
 * 전에는 예습을 예습 링크(`marks.preview`)로, 복습을 「올해 필기 또는 본덱」 OR로
 * 열었다. 그러면 도형이 「풀 것이 있다」가 아니라 「무언가 있다」가 되고, 도형을
 * 보고 누른 사람이 퀴즈 대신 필기를 만난다. 필기와 예습 링크가 사라지는 것은
 * 아니다 — 칸을 열면 패널에 그대로 있고, 자리 둘은 퀴즈만 센다.
 *
 * 웹 문항이 있으면 그 풀이 비율로 채운다. 파일을 받아 갔어도 웹 문항의
 * 진행률을 대신하지 않는다. 웹 문항이 없는 덱만 다운로드 기록을 사용한다.
 *
 * 관리자도 웹 문항이 있으면 자신의 예습 풀이 비율을 본다. 문항이 없는 칸은
 * `adminLectureSlots`의 자료 준비 상태를 유지한다.
 */
export function lectureSlots(lecture: LectureRef): Slots {
  const { marks, grabbed, prequizProgress: progress } = lecture;

  const preOpen = marks.prequiz;
  const hasProgress = Boolean(progress && progress.total > 0);
  const preDone = preOpen && (hasProgress ? prequizDone(lecture) : grabbed.pre);

  return {
    pre: preDone ? "done" : preOpen ? "ready" : "none",
    preFill: !preOpen || !progress || progress.total <= 0 ? null
      : Math.max(0, Math.min(1, progress.answered / progress.total)),
    // 옛 덱·필기를 받은 기록은 Quizbank 학습 완료를 뜻하지 않는다.
    main: marks.quiz || marks.mainQuiz ? "ready" : "none",
  };
}

/**
 * 아직 할 일이 남은 칸인가. 제목의 무게가 이것으로 갈린다.
 *
 * **`ready`만 참이다.** `none`은 관리자가 안 올린 것이고 `done`은 이미 한 것이다.
 * 둘 다 사용자가 지금 할 수 있는 일이 아니다.
 */
export function hasTodo(entry: CalendarEntry) {
  // 시험은 붙는 자료가 없어도 그 자체가 할 일이다. 자료로 판정하면 학기에서
  // 가장 중요한 칸이 가장 흐리게 나온다.
  if (entry.category === "exam") return true;

  return entry.lectures.some((lecture) => {
    const slots = lectureSlots(lecture);
    return slots.pre === "ready" || slots.main === "ready";
  });
}

export function startOfDay(value: Date) {
  return new Date(value.getFullYear(), value.getMonth(), value.getDate());
}

export function addDays(value: Date, amount: number) {
  const next = startOfDay(value);
  next.setDate(next.getDate() + amount);
  return next;
}

/**
 * 그 주의 월요일. 격자에 평일만 서므로 주의 시작은 곧 월요일이다.
 *
 * **일요일(0)은 다음 주로 보낸다.** 주는 일요일에 시작하고, 일요일에 하는 일은
 * 월요일 예습이다 — 지난 주로 돌리면 일요일에 캘린더를 열었을 때 정작 준비할
 * 주가 안 보인다.
 * 토요일(6)은 바로 전 금요일이 속한 주에 그대로 남는다.
 */
export function startOfWeek(value: Date) {
  const day = value.getDay();
  return addDays(value, day === 0 ? 1 : 1 - day);
}

export function toDateKey(value: Date) {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, "0");
  const day = String(value.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

export function formatWeekTitle(start: Date) {
  const end = addDays(start, 4);
  const head = `${start.getFullYear()}년 ${start.getMonth() + 1}월 ${start.getDate()}일`;
  return start.getFullYear() === end.getFullYear()
    ? `${head} ~ ${end.getMonth() + 1}월 ${end.getDate()}일`
    : `${head} ~ ${end.getFullYear()}년 ${end.getMonth() + 1}월 ${end.getDate()}일`;
}

/** CalendarGrid가 실제로 그리는 주 5일 또는 월간 6주의 범위. */
export function calendarRange(anchorDate: Date, mode: CalendarMode) {
  const start = mode === "week" ? startOfWeek(anchorDate)
    : startOfWeek(new Date(anchorDate.getFullYear(), anchorDate.getMonth(), 1));
  return { start: toDateKey(start), end: toDateKey(addDays(start, mode === "week" ? 4 : 39)) };
}

export function timeToMinutes(value: string) {
  const [hour, minute] = value.split(":").map(Number);
  return hour * 60 + minute;
}

/** 연강은 여러 줄을 차지한다. 끝 시각이 넘어서는 줄까지 센다. */
export function entryRowSpan(entry: CalendarEntry, hourSlots: number[], startIndex: number) {
  const endMinutes = timeToMinutes(entry.endTime);
  let span = 0;
  for (let index = startIndex; index < hourSlots.length; index += 1) {
    if (hourSlots[index] * 60 >= endMinutes) break;
    span += 1;
  }
  return Math.max(1, span);
}

/**
 * 시간표 이벤트를 캘린더 칸으로.
 *
 * `details`에서 담당 교수와 같은 줄을 빼고 남은 줄이 실제 강의 제목이다.
 * 시간표의 `title`은 "감염과 면역 12"처럼 과목과 회차라서 그것만으로는
 * 무슨 강의인지 알 수 없다.
 */
export function toCalendarEntries(events: TimetableEvent[]): CalendarEntry[] {
  return events
    .map((event) => {
      const normalizedProfessor = event.professor.replace(/[\s,.:()]/g, "");
      const detailLines = event.details
        .split("\n")
        .map((line) => line.trim())
        .filter((line) => {
          if (!line || line === event.professor.trim() || /^\([^)]*\)$/.test(line)) return false;
          const normalizedLine = line.replace(/[\s,.:()]/g, "");
          return !normalizedProfessor || normalizedLine.length < 2 || !normalizedProfessor.includes(normalizedLine);
        });
      return {
        id: event.id,
        title: event.title,
        date: event.date,
        startTime: event.startTime,
        endTime: event.endTime,
        detail: detailLines.join(" "),
        professor: event.professor,
        category: event.category,
        course: event.course,
        lectures: event.lectures,
      };
    })
    .sort(
      (left, right) =>
        left.date.localeCompare(right.date) ||
        left.startTime.localeCompare(right.startTime) ||
        left.title.localeCompare(right.title, "ko"),
    );
}

/** 열어 볼 것이 있는 칸인가. 시험과 휴일에는 붙일 자료가 없다. */
export function canOpen(entry: CalendarEntry) {
  return entry.lectures.length > 0;
}

/**
 * 자리 둘을 세울 칸인가.
 *
 * 강의 하나가 붙은 칸만이다. 시험·휴일·자율학습에는 붙을 자료가 없고, 한 교시에
 * 여럿이 열리는 선택형 과목도 같이 뺀다 — 셋을 한 자리로 접으면 "둘 중 하나만
 * 했다"가 사라지고, 셋을 다 세우면 자리가 여섯이 되어 칸에 안 들어간다. 그 칸은
 * 개수만 찍고 나머지는 패널로 넘긴다.
 */
export function hasSlots(entry: CalendarEntry) {
  return entry.lectures.length === 1;
}

/**
 * 관리자가 보는 자리 둘의 네 단계.
 *
 * **학생 쪽(`SlotState`)과 재는 것이 다르다.** 학생에게 `ready`는 「네가 열어 볼
 * 것이 있다」이고 `done`은 「네가 받아 갔거나 풀었다」다. 관리자에게는 그 둘 다
 * *자기가 무엇을 해 놓았는가*다 — 링크를 넣었는가, 덱을 만들었는가.
 *
 * `absent`가 하나 더 있다. 작년 필기가 아직 없는 강의는 관리자가 예습으로 할 수
 * 있는 일이 아무것도 없다 — 그 자리는 점도 안 찍고 비워 둔다.
 */
export type AdminSlotState = "absent" | "none" | "ready" | "done";

export type AdminSlots = {
  pre: AdminSlotState;
  main: AdminSlotState;
};

/**
 * 강의 하나 → 관리자 자리 둘 (2026-09-02 관리자 지시).
 *
 *   예습   작년 필기 없음         빈칸
 *          예습 링크 없음         점
 *          링크는 있고 Pre 덱 없음  빈 동그라미
 *          Pre 덱까지 있음         채운 동그라미
 *
 *   복습   올해 필기 없음         점
 *          필기는 있고 Main 덱 없음 빈 네모
 *          Main 덱까지 있음        채운 네모
 *
 * **닿은 것 중 가장 멀리 간 단계로 판정한다.** 사다리 순서대로 중첩해서 보면
 * 작년 필기가 없는 강의의 Pre 덱이 빈칸에 가려진다 — 이미 만들어 둔 것이 화면에서
 * 사라지는 쪽이 더 나쁘다. 순서대로 채운 흔한 경우에는 두 읽기가 같은 그림이다.
 */
export function adminLectureSlots(lecture: LectureRef): AdminSlots {
  const { marks } = lecture;
  return {
    pre: marks.prequiz ? "done" : marks.preview ? "ready" : marks.notesPrev ? "none" : "absent",
    main: marks.quiz || marks.mainQuiz ? "done" : marks.notesCurrent ? "ready" : "none",
  };
}

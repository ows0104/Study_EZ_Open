import type { LectureRef, TimetableEvent } from "../types";

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

export function startOfDay(value: Date) {
  return new Date(value.getFullYear(), value.getMonth(), value.getDate());
}

export function addDays(value: Date, amount: number) {
  const next = startOfDay(value);
  next.setDate(next.getDate() + amount);
  return next;
}

/** 주는 월요일에 시작한다. 일요일(0)은 지난 주로 돌린다. */
export function startOfWeek(value: Date) {
  const day = value.getDay();
  return addDays(value, day === 0 ? -6 : 1 - day);
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

import type { TimetableEvent } from "../types/lectures";
import { startOfWeek, studyDayKey, toDateKey } from "../calendar/entries";

const koreanDate = new Intl.DateTimeFormat("sv-SE", { timeZone: "Asia/Seoul" });
const MAX_GAP = 7 * 86_400_000;

/** 시간표 회차와 실습·시험 꼬리를 떼어 같은 블록으로 모은다. */
export function studyBlockName(value: string): string {
  let name = value.normalize("NFC").trim();
  while (name) {
    const next = name.replace(/[\s\-–—]*\d{1,3}\s*$/, "")
      .replace(/(?:\s*(?:실습시험|필기시험|실습|시험|평가|CBL\/TBL|PBL|CBL|TBL))+\s*$/gi, "").trim();
    if (!next || next === name) break;
    name = next;
  }
  return name;
}

export const studyBlockKey = (name: string) => studyBlockName(name).replace(/\s/g, "").toLowerCase();

/**
 * 1차·2차 시험 범위의 과목이 전혀 다른 과목은 1차 시험에서 블럭을 나눈다(2026-11-06 사용자 결정).
 * 일반 규칙(중간시험 뒤 수업이 남으면 블럭을 끝내지 않음)은 그대로 두고 여기 적은 과목만 예외다.
 */
const SPLIT_AT_FIRST_EXAM = new Set(["감염과면역"]);
const splitCache = new WeakMap<TimetableEvent[], Map<string, string>>();

type Named = Pick<TimetableEvent, "id" | "course" | "lectures" | "title">;

function baseName(event: Named) {
  return event.course || event.lectures[0]?.subject || event.title;
}

/** 나눌 과목의 수업마다 「과목 1차」·「과목 2차」 이름을 정한다. 1차 시험이 수업 사이에 없으면 나누지 않는다. */
function splitNames(events: TimetableEvent[]) {
  let names = splitCache.get(events);
  if (names) return names;
  names = new Map();
  const firstExams = events.filter(e => e.category === "exam" && /\(\s*1\s*차\s*\)|1차/.test(`${e.title} ${e.details}`));
  for (const key of SPLIT_AT_FIRST_EXAM) {
    const classes = events.filter(e => (e.category === "lecture" || e.category === "practice") && studyBlockKey(baseName(e)) === key);
    if (!classes.length) continue;
    const first = classes.reduce((a, b) => (a.date < b.date ? a : b)).date;
    const last = classes.reduce((a, b) => (a.date > b.date ? a : b)).date;
    const exam = firstExams.find(e => e.date > first && e.date < last);
    if (!exam) continue;
    const name = studyBlockName(baseName(classes[0]));
    for (const e of classes) names.set(e.id, `${name} ${e.date <= exam.date ? 1 : 2}차`);
  }
  splitCache.set(events, names);
  return names;
}

/** 블럭을 정할 때 쓰는 과목 이름. 나눈 과목이면 「감염과 면역 1차」처럼 차수가 붙는다. */
export function studyCourseOf(event: Named, events: TimetableEvent[]): string {
  return splitNames(events).get(event.id) ?? baseName(event);
}
const teaching = (event: TimetableEvent) => event.category === "lecture" || event.category === "practice";

/** 강의/퀴즈 첨부가 아직 없는 시간표도 블록 이름을 가진다. */
export function studyBlockNames(events: TimetableEvent[]): Map<string, string> {
  const names = new Map<string, string>();
  for (const event of events.filter(teaching)) {
    const name = studyBlockName(studyCourseOf(event, events));
    if (name && !names.has(studyBlockKey(name))) names.set(studyBlockKey(name), name);
  }
  return names;
}

function endTime(event: TimetableEvent): number {
  const end = /^\d{2}:\d{2}(?::\d{2})?$/.test(event.endTime) ? event.endTime : "23:59:59.999";
  return Date.parse(`${event.date}T${end}+09:00`);
}

type Block = {
  name: string; key: string; start: string; last: string;
  count: number; lastClassEnd: number; examEnd: number; end: number;
};

function blocksFrom(events: TimetableEvent[]): Block[] {
  const blocks: Block[] = [];
  const latest = new Map<string, Block>();
  const names = studyBlockNames(events);
  for (const event of events.filter(teaching).sort((a, b) => a.date.localeCompare(b.date))) {
    const key = studyBlockKey(studyCourseOf(event, events));
    const name = names.get(key);
    if (!name) continue;
    let block = latest.get(key);
    if (!block || Date.parse(event.date) - Date.parse(block.last) > MAX_GAP) {
      block = { name, key, start: event.date, last: event.date, count: 0, lastClassEnd: 0, examEnd: 0, end: 0 };
      latest.set(key, block);
      blocks.push(block);
    }
    block.last = event.date;
    block.lastClassEnd = Math.max(block.lastClassEnd, endTime(event));
    block.count += 1;
  }
  for (const exam of events.filter(event => event.category === "exam")) {
    const key = studyBlockKey(exam.course || exam.title);
    // 이름 없는 '시험'만 가까운 주 블록에 연결한다. 종합시험 등은 추정하지 않는다.
    const candidates = blocks.filter(block => (key === "시험" || block.key === key)
      && block.start <= exam.date && Date.parse(exam.date) - Date.parse(block.last) <= MAX_GAP);
    const block = dominant(candidates);
    if (block) block.examEnd = Math.max(block.examEnd, endTime(exam));
  }
  for (const block of blocks) {
    // 중간시험 뒤 수업이 남으면 그 시험으로 블록을 끝내지 않는다.
    block.end = block.examEnd >= block.lastClassEnd ? block.examEnd
      : Date.parse(`${block.last}T23:59:59.999+09:00`);
  }
  return blocks;
}

function dominant(blocks: Block[]): Block | undefined {
  return [...blocks].sort((a, b) => b.count - a.count || b.start.localeCompare(a.start)
    || a.name.localeCompare(b.name, "ko"))[0];
}

/** 시험 종료 후 다음 블록. 토요일은 이전 주, 일요일은 다음 월요일의 주다. */
export function currentStudyBlock(events: TimetableEvent[], now: Date = new Date()): string {
  const all = blocksFrom(events);
  const completed = all.filter(block => block.examEnd && block.end <= now.getTime())
    .filter(block => dominant(all.filter(other => other.start <= koreanDate.format(new Date(block.end))
      && other.end >= block.end)) === block)
    .sort((a, b) => b.end - a.end || b.count - a.count)[0];
  // 시험을 마친 주 블록에 겹쳐 있던 소수 강의가 다음 블록 자리를 차지하지 않는다.
  const blocks = completed ? all.filter(block => block !== completed
    && block.start >= koreanDate.format(new Date(completed.end))) : all;
  const today = studyDayKey(now);
  const day = new Date(`${today}T12:00:00`);
  const focusDay = day.getDay() === 0 ? toDateKey(startOfWeek(day)) : today;
  const ongoing = dominant(blocks.filter(block => block.start <= today && block.end > now.getTime()));
  // 일요일에 아직 끝나지 않은 이전 블록 시험이 있으면 종료를 먼저 기다린다.
  if (ongoing && ongoing.examEnd > now.getTime()) return ongoing.name;
  const current = dominant(blocks.filter(block => block.start <= focusDay && block.end > now.getTime()));
  if (current) return current.name;
  const upcoming = blocks.filter(block => block.start > focusDay)
    .sort((a, b) => a.start.localeCompare(b.start) || b.count - a.count);
  if (upcoming.length) return upcoming[0].name;
  // 학기 종료 후에는 마지막 블록을 계속 열 수 있다.
  return [...blocks, ...(completed ? [completed] : [])]
    .sort((a, b) => b.end - a.end || b.count - a.count)[0]?.name ?? "";
}

/** 같은 기본 블록에서 고른 전체 보기/다른 블록은 목록 갱신에도 유지한다. */
export function selectedStudyCourse(automatic: string, manual: { block: string; course: string } | null): string {
  return manual?.block === automatic ? manual.course : automatic;
}

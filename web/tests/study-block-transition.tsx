import { useState } from "react";
import { createRoot } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import { StudyOverview } from "../src/bank/StudyOverview";
import type { TimetableEvent } from "../src/types/lectures";

// A local, isolated browser fixture: no real account, API, quiz, or study records.
window.fetch = async () => new Response(JSON.stringify({ id: "block-test", isAdmin: false, isApproved: true }),
  { headers: { "Content-Type": "application/json" } });
const NativeDate = Date;
let clock = NativeDate.parse("2026-10-30T11:49:00+09:00");
class TestDate extends NativeDate {
  constructor(value: string | number = clock) { super(value); }
  static now() { return clock; }
}
window.Date = TestDate as DateConstructor;
const events: TimetableEvent[] = [
  ["이전 블록", "2026-10-29", "lecture", "10:00"],
  ["이전 블록", "2026-10-30", "lecture", "10:00"],
  ["이전 블록 시험", "2026-10-30", "exam", "11:50"],
  ["감염과 면역", "2026-11-02", "lecture", "10:00"],
  ["감염과 면역 TBL", "2026-11-03", "lecture", "10:00"],
  ["감염과 면역 시험", "2026-11-04", "exam", "16:00"],
  ["다음 블록", "2026-11-05", "lecture", "10:00"],
  ["다음 블록 시험", "2026-11-06", "exam", "16:00"],
  ["그다음 블록", "2026-11-09", "lecture", "10:00"],
].map(([course, date, category, endTime], i) => ({ id: String(i), course, date, category: category as TimetableEvent["category"],
  endTime, startTime: "09:00", title: course, details: "", professor: "", slot: null, lectures: [] }));

function Harness() {
  const [rows, setRows] = useState<TimetableEvent[]>([]);
  return <MemoryRouter><button id="refresh" onClick={() => setRows(events.map(e => ({ ...e })))}>목록 갱신</button>
    <StudyOverview events={rows} onStart={() => {}} /></MemoryRouter>;
}
createRoot(document.getElementById("root")!).render(<Harness />);
const pause = () => new Promise<void>(resolve => setTimeout(resolve, 10));
async function waitFor(condition: () => boolean, label: string) {
  for (let i = 0; i < 200; i++) { if (condition()) return; await pause(); }
  throw new Error(label);
}
const results: string[] = [];
// 강의 목록의 블럭 선택(2026-11 개편): 단추 + 목록. 지금 블럭은 단추의 data-block.
const picker = () => document.querySelector<HTMLButtonElement>(".block-picker-button");
async function change(name: string) {
  picker()!.click();
  await waitFor(() => !!document.querySelector(".block-menu"), "open block menu");
  const option = [...document.querySelectorAll<HTMLButtonElement>(".block-menu [role=option]")]
    .find(o => o.querySelector("b")?.firstChild?.textContent === name);
  if (!option) throw Error(`missing block option ${name}`);
  option.click();
}
async function check(course: string, label: string) {
  await waitFor(() => picker()?.dataset.block === course, label);
  results.push(label);
}
async function run() {
  await waitFor(() => !!picker(), "mount");
  await check("", "empty timetable");
  document.getElementById("refresh")!.click();
  await check("이전 블록", "late timetable arrival");
  await change("다음 블록");
  await check("다음 블록", "manual other-block view");
  document.getElementById("refresh")!.click();
  await pause();
  await check("다음 블록", "refresh preserves manual block");
  clock = NativeDate.parse("2026-10-30T11:50:00+09:00");
  window.dispatchEvent(new Event("focus"));
  await check("감염과 면역", "focus switches immediately after final exam");
  if (!picker()!.textContent?.includes("이번 블럭")) throw Error("missing current-block mark");
  if (!document.querySelector(".list-table")?.textContent?.includes("퀴즈 없음")) throw Error("missing pending class");
  await change("이전 블록");
  await check("이전 블록", "manual old-block review");
  document.getElementById("refresh")!.click();
  await pause();
  await check("이전 블록", "refresh preserves manual old block");
  clock = NativeDate.parse("2026-11-01T00:00:00+09:00");
  document.dispatchEvent(new Event("visibilitychange"));
  await pause();
  await check("이전 블록", "same automatic block preserves manual choice on Sunday");
  clock = NativeDate.parse("2026-11-04T16:00:00+09:00");
  await new Promise<void>(resolve => setTimeout(resolve, 60_100));
  await check("다음 블록", "open page switches on its periodic clock without interaction");
  await change("이전 블록");
  await check("이전 블록", "manual choice after an automatic transition");
  clock = NativeDate.parse("2026-11-06T16:00:00+09:00");
  document.dispatchEvent(new Event("visibilitychange"));
  await check("그다음 블록", "visibility return switches to next automatic block");
  const result = document.getElementById("result")!;
  result.dataset.status = "passed";
  result.textContent = JSON.stringify(results);
}
run().catch(error => {
  const result = document.getElementById("result")!;
  result.dataset.status = "failed";
  result.textContent = String(error);
});

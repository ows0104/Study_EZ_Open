import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import { CalendarPage } from "../src/calendar/CalendarPage";
import { startFirstScreen } from "../src/firstScreen";
import type { TimetableEvent } from "../src/types/lectures";
import "../src/styles/base.css";
import "../src/styles/calendar.css";

const options = new URLSearchParams(location.search);
const requests: string[] = [];
const releases: (() => void)[] = [];
let learningRequests = 0;
Object.assign(window, { calendarTest: { requests, release: () => releases.shift()?.() } });
const events: TimetableEvent[] = ["2026-10-16", "2026-10-19"].map((date, i) => ({
  id: `event-${i}`, title: `시간표 강의 ${i}`, details: `시간표 강의 ${i}`, date,
  startTime: "09:00", endTime: "10:00", professor: "교수", category: "lecture", course: "과목", slot: 1,
  lectures: [{ subject: "subject", runId: `run-${i}`, title: `시간표 강의 ${i}`, professors: [], studyLoaded: false,
    marks: { notesPrev: false, preview: false, prequiz: false, notesCurrent: false, quiz: true },
    grabbed: { pre: false, main: false }, prequizProgress: null, mastery: null, cardProgress: null }],
}));
window.fetch = async (input, init) => {
  const url = new URL(String(input), location.origin);
  requests.push(url.pathname + url.search);
  let result: object;
  if (url.pathname === "/api/me") result = { id: "calendar-test", isAdmin: !options.has("student"), isApproved: true };
  else if (url.pathname === "/api/timetable") {
    if (url.searchParams.get("include_study") === "false") result = { events };
    else {
      learningRequests++;
      if (options.has("learningFail") && learningRequests === 1)
        return new Response(JSON.stringify({ detail: "학습률 조회 실패" }), { status: 500 });
      await new Promise<void>((resolve, reject) => {
        releases.push(resolve);
        init?.signal?.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")), { once: true });
      });
      result = { events: events.filter(e => e.date >= url.searchParams.get("start")! && e.date <= url.searchParams.get("end")!)
        .map(e => ({ ...e, lectures: e.lectures.map(l => ({ ...l, studyLoaded: true,
          marks: { ...l.marks, prequiz: true }, prequizProgress: { total: 4, answered: 2 },
          mastery: { score: 50, status: "needs_review", scope: "core", conceptCount: 1,
            masteredConcepts: 0, weakConcepts: 1, assessedDirections: 1, totalDirections: 1, weakest: [] },
        })) })) };
    }
  } else if (url.pathname === "/api/bundles/decks") result = { decks: [] };
  else if (url.pathname === "/api/lectures/subject/run-0") result = {
    subject: "subject", runId: "run-0", uid: "one", date: "2026-10-16", slot: 1, slotEnd: 1,
    startTime: "09:00", title: "시간표 강의 0", professors: [], author: "", version: null, course: "과목",
    files: [], preview: null, myPreview: null, myReview: null, prequiz: null, mainquiz: null,
    bank: null, bankSources: [], mastery: null,
  };
  else if (url.pathname.endsWith("/prequiz-job") || url.pathname.endsWith("/deck-job")) result = { job: null, runner: null };
  else throw new Error(`Unexpected API ${url.pathname}`);
  return new Response(JSON.stringify(result), { headers: { "Content-Type": "application/json" } });
};
// 실제 앱처럼 me와 가벼운 시간표만 미리 띄운다.
startFirstScreen(true);
createRoot(document.getElementById("root")!).render(<StrictMode><MemoryRouter initialEntries={["/?date=2026-10-16"]}>
  <main style={{ padding: 16 }}><CalendarPage /></main>
</MemoryRouter></StrictMode>);

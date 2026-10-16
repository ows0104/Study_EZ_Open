import { createRoot } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import { getMe } from "../src/firstScreen";
import type { TimetableEvent } from "../src/types/lectures";
import "../src/styles/base.css";

const options = new URLSearchParams(location.search);
const deleted = new Set<string>();
let hidden: string[] = JSON.parse(localStorage.getItem("test-hidden") ?? "[]");
const requests: string[] = [];
const progressRequests: { subject: string; runId: string }[][] = [];
const releases: (() => void)[] = [];
Object.assign(window, { studyTest: { requests, progressRequests, release: () => releases.shift()?.() } });
const events = (): TimetableEvent[] => ["약력학", "약물대사", "예정 강의"].map((title, i) => ({
  id: String(i), title, date: `2026-10-0${i + 1}`, startTime: "09:00", endTime: "10:00",
  details: title, professor: "", category: "lecture", course: "약리학", slot: i + 1,
  lectures: i === 2 && !options.has("linked") ? [] : [{ title, subject: "약리학", runId: String(i), professors: [],
    grabbed: { pre: false, main: false }, prequizProgress: null,
    marks: { notesPrev: false, preview: false, prequiz: false, notesCurrent: true, quiz: !deleted.has(String(i)) },
    bankTimeline: deleted.has(String(i)) ? null : { builtAt: "2026-10-16T00:00:00Z", deleteVersion: options.has("student") ? undefined : `v${i}` },
    cardProgress: deleted.has(String(i)) ? null : { total: 100, seen: 80, unseen: 20, recognized: 15, retrieving: 40, retained: 25, newRemaining: 23, reviewDue: 12, suspended: 2 },
  }],
}));
const lazyEvents = (): TimetableEvent[] => [
  { ...events()[0], lectures: Array.from({ length: 10 }, (_, i) => ({ ...events()[0].lectures[0], runId: String(i), title: `강의 ${i}` })) },
  { ...events()[0], id: "other", date: "2026-09-01", course: "다른 블록",
    lectures: [{ ...events()[0].lectures[0], subject: "다른 과목", runId: "other", title: "다른 강의" }] },
];
window.fetch = async (input, init) => {
  const url = new URL(String(input), location.origin);
  const path = decodeURIComponent(url.pathname);
  let result: object;
  if (path === "/api/me") result = { id: "management-test", isAdmin: !options.has("student"), isApproved: true };
  else if (path === "/api/timetable") {
    const rows = options.has("lazy") ? lazyEvents() : events();
    result = { events: url.searchParams.get("include_study") === "false"
      ? rows.map(e => ({ ...e, lectures: e.lectures.map(l => ({ ...l, studyLoaded: false, mastery: null,
        cardProgress: null })) })) : rows };
  } else if (path === "/api/timetable/study-progress") {
    const lectures = JSON.parse(String(init?.body)).lectures as { subject: string; runId: string }[];
    progressRequests.push(lectures);
    if (options.has("progressError") && progressRequests.length === 1)
      return new Response(JSON.stringify({ detail: "학습 현황 조회 실패" }), { status: 500 });
    if (options.has("lazy")) await new Promise<void>((resolve, reject) => {
      releases.push(resolve);
      init?.signal?.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")), { once: true });
    });
    result = { lectures: lectures.map(key => {
      const l = (options.has("lazy") ? lazyEvents() : events()).flatMap(e => e.lectures)
        .find(l => l.subject === key.subject && l.runId === key.runId);
      return { ...key, ready: l?.marks.quiz ?? false, mastery: l?.mastery, cardProgress: l?.cardProgress };
    }) };
  }
  else if (path === "/api/me/study-hidden") {
    if (init?.method === "PATCH") {
      const payload = JSON.parse(String(init.body));
      if (options.has("hideError")) return new Response(JSON.stringify({ detail: "숨김 저장 실패" }), { status: 500 });
      hidden = payload.hidden ? [...new Set([...hidden, ...payload.keys])] : hidden.filter(k => !payload.keys.includes(k));
      localStorage.setItem("test-hidden", JSON.stringify(hidden));
    }
    result = { keys: hidden };
  } else if (path.endsWith("/bank") && init?.method === "DELETE") {
    const run = path.split("/").at(-2)!;
    requests.push(run);
    if (options.has("fail") && run === "1") return new Response(JSON.stringify({ detail: "생성 작업이 진행 중입니다." }), { status: 409 });
    deleted.add(run); result = { deleted: true, archiveId: requests.length };
  } else throw new Error(`Unexpected API ${path}`);
  return new Response(JSON.stringify(result), { headers: { "Content-Type": "application/json" } });
};
if (options.has("lazy")) history.replaceState(null, "", "/study");
await getMe();
const { BankBatchPage } = await import("../src/bank/BankBatch");
createRoot(document.getElementById("root")!).render(<MemoryRouter><main style={{ padding: 16 }}><BankBatchPage /></main></MemoryRouter>);

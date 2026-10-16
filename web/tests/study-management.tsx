import { createRoot } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import { getMe } from "../src/firstScreen";
import type { TimetableEvent } from "../src/types/lectures";
import "../src/styles/base.css";

const options = new URLSearchParams(location.search);
const deleted = new Set<string>();
let hidden: string[] = JSON.parse(localStorage.getItem("test-hidden") ?? "[]");
const requests: string[] = [];
Object.assign(window, { studyTest: { requests } });
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
window.fetch = async (input, init) => {
  const url = new URL(String(input), location.origin);
  const path = decodeURIComponent(url.pathname);
  let result: object;
  if (path === "/api/me") result = { id: "management-test", isAdmin: !options.has("student"), isApproved: true };
  else if (path === "/api/timetable") result = { events: events() };
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
await getMe();
const { BankBatchPage } = await import("../src/bank/BankBatch");
createRoot(document.getElementById("root")!).render(<MemoryRouter><main style={{ padding: 16 }}><BankBatchPage /></main></MemoryRouter>);

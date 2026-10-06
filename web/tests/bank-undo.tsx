// Local-only API fixture: exercises the real start, solve, waiting and completion screens.
import React from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Link, MemoryRouter, Route, Routes } from "react-router-dom";
import { StudyNav } from "../src/StudyNav";
import { CalendarPage } from "../src/calendar/CalendarPage";
import "../src/styles/base.css";
import "../src/styles/calendar.css";

const navigation = new URLSearchParams(location.search).has("navigation");
let active = !navigation, revealed = false, index = 0, serial = 1, requests = 0;
let token = "token-1";
const history: { index: number; token: string; rating: string }[] = [];
const waiting = new URLSearchParams(location.search).has("waiting");
const session = () => ({ session_id: "session-1", status: active ? "active" : "complete", reason: null,
  size: null, reviewed: history.length, ratings: { Again: 0, Hard: 0, Good: history.length, Easy: 0 },
  core_before: 0, core_after: history.length / 10, improved: [], weaknesses: [], started_at: Date.now(), ended_at: null });
const goal = () => ({ title: "되돌리기 예시", dayStart: 0, scope: "core", total: 2,
  completed: history.length, remaining: 2 - history.length, newRemaining: 2 - history.length,
  reviewRemaining: 0, relearningRemaining: 0, waiting: 0, retryAt: null,
  met: index === 2, progressPercent: history.length * 50, reviewedToday: history.length,
  firstPassSeen: history.length, firstPassTotal: 2 });
const answer = { answer: "예시 정답", answerUnits: ["예시 정답"], correctOptionIds: [], answerPairs: [], correctOrder: [], slides: [], medicalReview: null, conflict: "", external: false };
const next = () => ({ question: { question_id: `Q${index + 1}`, concept_id: "C1", tier: "Core", importance: 5,
  format: "basic", retrieval_direction: "direct", question: `예시 문제 ${index + 1}`, source_refs: [],
  conflict_id: "", options: [], matching_left: [], matching_right: [], sequence_items: [] },
  reviewToken: token, undoToken: history.at(-1)?.token ?? null, answer: revealed ? answer : null,
  session: session(), examDate: "2026-10-20", lectureGoal: goal(), preloadSlides: [] });
window.fetch = async (input, init) => {
  const path = new URL(String(input), location.origin).pathname;
  const body = init?.body ? JSON.parse(String(init.body)) : {};
  let result: object;
  if (path === "/api/me") result = { isAdmin: false, isApproved: true, email: "preview@example.com" };
  else if (path === "/api/bundles/decks") result = { decks: [] };
  else if (path === "/api/timetable") result = { events: [{
    id: "demo-event", date: "2026-10-07", startTime: "09:00", endTime: "10:00", title: "약동학", details: "", professor: "담당 교수",
    category: "lecture", course: "약리학", slot: 1, lectures: [{ subject: "local", runId: "demo", title: "약동학", professors: [],
      marks: { notesPrev: false, preview: false, prequiz: false, notesCurrent: true, quiz: true }, grabbed: { pre: false, main: false } }],
  }] };
  else if (path.endsWith("/lectures/local/demo")) result = {
    subject: "local", runId: "demo", title: "약동학", date: "2026-10-07", subjectLabel: "약리학", professors: [], files: [],
    preview: null, myPreview: null, myReview: null, prequiz: null, mainquiz: null,
    bank: { status: "ready", usable: true, open: true, questionCount: 2, conceptCount: 1 },
  };
  else if (path.endsWith("/session/start")) { active = true; result = session(); }
  else if (path.endsWith("/session/end")) { active = false; result = session(); }
  else if (path.endsWith("/undo")) {
    await new Promise(resolve => setTimeout(resolve, 150));
    if (body.reviewToken !== history.at(-1)?.token) return new Response(JSON.stringify({ detail: "stale token" }), { status: 409 });
    const last = history.pop()!;
    index = last.index; token = `token-${++serial}`; revealed = true; active = true;
    document.getElementById("requests")!.textContent = String(++requests);
    result = next();
  } else if (path.endsWith("/next")) {
    if (index === 2) { active = false; result = { question: null, summary: session(), undoToken: history.at(-1)?.token }; }
    else if (waiting && index === 1 && !revealed) result = { question: null, waiting: true, session: session(), lectureGoal: goal(), undoToken: history.at(-1)?.token };
    else result = next();
  } else if (path.endsWith("/reveal")) { revealed = true; result = answer; }
  else if (path.endsWith("/rate")) {
    history.push({ index, token, rating: body.rating }); index++; token = `token-${++serial}`; revealed = false;
    result = { session: session() };
  } else if (path.endsWith("/bank")) result = { summary: { usable: true, questionCount: 2, conceptCount: 1 },
    session: session(), previousSessions: [], conceptMap: [], sizes: [10], examDate: "2026-10-20", lectureGoal: goal(), undoToken: history.at(-1)?.token };
  else throw new Error(`Unexpected API: ${path}`);
  return new Response(JSON.stringify(result), { headers: { "Content-Type": "application/json" } });
};
const { BankStudyPage } = await import("../src/bank/BankStudy");
const root = createRoot(document.getElementById("root")!);
if (navigation) root.render(<BrowserRouter><StudyNav /><Routes>
  <Route path="/mainquiz/:subject/:runId" element={<BankStudyPage />} />
  <Route path="/mastery" element={<p>학습도 확인 <Link to="/">캘린더</Link></p>} />
  <Route path="*" element={<CalendarPage />} />
</Routes></BrowserRouter>);
else root.render(
  <MemoryRouter initialEntries={["/mainquiz/local/demo"]}><Routes>
    <Route path="/mainquiz/:subject/:runId" element={<BankStudyPage />} />
  </Routes></MemoryRouter>,
);

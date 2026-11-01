// Real completion/start/solve flow, with a timetable prefetched before studying.
import { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { startFirstScreen, takeTimetable } from "../src/firstScreen";
import "../src/styles/base.css";
let active = false, reviewed = 0, seen = 2, starts = 0, revealed = false;
const session = () => ({ session_id: "extra-session", status: active ? "active" : "complete",
  reason: active ? null : "lecture_goal_met", size: null, reviewed,
  ratings: { Again: 0, Hard: 0, Good: reviewed, Easy: 0 }, core_before: .5, core_after: .5,
  improved: [], weaknesses: [], started_at: Date.now(), ended_at: null });
const goal = { title: "약동학(1)", dayStart: 0, scope: "core", total: 2, completed: 2, remaining: 0,
  newRemaining: 0, reviewRemaining: 0, relearningRemaining: 0, waiting: 0, retryAt: null,
  met: true, progressPercent: 100, reviewedToday: 2, firstPassSeen: 2, firstPassTotal: 2 };
const answer = { answer: "정답", answerUnits: ["정답"], correctOptionIds: [], answerPairs: [],
  correctOrder: [], slides: [], medicalReview: null, conflict: "", external: false };
window.fetch = async (input, init) => {
  const path = new URL(String(input), location.origin).pathname;
  const body = init?.body ? JSON.parse(String(init.body)) : {};
  let result: object;
  if (path === "/api/me") result = { isAdmin: false, isApproved: true };
  else if (path === "/api/timetable") result = { events: [{ seen }] };
  else if (path.endsWith("/session/start")) {
    if (!body.continueAfterGoal || body.size !== null) throw new Error("Additional study must bypass the daily goal without a question cap");
    starts++; active = true; reviewed = 0; revealed = false;
    await new Promise(resolve => setTimeout(resolve, 200));
    result = session();
  } else if (path.endsWith("/next")) {
    if (reviewed > 0) { active = false; result = { question: null, summary: session() }; }
    else { seen = 3; result = { question: { question_id: "Q3", concept_id: "C1", tier: "Core", importance: 5,
      format: "basic", retrieval_direction: "direct", question: "추가 학습 문제", source_refs: [],
      conflict_id: "", options: [], matching_left: [], matching_right: [], sequence_items: [] },
      reviewToken: "extra-token", session: session(), lectureGoal: goal, preloadSlides: [],
      answer: revealed ? answer : null }; }
  } else if (path.endsWith("/prepare")) result = answer;
  else if (path.endsWith("/reveal")) { revealed = true; result = answer; }
  else if (path.endsWith("/rate")) { reviewed++; result = { session: session() }; }
  else if (path.endsWith("/bank")) result = { summary: { usable: true, studyQuestionCount: 3, seenQuestionCount: seen },
    session: session(), previousSessions: [], conceptMap: [], sizes: [10], lectureGoal: goal, undoToken: null };
  else throw new Error(`Unexpected API: ${path}`);
  document.body.dataset.starts = String(starts);
  return new Response(JSON.stringify(result), { headers: { "Content-Type": "application/json" } });
};
function CalendarResult() {
  const [count, setCount] = useState<number | null>(null);
  useEffect(() => { takeTimetable().then(data => setCount((data.events[0] as unknown as { seen: number }).seen)); }, []);
  return <p>Main 캘린더 · <span id="seen">{count}</span>/3문항 봄</p>;
}
startFirstScreen(true);
const { BankStudyPage } = await import("../src/bank/BankStudy");
createRoot(document.getElementById("root")!).render(<MemoryRouter initialEntries={["/mainquiz/local/demo"]}><Routes>
  <Route path="/mainquiz/:subject/:runId" element={<BankStudyPage />} />
  <Route path="/" element={<CalendarResult />} />
</Routes></MemoryRouter>);

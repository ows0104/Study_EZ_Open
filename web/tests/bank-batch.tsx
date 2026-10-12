import { createRoot } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import { getMe } from "../src/firstScreen";
import "../src/styles/base.css";
const counts: Record<string, number> = {};
const active: Record<string, boolean> = {};
const starts: string[] = [];
let finishedReason = "lecture_goal_met";
const session = (id: string) => ({ session_id: id, status: active[id] ? "active" : "complete",
  reason: active[id] ? null : finishedReason, size: null, reviewed: counts[id] ?? 0,
  ratings: { Again: 0, Hard: 0, Good: counts[id] ?? 0, Easy: 0 }, core_before: 0, core_after: .5,
  improved: [], weaknesses: [], started_at: Date.now(), ended_at: null });
const answer = { answer: "정답", answerUnits: ["정답"], correctOptionIds: [], answerPairs: [], correctOrder: [], slides: [], medicalReview: null };
window.fetch = async (input, init) => {
  const path = new URL(String(input), location.origin).pathname;
  const id = path.split("/")[4];
  let result: object;
  if (path === "/api/me") result = { id: "batch-test", isAdmin: true, isApproved: true };
  else if (path === "/api/timetable") result = { events: ["done", "first", "second"].map((runId, index) => ({
    date: `2026-10-${10 + index}`, lectures: [{ subject: "test", runId, title: `${index + 1}강의`, marks: { quiz: true } }],
  })) };
  else if (path.endsWith("/audit")) result = { jobId: id };
  else if (path.endsWith("/session/start")) {
    const body = JSON.parse(String(init?.body));
    if (body.size !== null || body.continueAfterGoal) throw new Error("Batch must use ordinary uncapped daily study");
    active[id] = true; starts.push(id); result = session(id);
  } else if (path.endsWith("/session/end")) { active[id] = false; finishedReason = "user_finished"; result = session(id); }
  else if (path.endsWith("/next")) {
    if ((counts[id] ?? 0) >= 2) { active[id] = false; finishedReason = "lecture_goal_met"; result = { question: null, summary: session(id) }; }
    else result = { question: { question_id: `${id}-${counts[id] ?? 0}`, concept_id: "C1", tier: "Core", importance: 5,
      format: "basic", retrieval_direction: "direct", question: `${id} 새 카드 ${(counts[id] ?? 0) + 1}`,
      source_refs: [], conflict_id: "", options: [], matching_left: [], matching_right: [], sequence_items: [] },
      reviewToken: `${id}-token`, session: session(id), preloadSlides: [] };
  } else if (path.endsWith("/prepare") || path.endsWith("/reveal")) result = answer;
  else if (path.endsWith("/rate")) { counts[id] = (counts[id] ?? 0) + 1; result = {}; }
  else if (path.endsWith("/bank")) result = { summary: { usable: true }, session: active[id] ? session(id) : null,
    lectureGoal: { met: id === "done" || (counts[id] ?? 0) >= 2 } };
  else throw new Error(`Unexpected API ${path}`);
  document.body.dataset.starts = starts.join(",");
  document.body.dataset.ratings = JSON.stringify(counts);
  return new Response(JSON.stringify(result), { headers: { "Content-Type": "application/json" } });
};
await getMe();
const { BankBatchPage } = await import("../src/bank/BankBatch");
createRoot(document.getElementById("root")!).render(<MemoryRouter><BankBatchPage /></MemoryRouter>);

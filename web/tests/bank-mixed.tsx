import { createRoot } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import { getMe } from "../src/firstScreen";
import "../src/styles/base.css";
type Saved = { counts: Record<string, number>; served: string | null; shown: Record<string, boolean>; revealed: Record<string, boolean>; history: string[] };
const saved: Saved = JSON.parse(sessionStorage.getItem("mixed-fixture") ?? '{"counts":{"first":0,"second":0},"served":null,"shown":{},"revealed":{},"history":[]}');
const options = [{ id: "A", text: "alpha" }, { id: "B", text: "beta" }];
const answer = { answer: "alpha", answerUnits: ["A: 조건 충족", "B: 조건 불충족"], correctOptionIds: ["A"], answerPairs: [], correctOrder: [], slides: [], medicalReview: null };
const session = (run: string) => ({ session_id: run, status: "active", reason: null, size: null, reviewed: saved.counts[run],
  ratings: { Again: saved.counts[run], Hard: 0, Good: 0, Easy: 0 }, core_before: 0, core_after: 0,
  improved: [], weaknesses: [], started_at: Date.now(), ended_at: null });
const goal = () => { const completed = Object.values(saved.counts).reduce((a, b) => a + b, 0); return {
  title: "선택한 2강의", dayStart: 0, scope: "all", total: 4, completed, remaining: 4 - completed,
  newRemaining: 4 - completed, reviewRemaining: 0, unlearnedRemaining: 4 - completed, relearningRemaining: 0, waiting: 0,
  retryAt: null, met: completed === 4, progressPercent: completed * 25, reviewedToday: completed, firstPassSeen: completed, firstPassTotal: 4 }; };
const reply = (run: string | null) => {
  if (!run) return { question: null, summary: null, batchGoal: goal(), undoToken: null };
  const qid = `${run}-${saved.counts[run]}`;
  const recall = run === "first" && saved.counts[run] === 0;
  return { question: { question_id: qid, concept_id: "C1", tier: "Core", importance: 5, format: "mcq", retrieval_direction: "direct",
      mcq_mode: recall ? "recall_first" : "comparison", question: recall ? "기전 X를 담당하는 항목은?" : `${run} · 두 항목 중 조건에 더 맞는 것은?`,
      source_refs: [], conflict_id: "", options: !recall || saved.shown[qid] || saved.revealed[qid] ? options : [],
      matching_left: [], matching_right: [], sequence_items: [] },
    lecture: { subject: "test", runId: run, title: run === "first" ? "기전 강의" : "비교 강의" }, reviewToken: qid,
    choicesShown: !recall || Boolean(saved.shown[qid]), batchGoal: goal(), session: session(run), preloadSlides: [],
    answer: saved.revealed[qid] ? answer : null, undoToken: null };
};
window.fetch = async (input, init) => {
  const path = new URL(String(input), location.origin).pathname;
  const body = init?.body ? JSON.parse(String(init.body)) : {};
  const run = path.split("/")[4];
  let result: object;
  if (path === "/api/me") result = { id: "mixed-test", isAdmin: false, isApproved: true };
  else if (path === "/api/timetable") result = { events: ["first", "second"].map((runId, i) => ({ date: `2026-10-${10 + i}`,
    lectures: [{ subject: "test", runId, title: runId === "first" ? "기전 강의" : "비교 강의", marks: { quiz: true } }] })) };
  else if (path === "/api/bank/batch/next") {
    if (!saved.served) {
      const eligible = Object.keys(saved.counts).filter(r => saved.counts[r] < 2);
      saved.served = eligible.find(r => r !== body.resumeLecture?.runId) ?? eligible[0] ?? null;
    }
    result = reply(saved.served);
  } else if (path === "/api/bank/batch/session/end") { saved.served = null; result = { batchGoal: goal() }; }
  else if (path.endsWith("/options")) { saved.shown[body.reviewToken] = true; result = { question: reply(run).question, choicesShown: true }; }
  else if (path.endsWith("/prepare")) result = answer;
  else if (path.endsWith("/reveal")) { saved.revealed[body.reviewToken] = true; result = answer; }
  else if (path.endsWith("/rate")) {
    if (!saved.revealed[body.reviewToken]) throw new Error("Rating requires reveal");
    saved.history.push(run); saved.counts[run]++; saved.served = null; result = {};
  } else if (path.endsWith("/bank")) result = { summary: { usable: true }, conceptMap: [], session: session(run) };
  else throw new Error(`Unexpected API ${path}`);
  sessionStorage.setItem("mixed-fixture", JSON.stringify(saved));
  document.body.dataset.sequence = saved.history.join(",");
  return new Response(JSON.stringify(result), { headers: { "Content-Type": "application/json" } });
};
await getMe();
const { BankBatchPage } = await import("../src/bank/BankBatch");
createRoot(document.getElementById("root")!).render(<MemoryRouter><BankBatchPage /></MemoryRouter>);

import { useState } from "react";
import { createRoot } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import { PersonalQuestions } from "../src/bank/PersonalQuestions";
import { BankSolve } from "../src/bank/BankSolve";
import type { BankRead, BankTier } from "../src/types/bank";
import "../src/styles/base.css";

const base = "/api/lectures/test/demo/bank";
let added: { question: string; answer: string; explanation: string; tier: BankTier } | null = null;
const calls: { path: string; body: Record<string, unknown>; method: string }[] = [];
const state = { calls, failAdd: false };
Object.assign(window, { personalTest: state });
const answer = () => ({ answer: added?.answer ?? "기존 답", explanation: added?.explanation ?? "", answerUnits: [],
  correctOptionIds: [], answerPairs: [], correctOrder: [], slides: [], medicalReview: null });
const info = () => ({ personalQuestions: added ? [{ questionId: "PQ_1", question: added.question, tier: added.tier }] : [] } as unknown as BankRead);
window.fetch = async (input, init) => {
  const path = new URL(String(input), location.origin).pathname;
  const body = init?.body ? JSON.parse(String(init.body)) : {};
  const method = init?.method ?? "GET";
  calls.push({ path, body, method });
  let result: unknown;
  if (path === "/api/me") result = { isAdmin: false, isApproved: true, id: "test" };
  else if (path.endsWith("/personal-question-slides")) result = {
    slides: [{ assetId: "slide-3", page: 3, sourceId: "self", url: "data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' width='200' height='100'><text x='20' y='40'>3</text></svg>" },
      { assetId: "slide-7", page: 7, sourceId: "self", url: "data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' width='200' height='100'><text x='20' y='40'>7</text></svg>" }],
    selectedAssetIds: new URL(String(input), location.origin).searchParams.has("sourceQuestionId") ? ["slide-3"] : [],
  };
  else if (path.endsWith("/personal-questions") && method === "POST") {
    if (state.failAdd) return new Response(JSON.stringify({ detail: "추가 실패 테스트" }), { status: 500 });
    added = body; result = { questionId: "PQ_1" };
  } else if (path.endsWith("/personal-questions/PQ_1")) { added = null; result = { deleted: true }; }
  else if (path.endsWith("/personal") && method === "GET") result = {
    original: added, draft: added, personalAdded: true, edited: true, comment: "", revision: "a".repeat(64),
  };
  else if (path.endsWith("/personal") && method === "PUT") {
    added = { ...added!, ...body }; result = { question: {}, answer: answer(), reported: false };
  } else if (path.endsWith("/next")) result = { question: { question_id: "Q1", question: "기존 문제", format: "basic", tier: "Essential",
    retrieval_direction: "direct", options: [], conflict_id: "", matching_left: [], matching_right: [], sequence_items: [], targetMastery: .9 },
    reviewToken: "token", preloadSlides: [] };
  else if (path.endsWith("/prepare")) result = answer();
  else if (path === base) result = info();
  else throw new Error(`Unexpected ${method} ${path}`);
  return new Response(JSON.stringify(result), { headers: { "Content-Type": "application/json" } });
};
function Fixture() {
  const [value, setValue] = useState(info());
  return <main style={{ maxWidth: 800, margin: "auto", padding: 16 }}><h1>내 문제</h1>
    <PersonalQuestions base={base} info={value} onChanged={() => setValue(info())} /></main>;
}
createRoot(document.getElementById("root")!).render(<MemoryRouter>
  {location.search.includes("solve") ? <BankSolve base={base} lecture={{ subject: "test", runId: "demo" }} onFinished={() => {}} /> : <Fixture />}
</MemoryRouter>);

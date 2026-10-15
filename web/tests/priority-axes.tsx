import { createRoot } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import { getMe } from "../src/firstScreen";
import "../src/styles/base.css";

const query = new URLSearchParams(location.search);
const tier = query.get("tier") ?? "Important";
const advanced = query.get("advanced") !== "false";
const question = { question_id: "axes", concept_id: "C1", tier, advanced,
  importance: tier === "Core" ? 5 : tier === "Important" ? 4 : 2,
  format: "basic", retrieval_direction: "integration", mcq_mode: "none",
  question: "두 조건을 함께 적용하면 선택되는 경로는?", options: [], matching_left: [], matching_right: [],
  sequence_items: [], source_refs: [], conflict_id: "" };
const answer = { answer: "경로 A", answerUnits: ["경로 A"], explanation: "두 조건을 모두 만족하는 경로를 선택합니다.",
  correctOptionIds: [], answerPairs: [], correctOrder: [], slides: [], medicalReview: null };
window.fetch = async (input) => {
  const path = new URL(String(input), location.origin).pathname;
  const result = path === "/api/me" ? { id: "axes-test", isAdmin: true, isApproved: true }
    : path.endsWith("/prepare") || path.endsWith("/reveal") ? answer
    : { question, reviewToken: "axes-token", undoToken: null, choicesShown: true, preloadSlides: [],
        session: { status: "active", size: null, reviewed: 0 } };
  return new Response(JSON.stringify(result), { headers: { "Content-Type": "application/json" } });
};
await getMe();
const { BankSolve } = await import("../src/bank/BankSolve");
createRoot(document.getElementById("root")!).render(<MemoryRouter><main style={{ width: "min(100%, 850px)", margin: "30px auto", padding: 20 }}>
  <BankSolve base="/api/lectures/test/axes/bank" lecture={{ subject: "test", runId: "axes" }} onFinished={() => {}} />
</main></MemoryRouter>);

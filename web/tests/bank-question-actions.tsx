// Browser fixture: report requests stay local, including a failed first submission.
import { createRoot } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import { BankSolve } from "../src/bank/BankSolve";
import type { BankAnswer, BankNext } from "../src/types/bank";
import "../src/styles/base.css";

const admin = !new URLSearchParams(location.search).has("student");
let reports = 0;
const next: BankNext = { question: {
  question_id: "CNS-C99", concept_id: "C1", tier: "Core", importance: 3, format: "basic",
  retrieval_direction: "direct", question: "두 개념의 차이를 설명하세요.", source_refs: [], conflict_id: "",
  options: [], matching_left: [], matching_right: [], sequence_items: [],
}, reviewToken: "demo-token" };
const answer: BankAnswer = { answer: "두 개념은 작용하는 위치가 다릅니다.", answerUnits: ["작용 위치"],
  correctOptionIds: [], answerPairs: [], correctOrder: [], slides: [], medicalReview: null };
window.fetch = async (input, init) => {
  const path = new URL(String(input), location.origin).pathname;
  let body: unknown = {};
  let status = 200;
  if (path.endsWith("/me")) body = { isAdmin: admin, isApproved: true };
  else if (path.endsWith("/timetable")) body = { events: [] };
  else if (path.endsWith("/next")) body = next;
  else if (path.endsWith("/prepare") || path.endsWith("/reveal")) body = answer;
  else if (path.endsWith("/feedback")) {
    reports++;
    document.getElementById("requests")!.textContent = String(init?.body);
    if (reports === 1) { status = 503; body = { detail: "전송 실패 예시 · 다시 보내 주세요." }; }
  }
  return new Response(JSON.stringify(body), { status });
};
createRoot(document.getElementById("root")!).render(<MemoryRouter>
  <BankSolve base="/api/test/bank" lecture={{ subject: "테스트", runId: "demo" }} onFinished={() => {}} />
</MemoryRouter>);

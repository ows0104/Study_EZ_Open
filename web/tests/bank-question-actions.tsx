// Browser fixture: report requests stay local, including a failed first submission.
import { createRoot } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import { BankSolve } from "../src/bank/BankSolve";
import type { BankAnswer, BankNext } from "../src/types/bank";
import "../src/styles/base.css";

const admin = !new URLSearchParams(location.search).has("student");
let reports = 0;
let personal: { question: string; answer: string; comment: string } | null = null;
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
  else if (path.endsWith("/prepare") || path.endsWith("/reveal")) body = personal && personal.answer !== answer.answer
    ? { ...answer, answer: personal.answer, answerUnits: [], personalAnswer: true, personalEdited: true } : answer;
  else if (path.endsWith("/personal")) {
    const original = { question: next.question!.question, answer: answer.answer };
    if (init?.method !== "PUT") body = { original, draft: personal ?? original, edited: Boolean(personal),
      comment: personal?.comment ?? "", revision: "r".repeat(64) };
    else {
      const sent = JSON.parse(String(init.body));
      document.getElementById("requests")!.textContent = String(init.body);
      if (sent.report && ++reports === 1) { status = 503; body = { detail: "전송 실패 예시 · 다시 보내 주세요." }; }
      else {
        personal = sent.action === "reset" ? null : { question: sent.question, answer: sent.answer, comment: sent.comment };
        const changed = personal?.answer !== undefined && personal.answer !== answer.answer;
        body = { question: { ...next.question, question: personal?.question ?? original.question, personalEdited: Boolean(personal) },
          answer: { ...answer, answer: personal?.answer ?? answer.answer, answerUnits: changed ? [] : answer.answerUnits,
            personalEdited: Boolean(personal), personalAnswer: changed }, reported: sent.action !== "reset", highlighted: sent.report };
      }
    }
  }
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

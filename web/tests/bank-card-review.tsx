// UI-only fixture; production requests never leave this page.
import { createRoot } from "react-dom/client";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { BankCardReview } from "../src/admin/BankCardReview";
import type { BankFullQuestion, BankReviewBoard } from "../src/types/bank";
import "../src/styles/base.css";

const base: BankFullQuestion = {
  question_id: "CNS-C01", concept_id: "C1", tier: "Core", importance: 3, item_difficulty: 2,
  format: "basic", retrieval_direction: "direct", question: "기초 개념을 설명하세요.", answer: "기초 개념의 답",
  answer_units: ["기초 개념"], prerequisites: [], source_refs: [{ source_id: "S1", locator: "p5" }],
  exam_rationale: "테스트", conflict_id: "", options: [], correct_option_ids: [], matching_left: [],
  matching_right: [], answer_pairs: [], sequence_items: [], correct_order: [],
};
const board: BankReviewBoard = { open: 3, done: 1, banks: [{
  subject: "테스트", runId: "demo", title: "중추신경계 · 문항 검토 예시", date: "2026-10-07", buildId: "demo-build",
  concepts: [{ id: "C1", title: "기초·통합 개념" }],
  questions: [{ id: "CNS-C01", question: base.question, available: true },
    { id: "CNS-C05", question: "두 개념을 연결해 설명하세요.", available: false },
    { id: "CNS-C36", question: "항목을 짝지으세요.", available: false }],
  cards: [
    { question: { ...structuredClone(base), question_id: "CNS-C99" }, errors: [], medicalReview: null,
      edit: { action: "accept", original: base, question: base, by: "관리자", at: "2026-10-09T00:00:00Z" } },
    { question: structuredClone(base), errors: [], edit: null, medicalReview: { question_id: base.question_id,
      verdict: "wrong", note: "정답의 표현을 확인하세요.", suggested_answer: "수정된 기초 개념의 답" } },
    { question: { ...structuredClone(base), question_id: "CNS-C05", question: "두 개념을 연결해 설명하세요.", retrieval_direction: "integration" },
      errors: ["CNS-C05: integration의 기초 문항 필요"], medicalReview: null, edit: null },
    { question: { ...structuredClone(base), question_id: "CNS-C36", question: "항목을 짝지으세요.", format: "matching",
      matching_left: ["가", "나"], matching_right: ["A", "B", "B"], answer_pairs: [{ left: "가", right: "A" }, { left: "나", right: "B" }] },
      errors: ["CNS-C36 right: ID/값 중복"], medicalReview: null, edit: null },
  ],
}] };
window.fetch = async (input, init) => {
  const url = new URL(String(input), location.origin);
  if (init?.method === "PUT") {
    const body = JSON.parse(String(init.body));
    const qid = decodeURIComponent(url.pathname.split("/").at(-1)!);
    const card = board.banks[0].cards.find(c => c.question.question_id === qid)!;
    const q = body.question ?? card.question;
    if (body.action === "edit" && q.retrieval_direction === "integration" && !q.prerequisites.length)
      return new Response(JSON.stringify({ detail: `${qid}: integration의 기초 문항 필요` }), { status: 422 });
    if (body.action === "edit" && new Set(q.matching_right).size !== q.matching_right.length)
      return new Response(JSON.stringify({ detail: `${qid} right: ID/값 중복` }), { status: 422 });
    card.edit = { action: body.action, original: structuredClone(card.question), question: q, by: "관리자", at: new Date().toISOString() };
    card.question = q; card.errors = [];
    board.open--; board.done++;
    const listed = board.banks[0].questions.find(p => p.id === qid);
    if (listed) listed.available = true;
    return new Response(JSON.stringify({ action: body.action }), { status: 200 });
  }
  return new Response(JSON.stringify(board), { status: 200 });
};
createRoot(document.getElementById("root")!).render(<MemoryRouter initialEntries={["/admin/bank-cards/테스트/demo" + location.search]}>
  <Routes><Route path="/admin/bank-cards/:subject/:runId" element={<BankCardReview />} /></Routes>
</MemoryRouter>);

import { createRoot } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import { BankReportTab } from "../src/admin/BankReportTab";
import type { BankReportBoard, BankReportGroup } from "../src/types/bank";
import "../src/styles/base.css";

function group(id: string, highlighted: boolean): BankReportGroup {
  return { subject: "테스트", runId: "demo", questionId: id, title: "복습퀴즈", date: "2026-10-09",
    medicalReview: null, question: { question_id: id, concept_id: "C1", tier: "Core", importance: 3, item_difficulty: 1,
      format: "basic", retrieval_direction: "direct", question: "두 개념의 차이를 설명하세요.", answer: "예시 정답",
      answer_units: [], prerequisites: [], source_refs: [], exam_rationale: "", conflict_id: "", options: [],
      correct_option_ids: [], matching_left: [], matching_right: [], answer_pairs: [], sequence_items: [], correct_order: [] },
    reports: [{ id: highlighted ? 1 : 2, category: "wording", comment: "발문의 범위를 구체적으로 고쳤습니다.\n[개인 수정 제안]\n발문: 두 개념의 작용 위치를 비교해 주세요.",
      highlighted, status: "open", email: "user@example.com", createdAt: "2026-10-09T07:00:00Z", stale: false }] };
}
const board: BankReportBoard = { open: 2, done: 0, questions: [group("Q1", true), group("Q2", false)] };
createRoot(document.getElementById("root")!).render(<MemoryRouter>
  <BankReportTab board={board} onChanged={() => {}} />
</MemoryRouter>);

import { createRoot } from "react-dom/client";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { BankCatalogPage } from "../src/bank/BankCatalog";
import type { BankAnswer, BankCatalog, BankQuestion } from "../src/types/bank";
import "../src/styles/base.css";

const state = { requests: [] as { path: string; method: string }[], failAnswer: false, failList: false, stale: false, delay: false };
Object.assign(window, { catalogTest: state });
function question(id: string, format: BankQuestion["format"], text: string, extra: Partial<BankQuestion> = {}): BankQuestion {
  return { question_id: id, concept_id: "C1", tier: "Core", importance: 5, format,
    retrieval_direction: "direct", question: text, source_refs: [], conflict_id: "", options: [],
    matching_left: [], matching_right: [], sequence_items: [], ...extra };
}
const questions: BankCatalog["questions"] = [
  { question: question("Q2", "basic", "두 번째 슬라이드의 핵심 개념을 설명하세요.", { tier: "Optional", advanced: true }), pages: [2], suspended: false },
  { question: question("Q4", "cloze", "수용체와 결합하는 물질은 {{c1}}입니다.", { tier: "Essential" }), pages: [2, 3], suspended: true },
  { question: question("Q3", "mcq", "다음 중 올바른 설명을 고르세요.", { options: [{ id: "A", text: "첫 번째 설명" }, { id: "B", text: "두 번째 설명" }] }), pages: [9], suspended: false },
  { question: question("Q1", "ox", "이 예시 문장은 참이다. — 검토 표시 예시"), pages: [12], suspended: false },
  { question: question("Q6", "matching", "관련 있는 항목끼리 연결하세요.", { matching_left: ["항목 1", "항목 2"], matching_right: ["설명 1", "설명 2"] }), pages: [20], suspended: false },
  { question: question("Q7", "sequence", "단계를 순서대로 나열하세요.", { sequence_items: ["첫 단계", "다음 단계"] }), pages: [20], suspended: false },
  { question: question("PQ1", "basic", "내가 추가한 긴 문제 " + "어떤 슬라이드에도 연결하지 않은 개인 메모입니다. ".repeat(4), { personalAdded: true }), pages: [], suspended: false },
];
const image = (page: number) => "data:image/svg+xml," + encodeURIComponent(`<svg xmlns="http://www.w3.org/2000/svg" width="800" height="520" viewBox="0 0 800 520"><rect width="800" height="520" fill="#f6f8fc"/><rect x="40" y="40" width="720" height="440" rx="12" fill="white" stroke="#d9e0ed"/><text x="80" y="115" font-family="sans-serif" font-size="32" fill="#27354d">Lecture notes · Slide ${page}</text><path d="M80 150H720M80 210H640M80 245H700M80 280H560" stroke="#cbd5e5" stroke-width="12"/><rect x="80" y="330" width="280" height="85" rx="8" fill="#eef2ff"/><rect x="400" y="330" width="280" height="85" rx="8" fill="#f0f7f4"/></svg>`);
const catalog: BankCatalog = { buildId: "b1", title: "강의 흐름과 핵심 개념", subject: "예시 과목", runId: "demo", questions,
  slides: [2, 9, 12, 20].map(page => ({ page, url: image(page) })) };
window.fetch = async (input, init) => {
  const url = new URL(String(input), location.origin);
  state.requests.push({ path: url.pathname, method: init?.method ?? "GET" });
  if (url.pathname.endsWith("/catalog")) return Response.json(state.failList ? { detail: "목록 조회 실패" } : location.search.includes("empty") ? { ...catalog, questions: [], slides: [] } : catalog, { status: state.failList ? 503 : 200 });
  if (state.delay) await new Promise(resolve => setTimeout(resolve, 300));
  if (state.failAnswer || state.stale) return Response.json({ detail: state.stale ? "문제은행이 갱신되었습니다. 목록을 새로고침해 주세요." : "정답 조회 실패" }, { status: state.stale ? 409 : 503 });
  const q = questions.find(item => item.question.question_id === url.pathname.split("/").pop())!.question;
  const answer: BankAnswer = { answer: q.format === "ox" ? "O" : "예시 정답", answerUnits: q.format === "cloze" ? ["예시 정답"] : [],
    explanation: "등록된 해설을 확인합니다.", correctOptionIds: q.format === "mcq" ? ["B"] : [],
    answerPairs: q.format === "matching" ? [{ left: "항목 1", right: "설명 1" }, { left: "항목 2", right: "설명 2" }] : [],
    correctOrder: q.format === "sequence" ? ["첫 단계", "다음 단계"] : [], slides: [],
    medicalReview: q.format === "ox" ? { question_id: q.question_id, verdict: "doubt", note: "남은 검토 사항", suggested_answer: "" } : null };
  return Response.json({ question: q, answer });
};
createRoot(document.getElementById("root")!).render(<MemoryRouter initialEntries={["/bank/test/demo/all"]}><Routes>
  <Route path="/bank/:subject/:runId/all" element={<BankCatalogPage />} />
</Routes></MemoryRouter>);

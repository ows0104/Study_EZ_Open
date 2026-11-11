import React from "react";
import { createRoot } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import "../src/styles/base.css";

const results: string[] = [];
const check = (value: unknown, message: string) => {
  if (!value) throw new Error(message);
  results.push(`PASS ${message}`);
  document.getElementById("results")!.textContent = results.join("\n");
};
const waitFor = async (test: () => unknown) => {
  for (let i = 0; i < 500; i++) { if (test()) return; await new Promise(resolve => setTimeout(resolve, 10)); }
  throw new Error("Timed out");
};
let index = 1;
const ratings: string[] = [];
const answer = { answer: "B: 약물이 효소의 작용을 촉진한다.", answerUnits: [
  "A: 참 — 약물이 수용체를 차단하므로 수용체의 작용을 억제한다.",
  "B: 거짓 — 효소의 작용을 촉진하지 않는다. **효소 억제**가 올바른 관계다.",
  "C: 참 — 조건에 따라 반응의 크기가 달라진다.",
], correctOptionIds: ["B"], answerPairs: [], correctOrder: [], slides: [], medicalReview: null };
window.fetch = async (input, init) => {
  const path = new URL(String(input), location.origin).pathname;
  let result: unknown;
  if (path.endsWith("/next")) result = { reviewToken: `choice-${index}`, question: {
    question_id: `C${index}`, question: "다음 관계 중 옳지 않은 것은?", concept_id: "C1", tier: "Core",
    importance: 5, format: index === 1 ? "mcq" : "multi_select", retrieval_direction: "discrimination",
    source_refs: [], conflict_id: "", options: [
      { id: "A", text: "약물이 수용체의 작용을 억제한다." },
      { id: "B", text: "약물이 효소의 작용을 촉진한다." },
      { id: "C", text: "조건에 따라 반응의 크기가 달라진다." },
    ], matching_left: [], matching_right: [], sequence_items: [],
  } };
  else if (path.endsWith("/prepare") || path.endsWith("/reveal")) result = answer;
  else if (path.endsWith("/rate")) { ratings.push(JSON.parse(String(init?.body)).rating); index++; result = {}; }
  else throw new Error(`Unexpected request: ${path}`);
  return new Response(JSON.stringify(result), { headers: { "Content-Type": "application/json" } });
};
try {
  const { BankSolve } = await import("../src/bank/BankSolve");
  createRoot(document.getElementById("root")!).render(<MemoryRouter>
    <BankSolve base="/api/test/bank" lecture={{ subject: "테스트", runId: "demo" }} onFinished={() => {}} />
  </MemoryRouter>);
  for (const format of ["mcq", "multi_select"]) {
    await waitFor(() => document.querySelectorAll(".bank-option").length === 3 && !document.querySelector(".bank-choice-explanation"));
    check(!document.body.textContent?.includes("효소 억제"), `${format}: prepared explanations stay hidden before reveal`);
    // mcq는 키 1로, multi_select는 누름으로 첫 선지를 고른다(2026-11-12 번호 키).
    if (format === "mcq") window.dispatchEvent(new KeyboardEvent("keydown", { key: "1", bubbles: true }));
    else document.querySelector<HTMLButtonElement>(".bank-option")!.click();
    await new Promise(resolve => setTimeout(resolve, 20));
    document.querySelector<HTMLButtonElement>(".quiz-submit")!.click();
    await waitFor(() => document.querySelectorAll(".bank-choice-explanation li").length === 3
      && !document.querySelector<HTMLButtonElement>(".quiz-grade")!.disabled);
    check(document.querySelector(".bank-option.is-picked")?.textContent?.startsWith("1"), `${format}: selected distractor remains visible`);
    const explanations = document.querySelectorAll(".bank-choice-explanation li");
    check(explanations[0].textContent?.includes("정답이 아닌 선지") && explanations[0].textContent?.includes("수용체를 차단"), `${format}: non-answer option includes its explanation`);
    check(explanations[1].textContent?.includes("정답 선지") && explanations[1].textContent?.includes("거짓")
      && explanations[1].querySelector("strong")?.textContent === "효소 억제", `${format}: negative stem keeps truth and answer status separate`);
    check(explanations[2].textContent?.includes("조건에 따라 반응"), `${format}: unselected distractor explanation is visible`);
    if (new URLSearchParams(location.search).has("preview")) {
      document.getElementById("results")!.style.display = "none";
      await new Promise<void>(() => {});
    }
    document.querySelector<HTMLButtonElement>(".quiz-grade.is-hard")!.click();
    await waitFor(() => !document.querySelector(".bank-choice-explanation"));
  }
  check(ratings.join() === "Hard,Hard", "choice formats save the user's difficulty rating");
  results.push("ALL PASSED");
  document.getElementById("results")!.textContent = results.join("\n");
} catch (error) { document.getElementById("results")!.textContent = results.join("\n") + `\nFAIL ${String(error)}`; }

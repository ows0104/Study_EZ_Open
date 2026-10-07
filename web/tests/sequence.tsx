import React from "react";
import { createRoot } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import type { BankQuestion } from "../src/types/bank";
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
const steps = ["첫 단계: **자극의 전달**", "둘째 단계: 수용체와 결합", "셋째 단계: 세포 내부 신호 활성화", "넷째 단계: 최종 반응 발생"];
let index = 1, revealed = false, rejectReveal = true, rejectRate = true, revealCalls = 0;
const ratings: string[] = [];
const question = (): BankQuestion => ({ question_id: `S${index}`, question: `순서형 예시 ${index}`, concept_id: "C1", tier: "Core",
  importance: 5, format: index === 3 ? "basic" : "sequence", retrieval_direction: "sequence",
  source_refs: [], conflict_id: "", options: [], matching_left: [], matching_right: [], sequence_items: steps });
const answer = { answer: "과정의 올바른 순서입니다.", answerUnits: [], correctOptionIds: [], answerPairs: [], correctOrder: steps, slides: [], medicalReview: null };
const next = () => ({ question: question(), reviewToken: `token-${index}`, undoToken: ratings.length ? "undo" : null,
  answer: revealed ? answer : null, preloadSlides: [] });
window.fetch = async (input, init) => {
  const path = new URL(String(input), location.origin).pathname;
  const body = init?.body ? JSON.parse(String(init.body)) : {};
  let result: unknown, status = 200;
  if (path.endsWith("/next")) result = next();
  else if (path.endsWith("/prepare")) result = answer;
  else if (path.endsWith("/reveal")) {
    revealCalls++;
    await new Promise(resolve => setTimeout(resolve, 50));
    if (rejectReveal) { rejectReveal = false; status = 503; result = { detail: "reveal failed" }; }
    else { revealed = true; result = answer; }
  } else if (path.endsWith("/rate")) {
    if (!revealed) throw new Error("Must reveal before rating");
    if (rejectRate) { rejectRate = false; status = 503; result = { detail: "rate failed" }; }
    else { ratings.push(body.rating); index++; revealed = false; result = {}; }
  } else if (path.endsWith("/undo")) { ratings.pop(); index--; revealed = true; result = next(); }
  else throw new Error(`Unexpected request: ${path}`);
  return new Response(JSON.stringify(result), { status, headers: { "Content-Type": "application/json" } });
};
const options = () => Array.from(document.querySelectorAll<HTMLButtonElement>(".bank-sequence-options button"));
const selected = () => Array.from(document.querySelectorAll<HTMLButtonElement>(".bank-sequence-order button"));
const submit = () => document.querySelector<HTMLButtonElement>(".quiz-bar .quiz-submit")!;
const pick = async (position: number) => {
  const labels = ["첫 단계", "둘째 단계", "셋째 단계", "넷째 단계"];
  options().find(button => button.textContent?.includes(labels[position]))!.click();
  await new Promise(resolve => setTimeout(resolve, 20));
};
try {
  const { BankSolve } = await import("../src/bank/BankSolve");
  const { sequenceScore } = await import("../src/bank/SequenceQuestion");
  createRoot(document.getElementById("root")!).render(<MemoryRouter><main className="app-main is-bare is-solving">
    <BankSolve base="/api/test/bank" onFinished={() => {}} />
  </main></MemoryRouter>);
  await waitFor(() => options().length === 4);
  check(submit().disabled, "incomplete sequence cannot be graded");
  window.dispatchEvent(new KeyboardEvent("keydown", { key: " ", bubbles: true }));
  await new Promise(resolve => setTimeout(resolve, 30));
  check(revealCalls === 0, "keyboard cannot bypass incomplete sequence");
  check(!document.querySelector(".bank-sequence-score"), "prepared answer stays hidden");
  await pick(2); await pick(0); await pick(1);
  check(selected()[0].textContent?.includes("셋째 단계") && selected()[1].textContent?.includes("첫 단계"), "clicked items stack below in click order");
  await pick(0);
  check(selected().length === 3, "selected options cannot be duplicated");
  selected()[1].click(); await new Promise(resolve => setTimeout(resolve, 20));
  check(selected().length === 2 && selected()[1].querySelector("b")!.textContent === "2", "removing a middle step renumbers the remaining order");
  await pick(0);
  check(selected()[2].textContent?.includes("첫 단계"), "removed item can be appended again");
  document.querySelector<HTMLButtonElement>(".bank-sequence-reset")!.click();
  await waitFor(() => selected().length === 0);
  check(options().every(button => !button.disabled) && submit().disabled, "reset clears order and re-enables all options");
  for (let i = 0; i < 4; i++) await pick(i);
  check(!submit().disabled && selected()[0].querySelector("strong"), "complete order enables grading and preserves emphasis");
  submit().click(); await waitFor(() => document.body.textContent?.includes("reveal failed") && !submit().disabled);
  check(selected().length === 4 && !document.querySelector(".bank-sequence-score"), "failed reveal preserves order without a provisional score");
  submit().click(); await waitFor(() => document.querySelector(".bank-sequence-score") && !submit().disabled);
  check(document.querySelector(".bank-sequence-score")!.textContent?.includes("모두 맞았어요"), "correct sequence is graded automatically");
  check(selected().every(button => button.disabled) && !document.querySelector(".bank-sequence-reset"), "graded order is locked");
  window.dispatchEvent(new KeyboardEvent("keydown", { key: "4", bubbles: true }));
  check(!document.querySelector(".quiz-grade") && ratings.length === 0, "manual rating cannot override automatic result");
  submit().click(); await waitFor(() => document.body.textContent?.includes("rate failed") && !submit().disabled);
  check(ratings.length === 0 && selected().length === 4, "failed saving keeps the graded sequence for retry");
  submit().click(); submit().click(); await waitFor(() => document.body.textContent?.includes("순서형 예시 2"));
  check(ratings.join() === "Good" && selected().length === 0, "all-correct result is saved once and next sequence starts empty");
  await pick(1); await pick(0); await pick(2); await pick(3);
  submit().click(); await waitFor(() => document.querySelector(".bank-sequence-score") && !submit().disabled);
  check(document.querySelector(".bank-sequence-score")!.textContent?.includes("2 / 4"), "wrong sequence reports matching positions");
  check(selected()[0].classList.contains("is-wrong") && selected()[2].classList.contains("is-correct"), "each selected position shows correctness");
  check(document.querySelectorAll(".bank-correct-order li").length === 4
    && document.querySelector(".bank-correct-order li strong"), "correct order is numbered and keeps emphasis");
  const q = question();
  check(sequenceScore(q, answer, [steps[0], steps[0], steps[2], steps[3]]) === null,
    "duplicate or invalid orders are never automatically graded");
  if (new URLSearchParams(location.search).has("preview")) {
    document.getElementById("results")!.style.display = "none";
    await new Promise<void>(() => {});
  }
  submit().click(); await waitFor(() => document.body.textContent?.includes("순서형 예시 3"));
  check(ratings.join() === "Good,Again" && submit().textContent?.includes("답 보기"), "wrong order saves Again and other formats keep their flow");
  document.querySelector<HTMLButtonElement>(".quiz-undo")!.click(); await waitFor(() => document.body.textContent?.includes("순서형 예시 2"));
  check(document.querySelectorAll(".quiz-grade").length === 4 && !document.querySelector(".bank-sequence-score"), "undo does not grade stale sequence selections");
  results.push("ALL PASSED");
  document.getElementById("results")!.textContent = results.join("\n");
} catch (error) { document.getElementById("results")!.textContent = results.join("\n") + `\nFAIL ${String(error)}`; }

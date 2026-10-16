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
const left = ["L1: Alpha", "L2: Beta", "L3: Gamma", "L4: Delta"];
const right = ["R1: One", "R2: Two", "R3: Three", "R4: Four"];
let index = 1, revealed = false, rejectReveal = true, rejectRate = true, revealCalls = 0;
const ratings: string[] = [];
const question = () => ({ question_id: `Q${index}`, question: `MATCHING-${index}`, concept_id: "C1", tier: "Core",
  importance: 5, format: index === 3 ? "basic" : "matching", retrieval_direction: "direct",
  source_refs: [], conflict_id: "", options: [], matching_left: left, matching_right: right, sequence_items: [] });
// Both of the first two rows map to the same right item: reuse is valid.
const answer = { answer: "ANSWER", answerUnits: [], correctOptionIds: [],
  answerPairs: left.map((item, i) => ({ left: item, right: right[i === 1 ? 0 : i] })),
  correctOrder: [], slides: [], medicalReview: null };
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
const buttons = () => Array.from(document.querySelectorAll<HTMLButtonElement>(".bank-match [aria-label='짝짓기 보기'] button"));
const rows = () => Array.from(document.querySelectorAll<HTMLButtonElement>(".bank-match [aria-label='짝짓기 번호'] button"));
const submit = () => document.querySelector<HTMLButtonElement>(".quiz-bar .quiz-submit")!;
const rateButton = (grade: string) => document.querySelector<HTMLButtonElement>(`.quiz-grade.is-${grade}`)!;
const pickRight = async (text: string) => {
  buttons().find(button => button.textContent?.includes(text))!.click();
  await new Promise(resolve => setTimeout(resolve, 20));
};
const fillCorrect = async () => {
  for (const [index, item] of left.entries()) {
    rows().find(row => row.textContent?.includes(item.split(': ')[1]))!.click();
    await new Promise(resolve => setTimeout(resolve, 20));
    await pickRight(right[index === 1 ? 0 : index].split(': ')[1]);
  }
};
try {
  const { BankSolve } = await import("../src/bank/BankSolve");
  createRoot(document.getElementById("root")!).render(<MemoryRouter><BankSolve base="/api/test/bank" lecture={{ subject: "테스트", runId: "demo" }} onFinished={() => {}} /></MemoryRouter>);
  await waitFor(() => buttons().length === 4);
  check(submit().disabled, "incomplete matching cannot be submitted");
  const nativeSelection = new KeyboardEvent("keydown", { key: " ", bubbles: true, cancelable: true });
  buttons()[0].dispatchEvent(nativeSelection);
  check(!nativeSelection.defaultPrevented, "Space still selects a focused choice while matching is incomplete");
  window.dispatchEvent(new KeyboardEvent("keydown", { key: " ", bubbles: true }));
  await new Promise(resolve => setTimeout(resolve, 50));
  check(revealCalls === 0, "keyboard cannot bypass incomplete matching");
  await pickRight("Two");
  check(rows()[0].querySelector(".bank-match-picked")!.textContent === buttons().find(b => b.textContent?.includes("Two"))!.querySelector("b")!.textContent,
    "right click writes its shuffled letter beside the left number");
  await pickRight("One"); await pickRight("Three"); await pickRight("Four");
  rows()[0].click(); await new Promise(resolve => setTimeout(resolve, 20)); await pickRight("One");
  check(rows()[0].querySelector(".bank-match-picked")!.textContent === rows()[1].querySelector(".bank-match-picked")!.textContent,
    "left row can be edited and right items can be reused");
  await fillCorrect();
  check(!submit().disabled, "all matched rows enable grading");
  buttons()[0].focus();
  buttons()[0].dispatchEvent(new KeyboardEvent("keydown", { key: " ", bubbles: true, cancelable: true }));
  await waitFor(() => document.body.textContent?.includes("reveal failed") && !submit().disabled);
  check(!document.querySelector(".bank-match-score"), "failed reveal clears provisional score and preserves picks for retry");
  submit().click(); await waitFor(() => document.querySelector(".bank-match-score") && !rateButton("hard").disabled);
  check(document.querySelector(".bank-match-score")!.textContent?.includes("4 / 4"), "correct raw pairs are graded using displayed shuffled letters");
  check(rows().every(row => row.disabled) && buttons().every(button => button.disabled), "graded choices are locked");
  check(document.querySelectorAll(".quiz-grade").length === 4, "automatic grading keeps all four manual rating buttons");
  window.dispatchEvent(new KeyboardEvent("keydown", { key: " ", bubbles: true }));
  await new Promise(resolve => setTimeout(resolve, 30));
  check(ratings.length === 0 && !document.body.textContent?.includes("rate failed"), "space after grading cannot save an automatic rating");
  rateButton("hard").click(); await waitFor(() => document.body.textContent?.includes("rate failed") && !rateButton("hard").disabled);
  check(ratings.length === 0 && document.body.textContent?.includes("MATCHING-1"), "failed rating keeps the graded question for retry");
  rateButton("hard").click(); rateButton("hard").click(); await waitFor(() => document.body.textContent?.includes("MATCHING-2"));
  check(ratings.join() === "Hard", "all-correct result stores the user's Hard rating exactly once");
  check(rows().every(row => row.querySelector(".bank-match-picked")!.textContent === "—"), "next question clears old selections");
  await fillCorrect();
  rows().find(row => row.textContent?.includes("Alpha"))!.click();
  await new Promise(resolve => setTimeout(resolve, 20)); await pickRight("Two");
  submit().click(); await waitFor(() => document.querySelector(".bank-match-score") && !rateButton("again").disabled);
  check(document.querySelector(".bank-match-score")!.textContent?.includes("3 / 4"), "partially wrong pairs show the correct count");
  const wrong = rows().find(row => row.textContent?.includes("Alpha"))!;
  check(wrong.classList.contains("is-wrong") && wrong.textContent?.includes("정답"), "wrong row shows its correct letter");
  window.dispatchEvent(new KeyboardEvent("keydown", { key: "1", bubbles: true }));
  await waitFor(() => document.body.textContent?.includes("MATCHING-3"));
  check(ratings.join() === "Hard,Again", "wrong result stores Again only when the user chooses it by keyboard");
  check(submit().textContent?.includes("답 보기"), "non-matching questions retain normal reveal flow");
  document.querySelector<HTMLButtonElement>(".quiz-undo")!.click(); await waitFor(() => document.body.textContent?.includes("MATCHING-2"));
  check(document.querySelectorAll(".quiz-grade").length === 4 && !document.querySelector(".bank-match-score"),
    "undo without recorded picks permits re-rating and never grades stale choices");
  results.push("ALL PASSED");
  document.getElementById("results")!.textContent = results.join("\n");
} catch (error) { document.getElementById("results")!.textContent = results.join("\n") + `\nFAIL ${String(error)}`; }

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
let index = 0, rejectReveal = true;
const ratings: string[] = [];
const answer = { answer: "정답: A, C", answerUnits: [], correctOptionIds: ["A", "C"], answerPairs: [], correctOrder: [], slides: [], medicalReview: null };
window.fetch = async (input, init) => {
  const path = new URL(String(input), location.origin).pathname;
  let result: unknown, status = 200;
  if (path.endsWith("/next")) result = { reviewToken: `choice-${index}`, question: {
    question_id: `C${index}`, question: `다음 중 옳은 것을 모두 고르시오. (${index + 1})`, concept_id: "C1", tier: "Core",
    importance: 5, format: "multi_select", retrieval_direction: "discrimination", source_refs: [], conflict_id: "",
    options: ["A", "B", "C", "D"].map(id => ({ id, text: `보기 ${id}` })), matching_left: [], matching_right: [], sequence_items: [],
  } };
  else if (path.endsWith("/prepare")) result = answer;
  else if (path.endsWith("/reveal")) {
    await new Promise(resolve => setTimeout(resolve, 80));
    if (rejectReveal) { rejectReveal = false; status = 503; result = { detail: "reveal failed" }; }
    else result = answer;
  }
  else if (path.endsWith("/rate")) { ratings.push(JSON.parse(String(init?.body)).rating); index++; result = {}; }
  else throw new Error(`Unexpected request: ${path}`);
  return new Response(JSON.stringify(result), { status, headers: { "Content-Type": "application/json" } });
};
const options = () => Array.from(document.querySelectorAll<HTMLButtonElement>(".bank-option"));
const submit = () => document.querySelector<HTMLButtonElement>(".quiz-submit")!;
const pick = async (id: string) => { options().find(button => button.querySelector("b")?.textContent === id)!.click(); await new Promise(resolve => setTimeout(resolve, 20)); };
try {
  const { BankSolve } = await import("../src/bank/BankSolve");
  createRoot(document.getElementById("root")!).render(<MemoryRouter>
    <BankSolve base="/api/test/bank" lecture={{ subject: "테스트", runId: "demo" }} onFinished={() => {}} />
  </MemoryRouter>);
  const cases = [
    { ids: ["A"], correct: 1, missed: 1, wrong: 0, all: false },
    { ids: ["A", "B"], correct: 1, missed: 1, wrong: 1, all: false },
    { ids: ["A", "C", "D"], correct: 2, missed: 0, wrong: 1, all: false },
    { ids: ["C", "A"], correct: 2, missed: 0, wrong: 0, all: true },
    { ids: [], correct: 0, missed: 2, wrong: 0, all: false },
  ];
  for (const sample of cases) {
    await waitFor(() => options().length === 4 && !options()[0].disabled);
    check(!document.querySelector(".bank-choice-score"), `case ${index}: prepared answers stay hidden`);
    for (const id of sample.ids) await pick(id);
    if (index === 0) {
      await pick("B"); await pick("B");
      check(options().filter(button => button.getAttribute("aria-pressed") === "true").length === 1, "clicking again removes a selection");
      submit().click();
      await waitFor(() => document.body.textContent?.includes("reveal failed") && !submit().disabled);
      check(!document.querySelector(".bank-choice-score") && options()[0].getAttribute("aria-pressed") === "true", "failed reveal keeps picks and clears provisional feedback");
    }
    submit().click();
    await waitFor(() => document.querySelector(".bank-choice-score") && !document.querySelector<HTMLButtonElement>(".quiz-grade")!.disabled);
    const text = document.querySelector(".bank-choice-score")!.textContent!;
    check(text.includes("모두 맞았어요") === sample.all, `case ${index}: success requires an exact answer set`);
    check(text.includes(`맞게 고른 정답 ${sample.correct}개 · 빠뜨린 정답 ${sample.missed}개 · 잘못 고른 선지 ${sample.wrong}개`), `case ${index}: all feedback counts match`);
    check(document.querySelectorAll(".bank-option.is-correct").length === sample.correct
      && document.querySelectorAll(".bank-option.is-missed").length === sample.missed
      && document.querySelectorAll(".bank-option.is-wrong").length === sample.wrong, `case ${index}: options have distinct feedback states`);
    check(options().every(button => button.disabled), `case ${index}: revealed selection is locked`);
    if (index === 1) {
      await waitFor(() => new Set([".is-correct", ".is-missed", ".is-wrong"].map(cls =>
        getComputedStyle(document.querySelector(`.bank-option${cls}`)!).backgroundColor)).size === 3);
      const styles = [".is-correct", ".is-missed", ".is-wrong"].map(cls => getComputedStyle(document.querySelector(`.bank-option${cls}`)!).backgroundColor);
      check(new Set(styles).size === 3, "correct, missed, and incorrect answers use different backgrounds");
      if (new URLSearchParams(location.search).has("preview")) {
        document.getElementById("results")!.style.display = "none";
        await new Promise<void>(() => {});
      }
    }
    document.querySelector<HTMLButtonElement>(".quiz-grade.is-hard")!.click();
    await waitFor(() => !document.querySelector(".bank-choice-score"));
    check(options().every(button => button.getAttribute("aria-pressed") === "false"), `case ${index}: next question starts unselected`);
  }
  check(ratings.join() === "Hard,Hard,Hard,Hard,Hard", "difficulty ratings remain user-controlled");
  document.getElementById("results")!.textContent = results.join("\n") + "\nALL PASSED";
} catch (error) { document.getElementById("results")!.textContent = results.join("\n") + `\nFAIL ${String(error)}`; }

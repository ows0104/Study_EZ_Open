import React from "react";
import { createRoot } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import { BankSolve } from "../src/bank/BankSolve";
import "../src/styles/base.css";

const results: string[] = [];
const check = (yes: unknown, message: string) => {
  if (!yes) throw new Error(message);
  results.push(`PASS ${message}`);
  document.getElementById("results")!.textContent = results.join("\n");
};
const waitFor = async (test: () => unknown) => {
  for (let i = 0; i < 500; i++) { if (test()) return; await new Promise(r => setTimeout(r, 10)); }
  throw new Error("Timed out");
};
const batchMode = new URLSearchParams(location.search).has("batch");
const lectures = ["A", "B"].map(runId => ({ subject: "test", runId }));
let index = 1, nextCalls = 0, rateCalls = 0, preparation = 0;
let releaseRate: (() => void) | null = null;
let failRate = false, stalePrediction = false, fallbackAdvance = false;
const answer = { answer: "EXPECTED ANSWER", answerUnits: [], correctOptionIds: [], answerPairs: [], correctOrder: [], slides: [], medicalReview: null };
const next = (id: number) => ({ question: { question_id: `Q${id}`, question: `QUESTION-${id}`, format: "basic",
  options: [], tier: "Core", retrieval_direction: "direct", conflict_id: "", matching_left: [], matching_right: [], sequence_items: [] },
  reviewToken: `token-${id}`, lecture: batchMode ? lectures[id % 2] : undefined, preloadSlides: [] });
window.fetch = async (input, init) => {
  const path = new URL(String(input), location.origin).pathname;
  const body = init?.body ? JSON.parse(String(init.body)) : {};
  let result: unknown, status = 200;
  if (path === "/api/me") result = { id: "student", isAdmin: false };
  else if (path.endsWith("/next")) { nextCalls++; result = next(index); }
  else if (path.endsWith("/prepare") || path.endsWith("/reveal")) result = answer;
  else if (path.endsWith("/prepare-next")) {
    check(!batchMode || body.lectures.length === 2, "preview retains batch selection");
    result = Object.fromEntries(["Again", "Hard", "Good", "Easy"].map(rating => [rating, next(stalePrediction ? 99 : index + 1)]));
    preparation++;
  } else if (path.endsWith("/rate")) {
    rateCalls++;
    check(body.advance === true && (!batchMode || body.lectures.length === 2), "rating requests combined advancement");
    await new Promise<void>(resolve => { releaseRate = resolve; });
    if (failRate) { status = 503; result = { detail: "save failed" }; }
    else { index++; result = fallbackAdvance ? { advanceFailed: true } : { next: next(index) }; }
  } else throw new Error(`Unexpected request: ${path}`);
  return new Response(JSON.stringify(result), { status, headers: { "Content-Type": "application/json" } });
};
const submit = () => document.querySelector<HTMLButtonElement>(".quiz-submit")!;
const grade = () => document.querySelector<HTMLButtonElement>(".quiz-grade.is-good")!;
const reveal = async () => {
  const before = preparation;
  submit().click();
  await waitFor(() => grade() && !grade().disabled && preparation > before);
  await new Promise(resolve => setTimeout(resolve, 30));
};
const pending = async (id: number) => {
  releaseRate = null;
  grade().click();
  await waitFor(() => releaseRate && document.body.textContent?.includes(`QUESTION-${id}`));
  check(submit().disabled, "predicted next question waits for saved review before accepting input");
  check(!document.querySelector(".quiz-answer"), "previous answer stays hidden on predicted question");
  check(nextCalls === 1, "predicted question appears without another next request");
};
try {
  createRoot(document.getElementById("root")!).render(<MemoryRouter><BankSolve base="/api/lectures/test/A/bank"
    lecture={lectures[0]} onFinished={() => {}} batch={batchMode ? { lectures, onProgress: () => {} } : undefined} /></MemoryRouter>);
  await waitFor(() => submit());
  await reveal();
  await pending(2);
  window.dispatchEvent(new KeyboardEvent("keydown", { key: "3", bubbles: true }));
  check(rateCalls === 1, "double input never records another review while saving");
  releaseRate!();
  await waitFor(() => !submit().disabled);
  check(nextCalls === 1, "combined rate response avoids the second round trip");
  await reveal();
  failRate = true;
  await pending(3);
  releaseRate!();
  await waitFor(() => grade() && !grade().disabled);
  check(document.body.textContent?.includes("QUESTION-2") && document.querySelector(".quiz-answer"), "failed saving restores the original question and answer");
  check(document.body.textContent?.includes("save failed"), "saving error remains visible for retry");
  failRate = false;
  releaseRate = null;
  grade().click(); await waitFor(() => releaseRate && submit()); releaseRate!();
  await waitFor(() => !submit().disabled);
  stalePrediction = true;
  await reveal();
  await pending(99);
  releaseRate!();
  await waitFor(() => document.body.textContent?.includes("QUESTION-4") && !submit().disabled);
  check(!document.body.textContent?.includes("QUESTION-99"), "server result replaces stale predictions");
  stalePrediction = false;
  await reveal();
  fallbackAdvance = true;
  releaseRate = null;
  grade().click(); await waitFor(() => releaseRate && submit()); releaseRate!();
  await waitFor(() => document.body.textContent?.includes("QUESTION-5") && !submit().disabled);
  check(nextCalls === 2 && rateCalls === 5, "failed advancement retries only next, preserving the saved rating");
  document.getElementById("results")!.textContent = results.join("\n") + "\nALL PASSED";
} catch (error) { document.getElementById("results")!.textContent = results.join("\n") + `\nFAIL ${String(error)}`; }

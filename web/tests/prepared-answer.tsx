// Local-only browser regression: real BankSolve with controlled network completion.
import React from "react";
import { createRoot } from "react-dom/client";
import "../src/styles/base.css";

const results: string[] = [];
const report = (message: string) => {
  results.push(message);
  document.getElementById("results")!.textContent = results.join("\n");
};
const check = (yes: unknown, message: string) => { if (!yes) throw new Error(message); report(`PASS ${message}`); };
const waitFor = async (test: () => unknown) => {
  for (let i = 0; i < 500; i++) { if (test()) return; await new Promise((r) => setTimeout(r, 10)); }
  throw new Error("Timed out");
};
const imageUrl = "data:image/svg+xml," + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="80" height="40"><text x="2" y="20">slide</text></svg>');
const NativeImage = window.Image;
const images: HTMLImageElement[] = [];
window.Image = function () { const image = new NativeImage(); images.push(image); return image; } as typeof Image;
let question = 1;
let prepared = false;
let releaseReveal: (() => void) | undefined;
let rejectReveal = false;
let revealDone = false;
const answer = (id: number) => ({ answer: `ANSWER-${id}`, answerUnits: [], correctOptionIds: [],
  answerPairs: [], correctOrder: [], slides: [{ page: 1, url: imageUrl }], conflict: "", external: false });
window.fetch = async (input, init) => {
  const path = new URL(String(input), location.origin).pathname;
  const body = init?.body ? JSON.parse(String(init.body)) : {};
  let result: unknown;
  let status = 200;
  if (path.endsWith("/next")) result = { question: { question_id: `Q${question}`, question: `QUESTION-${question}`,
    format: "basic", options: [], tier: "Core", retrieval_direction: "direct", conflict_id: "" },
    reviewToken: `token-${question}`, preloadSlides: [{ page: 1, url: imageUrl }] };
  else if (path.endsWith("/prepare")) {
    if (question === 2) { status = 503; result = { detail: "warmup unavailable" }; }
    else { result = answer(question); prepared = true; }
  } else if (path.endsWith("/reveal")) {
    revealDone = false;
    await new Promise<void>((r) => { releaseReveal = r; });
    status = rejectReveal ? 409 : 200;
    result = rejectReveal ? { detail: "stale token" } : answer(Number(body.reviewToken.split("-")[1]));
    revealDone = true;
  } else if (path.endsWith("/rate")) { question++; result = {}; }
  else throw new Error(`Unexpected path: ${path}`);
  return new Response(JSON.stringify(result), { status, headers: { "Content-Type": "application/json" } });
};

try {
  const { BankSolve } = await import("../src/bank/BankSolve");
  createRoot(document.getElementById("root")!).render(<BankSolve base="/api/test/bank" onFinished={() => {}} />);
  await waitFor(() => prepared && images.some((image) => image.complete && image.naturalWidth));
  check(!document.body.textContent?.includes("ANSWER-1"), "answer stays hidden before click");
  document.querySelector<HTMLButtonElement>(".quiz-submit")!.click();
  await waitFor(() => document.querySelector(".quiz-answer"));
  check(!revealDone, "answer appears before reveal request finishes");
  check(Array.from(document.querySelectorAll<HTMLButtonElement>(".quiz-grade")).every((button) => button.disabled), "grading waits for reveal acknowledgement");
  check(images.includes(document.querySelector(".quiz-slide")!), "the already loaded image node is displayed");
  releaseReveal!();
  await waitFor(() => !document.querySelector<HTMLButtonElement>(".quiz-grade")!.disabled);
  document.querySelector<HTMLButtonElement>(".quiz-grade.is-good")!.click();
  await waitFor(() => document.body.textContent?.includes("QUESTION-2"));
  check(!document.querySelector(".quiz-answer"), "previous answer is cleared on next question");
  document.querySelector<HTMLButtonElement>(".quiz-submit")!.click();
  await waitFor(() => document.querySelector<HTMLButtonElement>(".quiz-submit")?.disabled);
  check(!document.querySelector(".quiz-answer"), "failed warmup uses normal reveal without stale answer");
  releaseReveal!();
  await waitFor(() => document.querySelector(".quiz-answer")?.textContent?.includes("ANSWER-2"));
  document.querySelector<HTMLButtonElement>(".quiz-grade.is-good")!.click();
  await waitFor(() => document.body.textContent?.includes("QUESTION-3"));
  await new Promise((r) => setTimeout(r, 100));
  rejectReveal = true;
  document.querySelector<HTMLButtonElement>(".quiz-submit")!.click();
  await waitFor(() => document.querySelector(".quiz-answer"));
  releaseReveal!();
  await waitFor(() => !document.querySelector(".quiz-answer"));
  check(document.body.textContent?.includes("stale token"), "rejected reveal clears prepared answer and allows retry");
  report("ALL PASSED");
} catch (error) { report(`FAIL ${String(error)}`); }

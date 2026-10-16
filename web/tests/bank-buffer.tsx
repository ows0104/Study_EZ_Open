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
const failReveal = new URLSearchParams(location.search).has("revealFailure");
const lectures = ["A", "B"].map(runId => ({ subject: "test", runId }));
let index = 1, loaded = false, freeze = false, failRate = false, stale = false;
let releaseReveal: (() => void) | undefined, releaseRate: (() => void) | undefined;
let nextCalls = 0, rateCalls = 0;
const events: string[] = [], preparations: string[] = [];
const progressTokens: (string | undefined)[] = [];
const answer = (id: number) => ({ answer: `ANSWER-${id}`, answerUnits: [], correctOptionIds: ["A"],
  answerPairs: [], correctOrder: [], slides: [], medicalReview: null });
const question = (id: number, options = false) => ({ question_id: `Q${id}`, question: `QUESTION-${id}`,
  format: id === 2 ? "mcq" : "basic", mcq_mode: id === 2 ? "recall_first" : "comparison",
  options: id === 2 && options ? [{ id: "A", text: "OPTION-A" }, { id: "B", text: "OPTION-B" }] : [],
  tier: "Core", retrieval_direction: "direct", conflict_id: "", matching_left: [], matching_right: [], sequence_items: [] });
const next = (id: number) => ({ question: question(id), reviewToken: `token-${id}`, undoToken: id > 1 ? `undo-${id-1}` : null,
  choicesShown: id !== 2, lecture: batchMode ? lectures[id % 2] : undefined, preloadSlides: [] });
window.fetch = async (input, init) => {
  const path = new URL(String(input), location.origin).pathname;
  const body = init?.body ? JSON.parse(String(init.body)) : {};
  const id = Number(body.reviewToken?.split("-")[1]);
  let result: unknown, status = 200;
  if (path === "/api/me") result = { id: "student", isAdmin: false };
  else if (path.endsWith("/next")) { nextCalls++; result = next(index); }
  else if (path.endsWith("/prepare")) result = answer(id);
  else if (path.endsWith("/prepare-buffer")) {
    preparations.push(body.reviewToken);
    if (freeze || id !== index) { status = 409; result = { detail: "not served" }; }
    else {
      check(!batchMode || body.lectures.length === 2, "buffer preserves batch selection");
      const frames: Record<string, unknown> = {};
      const start = id + (body.ratings?.length ?? 0);
      for (let n = start; n <= start + 3; n++) {
        frames[`token-${n}`] = { next: next(n), answer: answer(n), options: question(n, true),
          previews: n === start + 3 ? {} : Object.fromEntries(["Again", "Hard", "Good", "Easy"]
            .map(r => [r, next(stale && n === start ? 99 : n + 1)])),
          origin: { subject: "test", runId: "A", reviewToken: body.reviewToken,
            ratings: [...(body.ratings ?? []), ...Array(n - start).fill("Good")] } };
      }
      loaded = true; result = { frames };
    }
  } else if (path.endsWith("/options")) {
    check(id === index, "options wait for preceding rating to save");
    events.push(`options-${id}`); result = { question: question(id, true), choicesShown: true };
  } else if (path.endsWith("/reveal")) {
    check(id === index, "reveal writes retain server order");
    events.push(`reveal-${id}`);
    if (id === 1) await new Promise<void>(r => { releaseReveal = r; });
    if (id === 1 && failReveal) { status = 503; result = { detail: "reveal failed" }; }
    else result = answer(id);
  } else if (path.endsWith("/rate")) {
    check(id === index, "ratings never overtake preceding writes");
    check(body.advance && (!batchMode || body.lectures.length === 2), "rating retains combined advancement and batch");
    rateCalls++; events.push(`rate-${id}`);
    await new Promise<void>(r => { releaseRate = r; });
    if (failRate) { status = 503; result = { detail: "save failed" }; }
    else { index++; result = { next: next(index) }; }
  } else throw new Error(`Unexpected request: ${path}`);
  return new Response(JSON.stringify(result), { status, headers: { "Content-Type": "application/json" } });
};
const submit = () => document.querySelector<HTMLButtonElement>(".quiz-submit")!;
const grade = () => document.querySelector<HTMLButtonElement>(".quiz-grade.is-good")!;
const reveal = async () => { submit().click(); await waitFor(() => grade() && !grade().disabled); };
const rate = async (id: number) => {
  grade().click(); await waitFor(() => document.body.textContent?.includes(`QUESTION-${id}`) && submit() && !submit().disabled);
};
const flushRate = async (id: number) => {
  await waitFor(() => releaseRate && events.includes(`rate-${id}`));
  const release = releaseRate!; releaseRate = undefined; release();
};
try {
  createRoot(document.getElementById("root")!).render(<MemoryRouter><BankSolve base="/api/lectures/test/A/bank"
    lecture={lectures[0]} onFinished={() => {}} batch={batchMode ? { lectures, onProgress: got => progressTokens.push(got.reviewToken) } : undefined} /></MemoryRouter>);
  await waitFor(() => submit() && loaded);
  await new Promise(r => setTimeout(r, 40));
  freeze = true;
  await reveal();
  await waitFor(() => releaseReveal);
  check(!grade().disabled, "cached answer can be graded before reveal acknowledgement");
  await rate(2);
  submit().click();
  await waitFor(() => document.body.textContent?.includes("OPTION-A"));
  check(!submit().disabled && !events.includes("options-2"), "cached recall-first options unlock while saving the previous card");
  await reveal(); await rate(3);
  await reveal(); await rate(4);
  check(rateCalls === 0 && nextCalls === 1, "three cached questions remain usable while the first reveal write is held");
  check(!document.querySelector(".quiz-answer"), "previous answers stay hidden on each new question");
  check(Array.from(document.querySelectorAll<HTMLButtonElement>("button")).find(b => b.textContent === "개념 지도")?.disabled,
    "management actions wait for pending saves");
  const leaving = new Event("beforeunload", { cancelable: true }); window.dispatchEvent(leaving);
  check(leaving.defaultPrevented, "leaving the page warns while writes are pending");
  releaseReveal!();
  if (failReveal) {
    await waitFor(() => document.body.textContent?.includes("reveal failed"));
    check(document.body.textContent?.includes("QUESTION-1") && !document.querySelector(".quiz-answer"), "failed reveal restores its question and clears the speculative answer");
    check(rateCalls === 0 && !events.includes("options-2"), "failed reveal cancels every dependent write");
  } else {
    await flushRate(1); await flushRate(2); await flushRate(3);
    await waitFor(() => !document.body.textContent?.includes("저장 중…"));
    check(index === 4 && events.join(",") === "reveal-1,rate-1,options-2,reveal-2,rate-2,reveal-3,rate-3",
      "all queued actions save exactly once in interaction order");
    check(document.body.textContent?.includes("QUESTION-4") && !document.querySelector(".quiz-answer"),
      "late acknowledgements preserve the visible question and hide earlier answers");
    if (batchMode) check(progressTokens.filter(token => token === "token-2").length === 1
      && progressTokens.at(-1) === "token-4", "late saves never move the batch lecture heading back to an earlier card");
    freeze = false;
    await reveal();
    grade().click();
    await flushRate(4);
    await waitFor(() => document.body.textContent?.includes("QUESTION-5") && submit() && !submit().disabled);
    await waitFor(() => preparations.includes("token-5"));
    await new Promise(r => setTimeout(r, 50));
    check(loaded, "the consumed buffer is replenished on the new current question");
    await reveal(); failRate = true; await rate(6);
    await flushRate(5);
    await waitFor(() => document.body.textContent?.includes("save failed") && grade() && !grade().disabled);
    check(document.body.textContent?.includes("QUESTION-5") && document.querySelector(".quiz-answer")?.textContent?.includes("ANSWER-5"),
      "failed rating restores its own question and answer without replaying saved reviews");
    failRate = false; grade().click(); await flushRate(5);
    await waitFor(() => document.body.textContent?.includes("QUESTION-6") && submit() && !submit().disabled);
    await new Promise(r => setTimeout(r, 40));
    check(index === 6 && rateCalls === 6, "retry saves only the failed rating");
    stale = true;
    // Force the next prepared window to differ from the authoritative selection.
    await reveal(); grade().click(); await flushRate(6);
    await waitFor(() => document.body.textContent?.includes("QUESTION-7") && submit() && !submit().disabled);
    await new Promise(r => setTimeout(r, 40));
    await reveal(); await rate(99); await flushRate(7);
    await waitFor(() => document.body.textContent?.includes("QUESTION-8") && submit() && !submit().disabled);
    check(!document.body.textContent?.includes("QUESTION-99"), "changed selection replaces speculative cards using the saved server result");
  }
  document.getElementById("results")!.textContent = results.join("\n") + "\nALL PASSED";
} catch (error) { document.getElementById("results")!.textContent = results.join("\n") + `\nFAIL ${String(error)}`; }

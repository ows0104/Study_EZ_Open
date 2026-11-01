import React from "react";
import { createRoot } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import { BankSolve } from "../src/bank/BankSolve";
import "../src/styles/base.css";

const results: string[] = [];
const check = (yes: unknown, message: string) => { if (!yes) throw new Error(message); results.push(`PASS ${message}`); };
const waitFor = async (test: () => unknown) => {
  for (let i = 0; i < 500; i++) { if (test()) return; await new Promise(r => setTimeout(r, 10)); }
  throw new Error("Timed out");
};
const question = { question_id: "Q1", concept_id: "C1", tier: "Core", importance: 5, format: "basic",
  retrieval_direction: "direct", question: "ORIGINAL QUESTION", options: [], matching_left: [], matching_right: [], sequence_items: [],
  source_refs: [], conflict_id: "", answer: "ANSWER", answer_units: ["ANSWER"], correct_option_ids: [], answer_pairs: [], correct_order: [],
  item_difficulty: 2, prerequisites: [], exam_rationale: "example" };
const original = structuredClone(question);
let fail = true, saved = false, gets = 0;
const requests: string[] = [];
window.fetch = async (input, init) => {
  const url = new URL(String(input), location.origin);
  const path = url.pathname;
  const body = init?.body ? JSON.parse(String(init.body)) : {};
  requests.push(path);
  let result: unknown, status = 200;
  if (path === "/api/me") result = { id: "admin", isAdmin: true, isApproved: true };
  else if (path === "/api/timetable") result = { events: [] };
  else if (path.endsWith("/next")) result = { question, reviewToken: saved ? "new-token" : "token", preloadSlides: [] };
  else if (path.endsWith("/prepare")) result = { answer: "ANSWER", answerUnits: ["ANSWER"], correctOptionIds: [],
    answerPairs: [], correctOrder: [], slides: [], medicalReview: null };
  else if (path === "/api/admin/bank-review") {
    gets++;
    check(url.searchParams.get("questionId") === "Q1" && url.searchParams.get("subject") === "test" && url.searchParams.get("runId") === "run",
      "loads only the current shared question");
    result = { banks: [{ subject: "test", runId: "run", title: "test", date: "2026-10-16", buildId: "v1",
      cards: [{ question: original, errors: [], medicalReview: null, edit: null }],
      concepts: [{ id: "C1", title: "concept" }], questions: [{ id: "Q1", question: "ORIGINAL QUESTION", available: true }] }], open: 1, done: 0 };
  } else if (path.endsWith("/cards/Q1")) {
    check(body.buildId === "v1" && body.expectedQuestion.question === original.question && body.action === "edit", "save retains shared editor conflict checks");
    if (fail) { status = 422; result = { detail: "validation failed" }; }
    else { question.question = body.question.question; saved = true; result = {}; }
  } else throw new Error(`Unexpected request: ${path}`);
  return new Response(JSON.stringify(result), { status, headers: { "Content-Type": "application/json" } });
};
try {
  const { getMe } = await import("../src/firstScreen"); await getMe();
  createRoot(document.getElementById("root")!).render(<MemoryRouter><BankSolve base="/api/lectures/test/run/bank"
    lecture={{ subject: "test", runId: "run" }} onFinished={() => {}} /></MemoryRouter>);
  await waitFor(() => Array.from(document.querySelectorAll('button')).some(b => b.textContent === "공용 문제 수정"));
  const before = requests.length;
  const open = () => Array.from(document.querySelectorAll('button')).find(b => b.textContent === "공용 문제 수정")!.click();
  open();
  await waitFor(() => document.querySelector('dialog[open] textarea'));
  check(!document.querySelector('a[href*="admin/bank-cards"]'), "shared editing stays in the study page");
  // Initial study requests may settle while the lazy editor opens. Check the
  // management boundary without depending on the timing of those requests.
  check(requests.slice(before).filter(path => path.startsWith("/api/admin/"))
    .every(path => path === "/api/admin/bank-review"), "no admin overview, jobs, users or reports are loaded");
  const dialog = () => document.querySelector<HTMLDialogElement>('dialog[open]')!;
  dialog().querySelector<HTMLButtonElement>('[aria-label="공용 수정창 닫기"]')!.click();
  await waitFor(() => !dialog());
  check(document.body.textContent?.includes("ORIGINAL QUESTION"), "closing editor preserves the study question");
  open(); await waitFor(() => dialog()?.querySelector('textarea'));
  const textarea = dialog().querySelector<HTMLTextAreaElement>('textarea')!;
  Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value")!.set!.call(textarea, "UPDATED QUESTION");
  textarea.dispatchEvent(new Event('input', { bubbles: true }));
  await new Promise(r => setTimeout(r, 30));
  const save = () => Array.from(dialog().querySelectorAll('button')).find(b => b.textContent === "검증하고 저장")!.click();
  save(); await waitFor(() => dialog()?.textContent?.includes("validation failed"));
  check(textarea.value === "UPDATED QUESTION", "failed shared validation preserves the draft");
  fail = false; save();
  await waitFor(() => !dialog() && document.querySelector('.bank-stem')?.textContent?.includes("UPDATED QUESTION"));
  check(saved && gets === 2, "successful save refreshes study without loading a management page");
  document.getElementById('results')!.textContent = results.join('\n') + '\nALL PASSED';
} catch (error) { document.getElementById('results')!.textContent = results.join('\n') + `\nFAIL ${String(error)}`; }

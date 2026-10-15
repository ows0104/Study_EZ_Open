import React, { useState } from "react";
import { createRoot } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import type { BankRead } from "../src/types/bank";
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
const batch = new URLSearchParams(location.search).has("batch");
const base = batch ? "/api/lectures/actual/lecture/bank" : "/api/test/bank";
const suspended = new Set<string>();
let calls = 0, reject = true, restored = 0, rated = 0;
const info = () => ({ summary: { buildId: "v1" }, suspendedQuestions: [...suspended].map(questionId => ({ questionId, question: `비활성 문항 ${questionId}` })) }) as BankRead;
window.fetch = async (input, init) => {
  const path = new URL(String(input), location.origin).pathname;
  const body = init?.body ? JSON.parse(String(init.body)) : {};
  let result: unknown, status = 200;
  if (path.endsWith("/next")) {
    const id = !suspended.has("Q1") ? "Q1" : !suspended.has("Q2") ? "Q2" : null;
    result = { reviewToken: id, ...(batch ? { lecture: { subject: "actual", runId: "lecture" } } : {}), question: id ? {
      question_id: id, question: `비활성화 테스트 ${id}`, format: "basic", tier: "Core", retrieval_direction: "direct",
      options: [], matching_left: [], matching_right: [], sequence_items: [],
    } : null };
  } else if (path.endsWith("/prepare") || path.endsWith("/reveal")) {
    result = { answer: "정답", answerUnits: [], correctOptionIds: [], answerPairs: [], correctOrder: [], slides: [] };
  } else if (path.endsWith("/suspension")) {
    check(path.startsWith(base + "/questions/"), "suspension uses the current lecture endpoint");
    const id = path.split("/").at(-2)!;
    if (body.suspended) {
      calls++;
      await new Promise(resolve => setTimeout(resolve, 80));
      if (reject) { reject = false; status = 503; result = { detail: "suspension failed" }; }
      else { check(body.reviewToken === id, "current review token is sent"); suspended.add(id); result = {}; }
    } else {
      check(body.buildId === "v1", "restoration checks the bank build");
      suspended.delete(id); restored++; result = {};
    }
  } else if (path.endsWith("/rate")) { rated++; result = {}; }
  else throw new Error(`Unexpected request: ${path}`);
  return new Response(JSON.stringify(result), { status, headers: { "Content-Type": "application/json" } });
};
const key = (target: EventTarget = window, options = {}) => target.dispatchEvent(new KeyboardEvent("keydown", { key: "5", bubbles: true, ...options }));
try {
  const { BankSolve } = await import("../src/bank/BankSolve");
  const { SuspendedQuestions } = await import("../src/bank/SuspendedQuestions");
  function Harness() {
    const [done, setDone] = useState(false), [reading, setReading] = useState(info());
    return done ? <SuspendedQuestions base={base} info={reading} onChanged={() => setReading(info())} />
      : <BankSolve base={base} lecture={{ subject: "initial", runId: "wrong" }}
        batch={batch ? { lectures: [{ subject: "actual", runId: "lecture" }], onProgress: () => {} } : undefined}
        onFinished={() => { setDone(true); setReading(info()); }} />;
  }
  createRoot(document.getElementById("root")!).render(<MemoryRouter><Harness /></MemoryRouter>);
  await waitFor(() => document.querySelector(".bank-suspend"));
  check(document.querySelector(".bank-suspend")!.textContent?.includes("5"), "button shows shortcut 5 before reveal");
  key(document.querySelector("input")!); key(window, { ctrlKey: true }); key(window, { repeat: true });
  const dialog = document.querySelector("dialog")!; dialog.showModal(); key(); dialog.close();
  await new Promise(resolve => setTimeout(resolve, 20));
  check(calls === 0, "typing, modifiers, held keys and open dialogs cannot suspend");
  key();
  await waitFor(() => document.body.textContent?.includes("suspension failed"));
  check(document.body.textContent?.includes("테스트 Q1") && rated === 0, "failed suspension preserves question without a rating");
  key(); key();
  await waitFor(() => document.body.textContent?.includes("테스트 Q2"));
  check(calls === 2 && suspended.has("Q1") && rated === 0, "successful shortcut advances once without grading");
  document.querySelector<HTMLButtonElement>(".quiz-submit")!.click();
  await waitFor(() => document.querySelectorAll(".quiz-grade").length === 4 && !document.querySelector<HTMLButtonElement>(".bank-suspend")!.disabled);
  check(document.querySelector(".bank-suspend")!.textContent?.includes("5"), "four rating buttons and shortcut 5 coexist after reveal");
  if (new URLSearchParams(location.search).has("preview")) {
    document.getElementById("results")!.style.display = "none";
    document.getElementById("typing-test")!.style.display = "none";
    await new Promise<void>(() => {});
  }
  document.querySelector<HTMLButtonElement>(".bank-suspend")!.click();
  await waitFor(() => document.querySelector(".bank-suspended"));
  check(calls === 3 && suspended.size === 2 && rated === 0, "button can suspend after reveal and finish without a review");
  document.querySelector<HTMLElement>(".bank-suspended summary")!.click();
  document.querySelector<HTMLButtonElement>(".bank-suspended button")!.click();
  await waitFor(() => restored === 1 && document.querySelectorAll(".bank-suspended li").length === 1);
  check(!suspended.has("Q1"), "suspended question can be restored from its list");
  document.getElementById("results")!.textContent = results.join("\n") + "\nALL PASSED";
} catch (error) { document.getElementById("results")!.textContent = results.join("\n") + `\nFAIL ${String(error)}`; }

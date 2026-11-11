/** Main-Quiz 객관식(2026-11-12): 선지 머리표 1·2·3, 답 보기 전 1–4 선택, 5 제외, 답 뒤 1–4 평가. */
import React from "react";
import { createRoot } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import "../src/styles/base.css";
import type { RootAction, RootView } from "../src/types/rootLearning";

const results: string[] = [];
const check = (value: unknown, message: string) => {
  if (!value) throw new Error(message);
  results.push(`PASS ${message}`);
  document.getElementById("results")!.textContent = results.join("\n");
};
const tick = () => new Promise(resolve => setTimeout(resolve, 30));
// 실제 키처럼 포커스된 요소(제목)에서 올라오게 보낸다.
const press = (key: string) => (document.activeElement ?? document.body).dispatchEvent(new KeyboardEvent("keydown", { key, code: key === " " ? "Space" : `Digit${key}`, bubbles: true }));
const question = (format: "mcq" | "multi_select") => ({
  question_id: "Q1", question: "옳은 것은?", concept_id: "C1", tier: "Core", importance: 5, format,
  retrieval_direction: "discrimination", source_refs: [], conflict_id: "",
  options: [{ id: "A", text: "첫째 보기" }, { id: "B", text: "둘째 보기" }, { id: "C", text: "셋째 보기" }],
  matching_left: [], matching_right: [], sequence_items: [],
});
const view = (format: "mcq" | "multi_select", answered = false): RootView => ({
  sessionId: "s1", revision: "v1", version: 1, day: "2026-11-12", policy: {} as RootView["policy"], position: 0, count: 3,
  finished: false, blocked: null, canUndo: false, mapSeen: false, summary: {} as RootView["summary"],
  task: { id: "t1", question: question(format) as never, response: null, attempted: answered ? true : null, helped: false,
    answer: answered ? { answer: "B: 둘째가 맞다.", answerUnits: ["B: 둘째가 맞다."], answerPairs: [], correctOrder: [],
      correctOptionIds: ["B"], medicalReview: null, slides: [] } as never : null },
});
const picked = () => Array.from(document.querySelectorAll<HTMLButtonElement>(".bank-option[aria-pressed='true'] b")).map(b => b.textContent);

try {
  try { localStorage.clear(); } catch { /* storage may be blocked */ }
  const { RootSolve } = await import("../src/bank/RootSolve");
  const actions: RootAction[] = [];
  const root = createRoot(document.getElementById("root")!);
  const render = (v: RootView, scope: string) => root.render(<MemoryRouter><RootSolve view={v} scope={scope} disabled={false} advancing={false}
    onAction={a => actions.push(a)} onToday={() => {}} onError={() => {}} /></MemoryRouter>);

  render(view("mcq"), "mcq");
  await tick();
  const heads = Array.from(document.querySelectorAll(".bank-option b")).map(b => b.textContent);
  check(heads.join() === "1,2,3", "options are labelled 1·2·3 in screen order");
  press("2"); await tick();
  check(picked().join() === "2", "key 2 picks the second option");
  press("3"); await tick();
  check(picked().join() === "3", "mcq: another number replaces the pick");
  press("4"); await tick();
  check(picked().join() === "3", "a number without an option is ignored");
  check(!actions.length, "picking records no event");
  press(" "); await tick();
  check(actions.at(-1)?.kind === "reveal" && actions.at(-1)?.response === "선택: C", "Space reveals with the saved option ID, not the number");

  render(view("multi_select"), "multi");
  await tick();
  press("1"); await tick(); press("3"); await tick();
  check(picked().join() === "1,3", "multi_select: numbers toggle on");
  press("1"); await tick();
  check(picked().join() === "3", "multi_select: same number toggles off");

  press("5"); await tick();
  check(actions.at(-1)?.kind === "exclude", "key 5 excludes the question");
  const menu = Array.from(document.querySelectorAll<HTMLButtonElement>(".mq-menu-pop button")).find(b => b.textContent?.startsWith("이 문제 제외"));
  check(menu && menu.getAttribute("aria-keyshortcuts") === "5", "menu offers 이 문제 제외 with 5");
  menu!.click(); await tick();
  check(actions.at(-1)?.kind === "exclude", "menu button excludes too");

  render(view("mcq", true), "answered");
  await tick();
  check(document.querySelector(".quiz-answer")?.textContent?.startsWith("2"), "answer head shows the option number");
  const count = actions.length;
  press("2"); await tick();
  check(actions.length === count + 1 && actions.at(-1)?.kind === "rate" && actions.at(-1)?.selfRating === "Hard", "after reveal, 2 still rates Hard");
  results.push("ALL PASSED");
  document.getElementById("results")!.textContent = results.join("\n");
} catch (error) { document.getElementById("results")!.textContent = results.join("\n") + `\nFAIL ${String(error)}`; }

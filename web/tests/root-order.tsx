/** Main-Quiz 순서 맞추기(2026-11-18 ordering-screen): 객관식 모드는 처음부터, 주관식은 V로. 숫자 키로 놓고·빼고, Backspace, Space로 확인, 답면 자리별 비교. */
import React from "react";
import { createRoot } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import "../src/styles/base.css";
import "../src/bank/main-quiz.css";
import type { RootAction, RootView } from "../src/types/rootLearning";

const results: string[] = [];
const check = (value: unknown, message: string) => {
  if (!value) throw new Error(message);
  results.push(`PASS ${message}`);
  document.getElementById("results")!.textContent = results.join("\n");
};
const tick = () => new Promise(resolve => setTimeout(resolve, 30));
const key = (init: KeyboardEventInit) => (document.activeElement ?? document.body).dispatchEvent(new KeyboardEvent("keydown", { bubbles: true, cancelable: true, ...init }));
const press = (k: string) => key({ key: k, code: k === " " ? "Space" : /^\d$/.test(k) ? `Digit${k}` : k });
const STEPS = ["세포 진입", "초기 전사", "추가 탈외피", "DNA 복제", "후기 유전자 발현", "입자 조립", "방출"];
const ids = STEPS.map((_, i) => `o${i}`);
const shuffledOrder = [3, 0, 6, 1, 5, 2, 4];   // 서버가 섞어 보낸 순서
const items = shuffledOrder.map(i => ({ id: ids[i], text: STEPS[i] }));
const question = {
  question_id: "Q174", question: "폭스바이러스의 복제주기 단계는?", concept_id: "C1", tier: "Core", importance: 5, format: "list",
  retrieval_direction: "direct", source_refs: [], conflict_id: "", options: [], matching_left: [], matching_right: [], sequence_items: [],
  order_items: items,
  // 순서형 문항에는 서버가 선지를 붙이지 않는다. 혹시 남아 있어도 화면은 순서 맞추기를 쓴다.
  mcq_choices: [{ id: "k1", text: "역전사" }],
};
const view = (answered = false): RootView => ({
  sessionId: "s1", revision: "v1", version: 1, day: "2026-11-18", policy: {} as RootView["policy"], position: 0, count: 3,
  finished: false, blocked: null, canUndo: false, mapSeen: false, summary: {} as RootView["summary"],
  task: { id: "t1", question: question as never, response: null, attempted: answered ? true : null, helped: false,
    answer: answered ? { answer: STEPS.join("; "), answerUnits: STEPS, answerPairs: [], correctOrder: [], correctOptionIds: [],
      orderCorrectIds: ids, medicalReview: null, slides: [] } as never : null },
});
const pool = () => Array.from(document.querySelectorAll<HTMLButtonElement>(".mq-order-pool .bank-option"));
const placedRow = () => Array.from(document.querySelectorAll(".mq-order-placed ol li")).map(li => li.textContent);

try {
  try { localStorage.clear(); } catch { /* storage may be blocked */ }
  const { RootSolve } = await import("../src/bank/RootSolve");
  const actions: RootAction[] = [];
  let root = createRoot(document.getElementById("root")!);
  const render = (v: RootView, scope: string) => root.render(<MemoryRouter><RootSolve view={v} scope={scope} disabled={false} advancing={false}
    onAction={a => actions.push(a)} onToday={() => {}} onError={() => {}} /></MemoryRouter>);

  // 객관식 모드: 처음부터 순서 맞추기. 「모두 고르기」 선지는 나오지 않는다.
  localStorage.setItem("studyez:main-quiz-mode", "mcq");
  render(view(), "mcq");
  await tick();
  check(pool().length === 7, "mcq mode: all seven shuffled steps are shown");
  check(pool()[0].textContent?.startsWith("1 DNA 복제"), "steps keep the server's shuffled order, numbered from 1");
  check(!document.body.textContent?.includes("역전사") && !document.body.textContent?.includes("모두 고르세요"), "no multi-select choices");
  press("2"); await tick(); press("4"); await tick();     // 세포 진입, 초기 전사
  check(placedRow().join("|") === "세포 진입|초기 전사", "number keys place steps in order");
  check(pool()[1].textContent?.includes("1번째") && pool()[3].textContent?.includes("2번째"), "placed steps show their position");
  press("2"); await tick();
  check(placedRow().join("|") === "초기 전사", "the same number takes that step back out");
  press("Backspace"); await tick();
  check(placedRow().length === 0, "Backspace removes the last step");
  for (const n of ["2", "4", "6", "1", "5", "3", "7"]) { press(n); await tick(); }
  check(placedRow().join("|") === "세포 진입|초기 전사|추가 탈외피|DNA 복제|입자 조립|방출|후기 유전자 발현", "all seven placed");
  check(!actions.length, "placing records no event");
  press(" "); await tick();
  const sent = actions.at(-1);
  check(sent?.kind === "reveal" && sent.response === "순서: o0 → o1 → o2 → o3 → o5 → o6 → o4", "Space reveals with the placed IDs in order");
  check(sent?.kind === "reveal" && sent.choicesShown === false, "mcq mode: the ordering screen counts like the mcq-mode choices (not helped)");

  // 답면: 같은 화면 상태에서 답을 받았을 때 자리별 비교.
  root.render(<MemoryRouter><RootSolve view={view(true)} scope="mcq" disabled={false} advancing={false}
    onAction={a => actions.push(a)} onToday={() => {}} onError={() => {}} /></MemoryRouter>);
  await tick();
  check(document.querySelector(".mq-order-compare"), "answer shows the position-by-position comparison");
  check(document.body.textContent?.includes("맞은 자리 4 / 전체 7"), "four of seven positions are right");
  check(document.querySelectorAll(".mq-order-compare li.is-wrong").length === 3, "three positions are marked wrong");
  const count = actions.length;
  press("3"); await tick();
  check(actions.length === count + 1 && actions.at(-1)?.kind === "rate" && actions.at(-1)?.selfRating === "Good", "after reveal, number keys still rate");

  // 주관식 모드: 접힌 채로 시작, V로 순서 맞추기를 편다. 편 풀이는 도움받은 풀이로 남는다.
  // 모드는 화면을 열 때 한 번 읽는다 — 새로 연다.
  localStorage.setItem("studyez:main-quiz-mode", "recall");
  root.unmount();
  root = createRoot(document.getElementById("root")!);
  render(view(), "recall");
  await tick();
  check(!pool().length, "recall mode: the ordering screen starts closed");
  const toggle = () => Array.from(document.querySelectorAll<HTMLButtonElement>(".mq-card > button")).map(b => b.textContent).join();
  check(toggle().startsWith("순서 맞추기"), "recall mode offers 순서 맞추기 (V)");
  press("2"); await tick();
  check(!document.querySelector(".mq-order-placed"), "numbers do nothing while closed");
  key({ key: "v", code: "KeyV" }); await tick();
  check(pool().length === 7 && toggle().startsWith("순서 맞추기 접기"), "V opens it");
  press("2"); await tick();
  key({ key: "v", code: "KeyV" }); await tick();
  check(!pool().length, "V again folds it");
  key({ key: "v", code: "KeyV" }); await tick();
  check(placedRow().length === 0, "folding clears what was placed");
  press("2"); await tick();
  press(" "); await tick();
  check(actions.at(-1)?.kind === "reveal" && actions.at(-1)?.response === "순서: o0" && actions.at(-1)?.choicesShown === true,
    "recall mode: reveal sends the order and that it was opened");
  results.push("ALL PASSED");
  document.getElementById("results")!.textContent = results.join("\n");
} catch (error) { document.getElementById("results")!.textContent = results.join("\n") + `\nFAIL ${String(error)}`; }

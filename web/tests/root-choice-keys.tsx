/** Main-Quiz 객관식(2026-11-12): 선지 머리표 1·2·3, 답 보기 전 1–4 선택, 5 제외, 답 뒤 1–4 평가, 답 뒤 스페이스 무시, Z·Ctrl+Z 되돌리기. */
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

  // 단답 「선지 보기」(#118): 펴기 전에는 1–4가 아무것도 고르지 않고, V로 편 뒤에는 그 선지 번호를 고른다.
  const recallView = view("mcq");
  recallView.task!.question = { ...question("mcq"), format: "basic", options: [],
    recall_choices: [{ id: "A", text: "가" }, { id: "B", text: "나" }, { id: "C", text: "다" }] } as never;
  render(recallView, "recall");
  await tick();
  press("2"); await tick();
  check(!document.querySelector(".bank-option") && !picked().length, "recall choices: numbers do nothing while closed");
  (document.activeElement ?? document.body).dispatchEvent(new KeyboardEvent("keydown", { key: "v", code: "KeyV", bubbles: true }));
  await tick();
  check(Array.from(document.querySelectorAll(".bank-option b")).map(b => b.textContent).join() === "1,2,3", "recall choices: V opens them numbered 1·2·3");
  press("2"); await tick();
  check(picked().join() === "2", "recall choices: key 2 picks the second");
  // 2026-11-12: 편 선지는 V 한 번 더, Z·Ctrl+Z로 다시 접는다. 고른 것은 비우고, 본 기록은 남는다. 서버 되돌리기는 부르지 않는다.
  const key = (init: KeyboardEventInit) => (document.activeElement ?? document.body).dispatchEvent(new KeyboardEvent("keydown", { bubbles: true, cancelable: true, ...init }));
  const open = () => !!document.querySelector(".bank-option");
  const toggleButton = () => Array.from(document.querySelectorAll<HTMLButtonElement>(".mq-card > button")).map(b => b.textContent).join();
  check(toggleButton().startsWith("선지 접기"), "recall choices: open choices offer 선지 접기");
  const undoCount = actions.length;
  key({ key: "v", code: "KeyV" }); await tick();
  check(!open() && !picked().length && toggleButton().startsWith("선지 보기"), "recall choices: V again folds them and clears the pick");
  key({ key: "ㅍ", code: "KeyV" }); await tick();
  check(open() && !picked().length, "recall choices: V reopens them (Korean IME too), nothing picked");
  press("2"); await tick();
  key({ key: "z", code: "KeyZ", ctrlKey: true }); await tick();
  check(!open() && !picked().length, "recall choices: Ctrl+Z folds them");
  key({ key: "v", code: "KeyV" }); await tick();
  key({ key: "z", code: "KeyZ" }); await tick();
  check(!open(), "recall choices: Z folds them");
  check(actions.length === undoCount, "folding records nothing and does not call server undo");
  press(" "); await tick();
  check(actions.at(-1)?.kind === "reveal" && actions.at(-1)?.response === "" && actions.at(-1)?.choicesShown === true,
    "recall choices: folded before reveal still records that choices were seen");
  render({ ...recallView }, "recall-again"); await tick();
  key({ key: "v", code: "KeyV" }); await tick();
  press("2"); await tick();
  press(" "); await tick();
  check(actions.at(-1)?.kind === "reveal" && actions.at(-1)?.response === "선택: B" && actions.at(-1)?.choicesShown === true,
    "recall choices: reveal sends the saved ID and that choices were shown");

  render(view("multi_select"), "multi");
  await tick();
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

  // 2026-11-12: 답을 본 뒤 스페이스는 쪽을 내리지 않는다(아래 바가 움직였다). 누르고 있어도.
  const space = (repeat = false) => { const e = new KeyboardEvent("keydown", { key: " ", code: "Space", bubbles: true, cancelable: true, repeat });
    (document.activeElement ?? document.body).dispatchEvent(e); return e.defaultPrevented; };
  const before = actions.length;
  check(space() && actions.length === before, "after reveal, Space is swallowed and records nothing");
  check(space(true), "held Space is swallowed too");

  // 되돌리기: Z·Ctrl+Z·⌘+Z, 한글 입력 상태(KeyZ, key ㅋ), 버튼에 포커스가 있어도. Ctrl+Z는 입력칸에서는 브라우저 몫.
  const undoView = view("mcq", true); undoView.canUndo = true;
  render(undoView, "undo"); await tick();
  const undo = (init: KeyboardEventInit, target: Element = document.activeElement ?? document.body) => {
    const n = actions.length; target.dispatchEvent(new KeyboardEvent("keydown", { bubbles: true, cancelable: true, ...init }));
    return actions.length === n + 1 && actions.at(-1)?.kind === "undo";
  };
  check(undo({ key: "z", code: "KeyZ" }), "Z undoes");
  check(undo({ key: "z", code: "KeyZ", ctrlKey: true }), "Ctrl+Z undoes");
  check(undo({ key: "z", code: "KeyZ", metaKey: true }), "Cmd+Z undoes");
  check(undo({ key: "ㅋ", code: "KeyZ" }), "Z with the Korean IME on undoes (by key position)");
  check(undo({ key: "z", code: "KeyZ", ctrlKey: true }, document.querySelector(".quiz-undo")!), "Ctrl+Z undoes while a button has focus");
  check(!undo({ key: "z", code: "KeyZ", altKey: true }), "Alt+Z does nothing");
  const input = document.body.appendChild(document.createElement("input"));
  check(!undo({ key: "z", code: "KeyZ", ctrlKey: true }, input), "Ctrl+Z inside a text field is left to the browser");
  input.remove();
  check(!undo({ key: "c", code: "KeyC", ctrlKey: true }), "other Ctrl shortcuts are left alone");
  const noUndo = view("mcq", true);
  render(noUndo, "no-undo"); await tick();
  check(!undo({ key: "z", code: "KeyZ", ctrlKey: true }), "nothing to undo: Ctrl+Z records nothing");
  results.push("ALL PASSED");
  document.getElementById("results")!.textContent = results.join("\n");
} catch (error) { document.getElementById("results")!.textContent = results.join("\n") + `\nFAIL ${String(error)}`; }

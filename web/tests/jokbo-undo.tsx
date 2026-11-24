/** 족보 풀이 z 되돌리기(2026-11-15, 2026-11-24 무제한·답 취소): 한 칸씩 판 처음까지. 표시 → 답 화면 → 고르기 전. 회독은 한 번만. */
import React from "react";
import { createRoot } from "react-dom/client";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import "../src/styles/base.css";
import type { JokboDoc, JokboItem } from "../src/types/jokbo";

const results: string[] = [];
const check = (value: unknown, message: string) => {
  if (!value) throw new Error(message);
  results.push(`PASS ${message}`);
  document.getElementById("results")!.textContent = results.join("\n");
};
const tick = () => new Promise(resolve => setTimeout(resolve, 40));
const press = async (key: string, init: KeyboardEventInit = {}) => {
  const code = key === "z" ? "KeyZ" : key === "Enter" ? "Enter" : `Digit${key}`;
  (document.activeElement ?? document.body).dispatchEvent(new KeyboardEvent("keydown", { key, code, bubbles: true, cancelable: true, ...init }));
  await tick();
};
const count = () => document.querySelector(".pq-count")?.textContent ?? "";
const revealed = () => Boolean(document.querySelector(".jokbo-rate"));
const done = () => Boolean(document.querySelector(".jokbo-done"));

const item = (n: number): JokboItem => ({
  id: `I${n}`, setId: "S", year: 2025, yearLabel: "2025", number: n, stem: `문제 ${n}`,
  choices: ["가", "나", "다"], answers: [2], answerMode: "one_of", selectCount: 1, answerStatus: "key",
  allCorrect: false, verification: "verified", explanation: null,
});
const doc: JokboDoc = {
  schema: "jokbo-solve/1",
  lecture: { eventId: "E1", runId: null, number: "1", title: "시험 강의", date: "2026-11-15", currentProfessors: ["가교수"], professorSource: "notes" },
  sections: [{ kind: "same", professors: ["가교수"], years: ["2025"], itemIds: ["I1", "I2", "I3"] }],
  items: [item(1), item(2), item(3)],
};

const calls: { method: string; path: string; body: unknown }[] = [];
const marks = () => calls.filter(c => c.method === "PUT").map(c => `${c.path.split("/").at(-2)}=${(c.body as { band: string | null }).band}`);
window.fetch = (async (input: RequestInfo | URL, init: RequestInit = {}) => {
  const path = String(input).replace(/^https?:\/\/[^/]+/, "");
  const method = init.method ?? "GET";
  calls.push({ method, path, body: init.body ? JSON.parse(String(init.body)) : null });
  const json = (value: unknown) => new Response(JSON.stringify(value), { status: 200, headers: { "Content-Type": "application/json" } });
  if (path.startsWith("/api/jokbo/marks")) return json({ marks: [] });
  if (path.endsWith("/answer")) return json({ before: { band: null, markedAt: null, lastResult: null, answeredAt: null } });
  if (path === "/api/jokbo/events/E1") return json({ eventId: "E1", audience: "all", items: 3, sameItems: 3, otherItems: 0, unknownItems: 0, doc });
  return json({});
}) as typeof fetch;

try {
  try { localStorage.clear(); } catch { /* storage may be blocked */ }
  const { JokboPage } = await import("../src/jokbo/JokboPage");
  createRoot(document.getElementById("root")!).render(
    <MemoryRouter initialEntries={["/jokbo/E1"]}><Routes><Route path="/jokbo/:eventId" element={<JokboPage />} /></Routes></MemoryRouter>);
  for (let i = 0; i < 20 && !document.querySelector(".mq-start-button"); i++) await tick();
  document.querySelector<HTMLButtonElement>(".mq-start-button")!.click();
  await tick();
  const answers = () => calls.filter(c => c.path.endsWith("/answer")).map(c => `${c.path.split("/").at(-2)}=${(c.body as { result: string }).result}`);
  const undos = () => calls.filter(c => c.path.endsWith("/answer/undo")).map(c => `${c.path.split("/").at(-3)}=${(c.body as { result: string }).result}`);
  const picked = () => document.querySelectorAll(".jokbo-solve [aria-pressed='true'], .jokbo-solve .is-picked").length;
  check(count() === "족보 1 / 3" && !revealed(), "starts on question 1");

  await press("z");
  check(count() === "족보 1 / 3" && !revealed() && !undos().length, "z before any answer does nothing");
  await press("1");
  check(revealed(), "wrong pick reveals the answer");
  await press("z");
  check(count() === "족보 1 / 3" && !revealed(), "z on the answer screen takes back the checked answer");
  check(undos().join() === "I1=wrong", "the answer record is undone on the server with its result");
  check((calls.find(c => c.path.endsWith("/answer/undo"))!.body as { before: { band: null } }).before.band === null,
    "undo sends the before values the answer returned");
  check(!picked(), "the choice is cleared to pick again");
  await press("2");
  check(revealed() && document.querySelector(".jokbo-rate.is-default")?.classList.contains("is-fine"), "re-answering grades the new choice");
  await press("2");
  check(count() === "족보 2 / 3" && !revealed() && marks().join() === "I1=mid", "rating moves to question 2");

  await press("z");
  check(count() === "족보 1 / 3" && revealed(), "z returns to question 1's answer screen");
  check(marks().join() === "I1=mid,I1=null", "z restores the band from before the rating");
  await press("z");
  check(count() === "족보 1 / 3" && !revealed() && undos().join() === "I1=wrong,I1=correct", "a second z takes back that answer too");
  await press("z");
  check(count() === "족보 1 / 3" && !revealed() && undos().length === 2, "z stops at the first question");

  await press("3"); await press("Enter");
  await press("2"); await press("Enter");
  await press("2"); await press("1");
  check(done(), "finishing reaches the done screen");
  const rounds = () => calls.filter(c => c.path.endsWith("/rounds")).length;
  check(rounds() === 1, "the round is recorded once");

  await press("z");
  check(count() === "족보 3 / 3" && revealed(), "z on the done screen returns to the last answer screen");
  await press("z", { ctrlKey: true });
  check(count() === "족보 3 / 3" && !revealed(), "Ctrl+Z also takes back the answer");
  await press("z"); await press("z"); await press("z");
  check(count() === "족보 1 / 3" && revealed(), "z keeps going back across questions");
  check(undos().join() === "I1=wrong,I1=correct,I3=correct,I2=correct", "each taken-back answer is undone once, newest first");
  check(answers().length === 5, "z never re-records an answer");

  await press("Enter");
  await press("2"); await press("Enter");
  await press("2"); await press("Enter");
  check(done() && rounds() === 1, "finishing again does not record a second round");

  results.push("ALL PASSED");
  document.getElementById("results")!.textContent = results.join("\n");
} catch (error) {
  results.push(`FAIL ${(error as Error).message}`);
  document.getElementById("results")!.textContent = results.join("\n");
}

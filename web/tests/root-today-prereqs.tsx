/**
 * Main-Quiz 시작 화면의 「선행 문항」(docs/changes/2026-11-18-prereq-toggle). 서버 없이 RootToday만 그린다.
 * 중요도 칩 줄 끝에 있고, 기본 켜짐, 누르면 지금 칩과 반대 값을 넘기며, 칩이 모두 켜져 있으면 끌 수 없다.
 */
import { createRoot } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import { flushSync } from "react-dom";
import "../src/styles/base.css";
import "../src/bank/main-quiz.css";
import { RootToday } from "../src/bank/RootToday";
import type { RootOverview, RootTierName } from "../src/types/rootLearning";

const results: string[] = [];
const out = () => { document.getElementById("results")!.textContent = results.join("\n"); };
const check = (value: unknown, message: string) => { if (!value) throw new Error(message); results.push(`PASS ${message}`); out(); };
const counts = { Essential: 0, Core: 5, Important: 3, Optional: 4 };
const info = (tiers: RootTierName[], prereqs?: boolean): RootOverview => ({ revision: "r", title: "감염 병리 통합실습", policyReady: true,
  summary: null, sessionId: null, plan: { tasks: [{ task_id: "K1" }], newGoalQuota: 1, days: null, deadline: null,
  habitualTasks: null, preparedUnseen: 1, unpreparedGoals: 0, scopeNote: "" } as never,
  focus: { tiers, counts, ...(prereqs === undefined ? {} : { prereqs }) } });
const toggle = () => [...document.querySelectorAll<HTMLButtonElement>('[aria-label="중요도"] button')].find(b => b.textContent === "선행 문항")!;

try {
  const root = createRoot(document.getElementById("root")!);
  let sent: unknown[] = [];
  const render = (i: RootOverview) => flushSync(() => root.render(<MemoryRouter><main className="root-learning main-quiz-learning">
    <RootToday key={JSON.stringify(i)} info={i} disabled={false} onStart={() => {}} onFocus={(tiers, prereqs) => { sent = [tiers, prereqs]; }} /></main></MemoryRouter>));
  render(info(["Essential", "Core", "Important", "Optional"]));
  check(toggle() && toggle().disabled, "every tier on: the toggle has nothing to narrow");
  render(info(["Essential", "Core", "Important"]));
  check(toggle().getAttribute("aria-pressed") === "true" && !toggle().disabled, "older choice without prereqs: on");
  flushSync(() => toggle().click());
  check(JSON.stringify(sent) === JSON.stringify([["Essential", "Core", "Important"], false]), "click sends the same tiers and off");
  render(info(["Essential", "Core", "Important"], false));
  check(toggle().getAttribute("aria-pressed") === "false", "off is shown");
  flushSync(() => [...document.querySelectorAll<HTMLButtonElement>('[aria-label="중요도"] button')].find(b => b.textContent?.startsWith("Optional"))!.click());
  check(JSON.stringify(sent) === JSON.stringify([["Essential", "Core", "Important", "Optional"], undefined]), "a tier chip leaves prereqs to the server");
  results.push("ALL PASSED"); out();
} catch (error) { results.push(`FAIL ${String(error)}`); out(); }

/**
 * Main-Quiz 시작 화면의 「순서대로/랜덤」(docs/changes/2026-11-15-photo-quiz-shuffle). 서버 없이 RootToday만 그린다.
 * 사진 판(orderChoice)에만 보이고, 고른 값이 시작 버튼으로 넘어가며, 이어 풀 때는 회차의 지금 순서를 먼저 보인다.
 */
import { createRoot } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import { flushSync } from "react-dom";
import "../src/styles/base.css";
import "../src/bank/main-quiz.css";
import { RootToday } from "../src/bank/RootToday";
import type { RootOverview } from "../src/types/rootLearning";

const results: string[] = [];
const out = () => { document.getElementById("results")!.textContent = results.join("\n"); };
const check = (value: unknown, message: string) => { if (!value) throw new Error(message); results.push(`PASS ${message}`); out(); };
const info = (extra: Partial<RootOverview>): RootOverview => ({ revision: "r", title: "감염 병리 통합실습", policyReady: true,
  summary: null, sessionId: null, plan: { tasks: [{ task_id: "K1" }, { task_id: "K2" }], newGoalQuota: 2, days: null, deadline: null,
  habitualTasks: null, preparedUnseen: 2, unpreparedGoals: 0, scopeNote: "" } as never, ...extra });
const group = () => document.querySelector('[aria-label="문항 순서"]');
const pick = (label: string) => [...document.querySelectorAll<HTMLButtonElement>('[aria-label="문항 순서"] button')].find(b => b.textContent === label)!;

try {
  try { localStorage.removeItem("studyez:main-quiz-order"); } catch { /* 없어도 된다 */ }
  const root = createRoot(document.getElementById("root")!);
  let started: unknown = "none";
  const render = (i: RootOverview) => flushSync(() => root.render(<MemoryRouter><main className="root-learning main-quiz-learning">
    <RootToday key={JSON.stringify(i)} info={i} disabled={false} onStart={order => { started = order; }} /></main></MemoryRouter>));
  render(info({}));
  check(!group(), "ordinary revision: no order choice");
  document.querySelector<HTMLButtonElement>(".mq-start-button")!.click();
  check(started === undefined, "ordinary revision: start sends no order");
  render(info({ orderChoice: true }));
  check(group() && pick("순서대로").getAttribute("aria-checked") === "true", "photo revision: 순서대로 is the default");
  flushSync(() => pick("랜덤").click());
  check(pick("랜덤").getAttribute("aria-checked") === "true", "랜덤 can be chosen");
  document.querySelector<HTMLButtonElement>(".mq-start-button")!.click();
  check(started === "random", "start sends the chosen order");
  render(info({ orderChoice: true, sessionId: "s1", order: "ordered" }));
  check(pick("순서대로").getAttribute("aria-checked") === "true", "resume shows the session's current order");
  render(info({ orderChoice: true }));
  check(pick("랜덤").getAttribute("aria-checked") === "true", "the choice is remembered on this device");
  results.push("ALL PASSED"); out();
} catch (error) { results.push(`FAIL ${String(error)}`); out(); }

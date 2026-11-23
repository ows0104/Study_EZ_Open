/**
 * Main-Quiz 시작 화면의 숫자는 카드(문항) 수다(docs/changes/2026-11-24-lecture-list-block-scope,
 * 사용자 「기준을 학습 목표 개수로 표기하지 말고 카드 수로」). 서버 없이 RootToday만 그린다.
 * 숫자 칸·막대·오늘 추천은 questionProgress, 접은 자세히 보기만 목표 기준임을 밝힌다.
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
const summary = { total: 12, learned: 5, recalled: 2, score: 20, unseen: 7, unready: 0, importantUnseen: 3, newToday: 1,
  recallChange: 0, recallLearningChange: 0, recallTimeChange: 0, targets: [] };
const info = (extra: Partial<RootOverview>): RootOverview => ({ revision: "r", title: "감염성 질환의 병리 1", policyReady: true,
  summary, sessionId: null,
  plan: { tasks: Array.from({ length: 9 }, (_, i) => ({ task_id: `K${i}` })), newGoalQuota: 2, days: 3, deadline: "2026-11-27",
    habitualTasks: null, preparedUnseen: 40, unpreparedGoals: 0, scopeNote: "" } as never,
  questionProgress: { total: 57, unseen: 40, recognized: 9, retrieving: 6, retained: 2, reviewDue: 3, newToday: 6 }, ...extra });
const stats = () => [...document.querySelectorAll(".mq-stats > div")].map(d => d.textContent);

try {
  const root = createRoot(document.getElementById("root")!);
  const render = (i: RootOverview) => flushSync(() => root.render(<MemoryRouter><main className="root-learning main-quiz-learning">
    <RootToday key={JSON.stringify(i)} info={i} disabled={false} onStart={() => {}} /></main></MemoryRouter>));
  render(info({}));
  if (new URLSearchParams(location.search).has("view")) throw "view";  // 눈으로 볼 때: 첫 화면에서 멈춘다.
  check(JSON.stringify(stats()) === JSON.stringify(["전체 카드57", "본 카드17/57", "회상 가능8/57"]), `card stats: ${stats()}`);
  check(document.querySelector(".mq-progress")!.getAttribute("aria-label") === "본 카드 17/57 · 회상 가능 8/57", "bar is per card");
  check(document.querySelector(".mq-today-text p")!.textContent === "새 카드 6장 · 복습 3장", "today: new and review cards");
  // 「첫 학습 목표일 2026-11-27」은 날짜라 남는다. 개수 표기(학습 목표 N·새 목표 N개·고유 목표)만 없어야 한다.
  check(!/학습 목표\s*\d|새 목표|고유 목표/.test(document.querySelector(".mq-start")!.textContent!.replace(document.querySelector(".mq-more")!.textContent!, "")),
    "no goal counts outside the folded details");
  check(/^학습 목표 기준 · 고유 목표 12개/.test(document.querySelector(".mq-summary-line")!.textContent!), "folded details say they count goals");
  // An older API without newToday still names the day's load in cards.
  render(info({ questionProgress: { total: 57, unseen: 40, recognized: 9, retrieving: 6, retained: 2, reviewDue: 3 } }));
  check(document.querySelector(".mq-today-text p")!.textContent === "오늘 카드 9장", "older API: today's card count");
  render(info({ questionProgress: undefined }));
  check(!document.querySelector(".mq-stats"), "no card counts: no stat row");
  results.push("ALL PASSED"); out();
} catch (error) { if (error !== "view") { results.push(`FAIL ${String(error)}`); out(); } else document.getElementById("results")!.remove(); }

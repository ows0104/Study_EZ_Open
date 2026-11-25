/**
 * Main-Quiz 시작 화면의 중요도 범위(docs/changes/2026-11-25-lecture-tier-range)와 「선행 문항」(2026-11-18-prereq-toggle).
 * 서버 없이 RootToday만 그린다. 범위: 선분 4개·점 5개, 손잡이 둘은 점 위, 놓을 때 한 번 저장, 늘 한 선분 이상,
 * 선분 이름을 누르면 가까운 손잡이가 와서 그 선분을 넣는다.
 * 선행 문항: 범위 옆, 기본 켜짐, 누르면 지금 범위와 반대 값을 넘기며, 모두 고르면 끌 수 없다.
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
const ALL: RootTierName[] = ["Essential", "Core", "Important", "Optional"];
const NARROW: RootTierName[] = ["Essential", "Core", "Important"];
const info = (tiers: RootTierName[], prereqs?: boolean): RootOverview => ({ revision: "r", title: "감염 병리 통합실습", policyReady: true,
  summary: null, sessionId: null, plan: { tasks: [{ task_id: "K1" }], newGoalQuota: 1, days: null, deadline: null,
  habitualTasks: null, preparedUnseen: 1, unpreparedGoals: 0, scopeNote: "" } as never,
  focus: { tiers, counts, ...(prereqs === undefined ? {} : { prereqs }) } });
const buttons = () => [...document.querySelectorAll<HTMLButtonElement>('[aria-label="중요도"] button')];
const toggle = () => buttons().find(b => b.textContent === "선행 문항")!;
const stop = (tier: string) => buttons().find(b => b.textContent?.startsWith(tier))!;
const thumb = (which: "시작" | "끝") => document.querySelector<HTMLInputElement>(`input[aria-label="중요도 ${which}"]`)!;
const tick = () => new Promise(r => setTimeout(r, 0));
const setValue = (el: HTMLInputElement, v: number) => {
  Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!.call(el, String(v));
  el.dispatchEvent(new Event("input", { bubbles: true }));
};
const release = (el: HTMLInputElement) => el.dispatchEvent(new PointerEvent("pointerup", { bubbles: true }));
const inside = () => buttons().filter(b => b.classList.contains("is-in")).map(b => b.textContent!.replace(/\d+$/, ""));

(async () => {
  try {
    const root = createRoot(document.getElementById("root")!);
    let sent: unknown[] | null = null, renders = 0;
    const render = (i: RootOverview) => { sent = null; flushSync(() => root.render(<MemoryRouter><main className="root-learning main-quiz-learning">
      <RootToday key={++renders} info={i} disabled={false} onStart={() => {}} onFocus={(tiers, prereqs) => { sent = [tiers, prereqs]; }} /></main></MemoryRouter>)); };

    // ── 범위 ──
    render(info(NARROW));
    check(thumb("시작").value === "0" && thumb("끝").value === "3", "Essential~Important: handles on points 0 and 3");
    check(document.querySelectorAll(".mq-range-track > span").length === 5 && document.querySelectorAll(".mq-range-stops button").length === 4, "four segments, five points");
    check(JSON.stringify(inside()) === JSON.stringify(NARROW), "stops inside the range are marked");
    setValue(thumb("끝"), 4); await tick();
    check(sent === null && thumb("끝").value === "4", "dragging moves the handle without saving");
    release(thumb("끝")); await tick();
    check(JSON.stringify(sent) === JSON.stringify([ALL, undefined]), "release saves once: every tier, prereqs left to the server");

    render(info(NARROW));
    setValue(thumb("시작"), 4); await tick();
    check(thumb("시작").value === "2", "the start handle stops one segment before the end");
    release(thumb("시작")); await tick();
    check(JSON.stringify(sent) === JSON.stringify([["Important"], undefined]), "handles on neighbouring points: that segment's tier alone");

    render(info(NARROW));
    release(thumb("끝")); thumb("끝").dispatchEvent(new FocusEvent("blur")); await tick();
    check(sent === null, "release without a change saves nothing");

    render(info(["Essential", "Important"]));
    check(thumb("시작").value === "0" && thumb("끝").value === "3" && sent === null, "older non-contiguous choice shows its span, unsaved");
    setValue(thumb("끝"), 2); setValue(thumb("끝"), 3); release(thumb("끝")); await tick();
    check(JSON.stringify(sent) === JSON.stringify([NARROW, undefined]), "first move saves the contiguous span");

    render(info(["Optional"]));
    check(thumb("시작").value === "3" && thumb("끝").value === "4", "Optional alone: the last segment");
    setValue(thumb("끝"), 3); await tick();
    check(thumb("끝").value === "4", "the end handle keeps at least one segment");

    render(info(NARROW));
    flushSync(() => stop("Optional").click());
    check(JSON.stringify(sent) === JSON.stringify([ALL, undefined]), "a stop outside the range extends the nearer end");
    render(info(ALL));
    flushSync(() => stop("Core").click());
    check(JSON.stringify(sent) === JSON.stringify([["Core", "Important", "Optional"], undefined]), "a stop inside moves the nearer end");

    // ── 선행 문항 ──
    render(info(ALL));
    check(toggle() && toggle().disabled, "every tier on: the toggle has nothing to narrow");
    render(info(NARROW));
    check(toggle().getAttribute("aria-pressed") === "true" && !toggle().disabled, "older choice without prereqs: on");
    flushSync(() => toggle().click());
    check(JSON.stringify(sent) === JSON.stringify([NARROW, false]), "click sends the same tiers and off");
    render(info(NARROW, false));
    check(toggle().getAttribute("aria-pressed") === "false", "off is shown");
    results.push("ALL PASSED"); out();
  } catch (error) { results.push(`FAIL ${String(error)}`); out(); }
})();

/**
 * Main-Quiz 풀이의 아래 바(2026-11-12 사용자: 「스페이스를 누르면 아래 바 위치가 위아래로 움직임. 고정해줘」).
 * 실제 화면 틀(app-shell > app-main > main-quiz-learning) 안에서, 짧은 문제·답을 연 긴 화면·스크롤 끝·스페이스 뒤에
 * 바의 아래 끝이 언제나 화면 아래 16px인지 잰다.
 */
import { createRoot } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import "../src/styles/base.css";
import "../src/bank/main-quiz.css";
import type { RootView } from "../src/types/rootLearning";

const results: string[] = [];
const check = (value: unknown, message: string) => {
  if (!value) throw new Error(message);
  results.push(`PASS ${message}`);
  document.getElementById("results")!.textContent = results.join("\n");
};
const frame = () => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
const gap = () => Math.round(innerHeight - document.querySelector(".main-quiz-solve .quiz-bar")!.getBoundingClientRect().bottom);
const long = Array.from({ length: 40 }, (_, i) => `${i + 1}. 긴 해설 줄 — 화면보다 길게 만든다.`);
const view = (answered: boolean): RootView => ({
  sessionId: "s1", revision: "v1", version: 1, day: "2026-11-12", policy: {} as RootView["policy"], position: 0, count: 3,
  finished: false, blocked: null, canUndo: true, mapSeen: false, summary: {} as RootView["summary"],
  task: { id: "t1", question: { question_id: "Q1", question: "짧은 문제?", concept_id: "C1", tier: "Core", importance: 5, format: "basic",
    retrieval_direction: "recall", source_refs: [], conflict_id: "", options: [], matching_left: [], matching_right: [], sequence_items: [] } as never,
    response: null, attempted: answered ? true : null, helped: false,
    answer: answered ? { answer: long.join("\n"), answerUnits: long, answerPairs: [], correctOrder: [], correctOptionIds: [],
      medicalReview: null, slides: [] } as never : null },
});

try {
  const { RootSolve } = await import("../src/bank/RootSolve");
  const root = createRoot(document.getElementById("root")!);
  const render = (v: RootView) => root.render(<MemoryRouter><main className="root-learning main-quiz-learning">
    <RootSolve view={v} scope="bar" disabled={false} advancing={false} onAction={() => {}} onToday={() => {}} onError={() => {}} />
  </main></MemoryRouter>);
  render(view(false)); await frame(); scrollTo(0, 0); await frame();
  const first = gap();
  check(first === 16, `short question: bar 16px above the bottom (got ${first})`);
  render(view(true)); await frame();
  check(gap() === 16, `answer opened (long page): bar stays (got ${gap()})`);
  const e = new KeyboardEvent("keydown", { key: " ", code: "Space", bubbles: true, cancelable: true });
  document.querySelector<HTMLElement>(".mq-solve-head h2, .main-quiz-question-heading")?.dispatchEvent(e);
  check(e.defaultPrevented, "Space after the answer does not scroll the page");
  scrollTo(0, document.documentElement.scrollHeight); await frame();
  check(scrollY > 0 && gap() === 16, `scrolled to the end: bar stays (got ${gap()}, scrollY ${scrollY})`);
  scrollTo(0, 200); await frame();
  check(gap() === 16, `middle of the page: bar stays (got ${gap()})`);
  render(view(false)); await frame(); scrollTo(0, 0); await frame();
  check(gap() === 16, `next short question: bar stays (got ${gap()})`);
  results.push("ALL PASSED");
  document.getElementById("results")!.textContent = results.join("\n");
} catch (error) { document.getElementById("results")!.textContent = results.join("\n") + `\nFAIL ${String(error)}`; }

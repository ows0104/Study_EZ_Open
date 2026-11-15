/**
 * Main-Quiz 「선행 문항」 표시(docs/changes/2026-11-16-prereq-question-only): 뒤 과제의 문항 선행이라 들어온 과제에만
 * 태그와 설명이 붙는다. 옛 서버(필드 없음)·스스로 고른 과제에는 없다.
 */
import { createRoot } from "react-dom/client";
import { flushSync } from "react-dom";
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
const view = (prerequisite?: boolean): RootView => ({
  sessionId: "s1", revision: "v1", version: 1, day: "2026-11-16", policy: {} as RootView["policy"], position: 0, count: 3,
  finished: false, blocked: null, canUndo: false, mapSeen: false, summary: {} as RootView["summary"],
  task: { id: "t1", question: { question_id: "Q3", question: "배양균 도말과 조직 검체에 쓰는 염색법은?", concept_id: "C1", tier: "Optional",
    importance: 0, format: "basic", retrieval_direction: "recall", source_refs: [], conflict_id: "", options: [], matching_left: [],
    matching_right: [], sequence_items: [] } as never, response: null, attempted: null, helped: false, answer: null,
    ...(prerequisite === undefined ? {} : { prerequisite }) },
});

try {
  const { RootSolve } = await import("../src/bank/RootSolve");
  const host = document.getElementById("root")!;
  const root = createRoot(host);
  const render = (v: RootView) => flushSync(() => root.render(<MemoryRouter><main className="root-learning main-quiz-learning">
    <RootSolve view={v} scope="tag" disabled={false} advancing={false} onAction={() => {}} onToday={() => {}} onError={() => {}} />
  </main></MemoryRouter>));
  render(view(true));
  const note = host.querySelector(".mq-prerequisite");
  check(note?.querySelector(".tag")?.textContent === "선행 문항", "brought-in prerequisite shows the 「선행 문항」 tag");
  check(note?.textContent?.includes("제외해도 뒤 문제는 그대로 나옵니다"), "the note says excluding it does not hold back what follows");
  render(view(false));
  check(!host.querySelector(".mq-prerequisite"), "a task chosen for itself has no tag");
  render(view());
  check(!host.querySelector(".mq-prerequisite"), "an older server without the field shows no tag");
  if (new URLSearchParams(location.search).has("preview")) {
    render(view(true));
    document.getElementById("results")!.style.display = "none";
  } else {
    results.push("ALL PASSED");
    document.getElementById("results")!.textContent = results.join("\n");
  }
} catch (error) { document.getElementById("results")!.textContent = results.join("\n") + `\nFAIL ${String(error)}`; }

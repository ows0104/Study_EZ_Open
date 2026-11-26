/** 족보 강의별 진입 화면 순서(2026-11-26 「오래된 해부터」): 기본은 최신부터, 버튼으로 오래된 해부터, 강의별로 기억. */
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

const item = (id: string, year: number): JokboItem => ({
  id, setId: "S", year, yearLabel: String(year), number: 1, stem: `문제 ${id}`,
  choices: ["가", "나", "다"], answers: [2], answerMode: "one_of", selectCount: 1, answerStatus: "key",
  allCorrect: false, verification: "verified", explanation: null,
});
const doc: JokboDoc = {
  schema: "jokbo-solve/1",
  lecture: { eventId: "E1", runId: null, number: "1", title: "시험 강의", date: "2026-11-26", currentProfessors: ["가교수"], professorSource: "notes" },
  sections: [
    { kind: "same", professors: ["가교수"], years: ["2025", "2021"], itemIds: ["A25", "A21"] },
    { kind: "other", professors: ["나교수"], years: ["2023", "2018"], itemIds: ["B23", "B18"] },
  ],
  items: [item("A25", 2025), item("A21", 2021), item("B23", 2023), item("B18", 2018)],
};
window.fetch = (async (input: RequestInfo | URL) => {
  const path = String(input).replace(/^https?:\/\/[^/]+/, "");
  const json = (value: unknown) => new Response(JSON.stringify(value), { status: 200, headers: { "Content-Type": "application/json" } });
  if (path.startsWith("/api/jokbo/marks")) return json({ marks: [] });
  if (path === "/api/jokbo/events/E1") return json({ eventId: "E1", audience: "all", items: 4, sameItems: 2, otherItems: 2, unknownItems: 0, doc });
  return json({});
}) as typeof fetch;

const button = (label: string) => [...document.querySelectorAll<HTMLButtonElement>(".jokbo-start button")].find(b => b.textContent?.startsWith(label));
const stem = () => document.querySelector(".jokbo-solve")?.textContent ?? "";

try {
  try { localStorage.clear(); } catch { /* storage may be blocked */ }
  const { JokboPage } = await import("../src/jokbo/JokboPage");
  const mount = () => {
    const host = document.getElementById("root")!;
    const root = createRoot(host);
    root.render(<MemoryRouter initialEntries={["/jokbo/E1"]}><Routes><Route path="/jokbo/:eventId" element={<JokboPage />} /></Routes></MemoryRouter>);
    return root;
  };
  let root = mount();
  for (let i = 0; i < 20 && !document.querySelector(".mq-start-button"); i++) await tick();
  check(button("최신 해부터")?.getAttribute("aria-checked") === "true", "default order is newest first");
  button("다른 교수까지")!.click();
  await tick();
  button("오래된 해부터")!.click();
  await tick();
  check(button("오래된 해부터")?.getAttribute("aria-checked") === "true", "oldest-first can be picked");
  check(document.querySelector(".mq-card-count")?.textContent === "4", "order does not change the count");
  document.querySelector<HTMLButtonElement>(".mq-start-button")!.click();
  await tick();
  check(stem().includes("문제 B18") && stem().includes("2018"), "oldest year (other professor) comes first");

  root.unmount();
  root = mount();
  for (let i = 0; i < 20 && !document.querySelector(".mq-start-button"); i++) await tick();
  check(button("오래된 해부터")?.getAttribute("aria-checked") === "true", "order is remembered per lecture");
  results.push("ALL PASSED");
  document.getElementById("results")!.textContent = results.join("\n");
} catch (error) {
  results.push(`FAIL ${(error as Error).message}`);
  document.getElementById("results")!.textContent = results.join("\n");
}

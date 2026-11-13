import React from "react";
import { createRoot, type Root } from "react-dom/client";
import { flushSync } from "react-dom";
import { AnswerBody } from "../src/bank/BankQuestion";
import type { BankAnswer, BankQuestion } from "../src/types/bank";
import fixture from "./source-notes-fixture.json";
import "../src/styles/base.css";

// 2026-11-13: Main-Quiz(reviewInline=false)는 자료 충돌을 답 위 배지로 띄운다. Quiz Bank(기본)는 그대로.
const results: string[] = [];
const check = (value: unknown, message: string) => {
  if (!value) throw new Error(message);
  results.push(`PASS ${message}`);
  document.getElementById("results")!.textContent = results.join("\n");
};
const q = fixture.question as BankQuestion;
const base = fixture.answer as BankAnswer;
const host = document.getElementById("root")!;
let root: Root | null = null;
const show = (answer: BankAnswer, reviewInline?: boolean) => {
  root?.unmount();
  root = createRoot(host);
  flushSync(() => root!.render(<div className="quiz"><AnswerBody question={q} answer={answer} reviewInline={reviewInline} /></div>));
  return host.querySelector(".bank-conflict-badge");
};
try {
  let badge = show(base, false);
  check(badge?.textContent?.includes("자료 충돌"), "main-quiz: recorded conflict shows the badge");
  check(badge?.querySelector(".bank-conflict-judgment")?.textContent?.includes("권고에서 제외되었다")
    && !badge?.textContent?.includes("자료 1"), "main-quiz: badge carries only the 판단 line");
  check(host.firstElementChild?.firstElementChild === badge, "main-quiz: badge sits above the answer");
  check(!host.querySelector(".bank-source-note"), "main-quiz: full comparison stays in the folded record");

  check(!show(base)?.isConnected && host.querySelector(".bank-source-note"), "quiz bank: inline comparison unchanged, no badge");
  check(!show({ ...base, conflict: "" }, false), "main-quiz: no conflict, no badge");
  check(!show({ ...base, conflict: "   " }, false), "main-quiz: blank conflict, no badge");

  badge = show({ ...base, conflict: "", evidenceStatus: { category: "source_conflict", reason: "강의록과 족보 정답이 다르다." } }, false);
  check(badge?.querySelector(".bank-conflict-judgment")?.textContent?.includes("족보 정답이 다르다"), "main-quiz: evidence status 자료 충돌 alone shows the badge");
  check(!show({ ...base, conflict: "", evidenceStatus: { category: "partial_support", reason: "일부 부족" } }, false),
    "main-quiz: other evidence statuses do not show the badge");

  badge = show({ ...base, conflict: "강의록은 B형도 재분절된다고 하고\n족보 정답은 일어나지 않는다고 한다." }, false);
  check(badge?.querySelector(".bank-conflict-judgment")?.textContent?.includes("B형도 재분절된다고 하고")
    && !badge?.textContent?.includes("족보 정답은"), "main-quiz: legacy free-text conflict shows its first line");

  if (new URLSearchParams(location.search).has("preview")) {
    show(base, false);
    document.getElementById("results")!.style.display = "none";
  } else {
    results.push("ALL PASSED");
    document.getElementById("results")!.textContent = results.join("\n");
  }
} catch (error) { document.getElementById("results")!.textContent = results.join("\n") + `\nFAIL ${String(error)}`; }

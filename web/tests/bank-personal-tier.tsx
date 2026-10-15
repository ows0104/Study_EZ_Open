import { createRoot } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import "../src/styles/base.css";

const results: string[] = [];
const check = (ok: unknown, message: string) => {
  if (!ok) throw new Error(message);
  results.push(`PASS ${message}`);
  document.getElementById("results")!.textContent = results.join("\n");
};
const waitFor = async (test: () => unknown) => {
  for (let i = 0; i < 500; i++) { if (test()) return; await new Promise(resolve => setTimeout(resolve, 10)); }
  throw new Error("Timed out");
};
const batch = new URLSearchParams(location.search).has("batch");
const base = batch ? "/api/lectures/actual/lecture/bank" : "/api/test/bank";
let tier = "Core", personal = false, fail = true, saves = 0, nexts = 0, rates = 0;
const question = () => ({ question_id: "Q1", concept_id: "C1", question: "중요도 변경 테스트", format: "mcq", tier,
  originalTier: "Core", personalTier: personal, targetMastery: personal ? tier === "Core" ? .85 : tier === "Important" ? .78 : .55 : .4,
  advanced: true, retrieval_direction: "direct", source_refs: [], conflict_id: "",
  options: [{ id: "A", text: "첫째" }, { id: "B", text: "둘째" }], matching_left: [], matching_right: [], sequence_items: [] });
const answer = { answer: "첫째", answerUnits: ["첫째"], explanation: "", correctOptionIds: ["A"], answerPairs: [], correctOrder: [], slides: [] };
window.fetch = async (input, init) => {
  const path = new URL(String(input), location.origin).pathname;
  const body = init?.body ? JSON.parse(String(init.body)) : {};
  let result: unknown, status = 200;
  if (path.endsWith("/next")) {
    nexts++; result = { question: question(), reviewToken: "token", ...(batch ? { lecture: { subject: "actual", runId: "lecture" } } : {}) };
  } else if (path.endsWith("/prepare") || path.endsWith("/reveal")) result = answer;
  else if (path.endsWith("/priority")) {
    saves++;
    check(path === base + "/questions/Q1/priority" && body.reviewToken === "token", "saves to the current lecture with its review token");
    await new Promise(resolve => setTimeout(resolve, 70));
    if (fail) { fail = false; status = 503; result = { detail: "저장 실패 테스트" }; }
    else { tier = body.tier ?? "Core"; personal = body.tier !== null; result = { question: question(), rescheduled: true }; }
  } else if (path.endsWith("/rate")) { rates++; result = {}; }
  else throw new Error(`Unexpected request: ${path}`);
  return new Response(JSON.stringify(result), { status, headers: { "Content-Type": "application/json" } });
};
const choose = (value: string) => {
  const select = document.querySelector<HTMLSelectElement>("select[aria-label='내 문제 중요도']")!;
  select.value = value; select.dispatchEvent(new Event("change", { bubbles: true }));
};
try {
  const { BankSolve } = await import("../src/bank/BankSolve");
  createRoot(document.getElementById("root")!).render(<MemoryRouter><BankSolve base={base}
    lecture={{ subject: "initial", runId: "wrong" }} onFinished={() => {}}
    batch={batch ? { lectures: [{ subject: "actual", runId: "lecture" }], onProgress: () => {} } : undefined} /></MemoryRouter>);
  await waitFor(() => document.querySelector("select"));
  check(document.querySelectorAll("select option").length === 3, "all three tiers are available before revealing the answer");
  check(document.querySelector(".bank-target")?.textContent?.includes("40%"), "shows the server's original target");
  const option = document.querySelector<HTMLButtonElement>(".bank-option")!;
  option.click(); choose("Optional");
  await waitFor(() => document.body.textContent?.includes("저장 실패 테스트"));
  check(document.querySelector<HTMLSelectElement>("select")!.value === "Core" && nexts === 1, "save failure keeps the current tier and question");
  choose("Optional"); choose("Important");
  await waitFor(() => document.body.textContent?.includes("Optional로 저장"));
  check(saves === 2 && document.querySelector<HTMLSelectElement>("select")!.value === "Optional", "duplicate changes are blocked while saving");
  check(document.querySelector(".bank-target")?.textContent?.includes("55%"), "Optional applies its new target immediately");
  check(document.body.textContent?.includes("복습 예정일도 새 목표로 다시 계산했습니다"), "confirms that the existing review date was recalculated");
  check(option.getAttribute("aria-pressed") === "true" && document.body.textContent?.includes("Advanced · 심화") && rates === 0, "picked answer, depth flag, and ungraded state survive tier changes");
  document.querySelector<HTMLButtonElement>(".quiz-submit")!.click();
  await waitFor(() => document.querySelectorAll(".quiz-grade").length === 4
    && !document.querySelector<HTMLSelectElement>("select")!.disabled);
  choose("Important");
  await waitFor(() => document.body.textContent?.includes("Important로 저장"));
  check(document.querySelector(".bank-target")?.textContent?.includes("78%"), "raising priority raises the target");
  check(document.querySelectorAll(".quiz-grade").length === 4 && nexts === 1, "changing priority after reveal keeps the answer visible");
  document.querySelector<HTMLButtonElement>(".bank-tier-reset")!.click();
  await waitFor(() => document.body.textContent?.includes("원래 중요도로 되돌렸습니다"));
  check(document.querySelector<HTMLSelectElement>("select")!.value === "Core" && !document.querySelector(".bank-tier-reset"), "reset restores the shared tier");
  check(document.querySelector(".bank-target")?.textContent?.includes("40%"), "reset restores the original target");
  document.getElementById("results")!.textContent = results.join("\n") + "\nALL PASSED";
} catch (cause) { document.getElementById("results")!.textContent = results.join("\n") + `\nFAIL ${String(cause)}`; }

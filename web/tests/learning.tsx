// Interactive browser fixture: real screen, synthetic data, no account/network writes.
import { createRoot } from "react-dom/client";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import type { LearningAnswer, LearningDashboard, LearningSession } from "../src/types/learning";
import "../src/styles/base.css";

const scenario = new URLSearchParams(location.search).get("scenario");
const mode = scenario === "exam" ? "exam" : scenario === "recall" || scenario === "explanation" ? "extra" : "daily";
let submitted = false, options = Boolean(scenario), assisted = false, complete = false, count = 0;
let submittedAnswer: LearningAnswer = {}, confidence: string | null = null;
const question = { question_id: "Q1", concept_id: "C1", format: scenario === "recall" ? "list" : "mcq", question: scenario === "recall" ? "학습 계획을 세울 때 먼저 확인할 세 가지는?" : "두 개념을 구별할 때 가장 먼저 확인할 것은?", options: scenario === "recall" ? [] : [{ id: "A", text: "두 개념의 차이를 만드는 조건" }, { id: "B", text: "문제에 사용된 보기의 순서" }], matching_left: [], matching_right: [], sequence_items: [], source_refs: [{ source_id: "S1", locator: "p12" }] };
const response = { answer: "A. 두 개념의 차이를 만드는 조건", answerUnits: [], correctOptionIds: ["A"], answerPairs: [], correctOrder: [], optionExplanations: [{ option_id: "A", text: "조건에 따라 결과가 달라지는 이유를 구별합니다." }, { option_id: "B", text: "보기 순서는 지식의 차이를 설명하지 않습니다." }], sourceRefs: question.source_refs, correct: true, confidence: "sure", explanation: "같은 결과처럼 보여도 발생하는 조건이 다를 수 있습니다. 그 차이를 기준으로 묶어 보세요.", minimum: "구별 조건 → 결과" };
if (scenario === "recall") Object.assign(response, { answer: "목표, 공부할 범위, 쓸 수 있는 시간", answerUnits: ["목표", "공부할 범위", "쓸 수 있는 시간"], correctOptionIds: [], optionExplanations: [], explanation: "목표와 범위를 먼저 정한 뒤 쓸 수 있는 시간 안에 분량을 배정합니다.", minimum: "목표 · 범위 · 시간" });
const feedback = () => scenario === "explanation" ? { explanation: response.explanation, minimum: response.minimum }
  : ({ ...response, confidence, correct: scenario === "recall" ? null : submittedAnswer.selected?.[0] === "A" });
const view = (): LearningSession => ({
  sessionId: "demo", mode, status: complete ? "complete" : "active", index: count, total: 2,
  seconds: 60 * count, canUndo: count > 0 && mode !== "exam", token: `token-${count}`,
  lane: mode === "daily" ? count ? "review" : "new" : mode,
  lecture: "강의 흐름과 개념 구별", subject: "local", runId: "demo",
  optionsShown: options, assisted: assisted || scenario === "explanation", submitted,
  question: scenario === "explanation" ? null : { ...question, options: options ? question.options : [] },
  recallPrompt: scenario ? undefined : "두 개념의 차이는 무엇으로 판단하나요?", objective: "개념 구별",
  help: assisted ? { context: "큰 흐름에서 개념을 구별하는 단계입니다.", explanation: response.explanation,
    minimum: response.minimum, rationale: "이 강의의 학습목표입니다.", source_refs: question.source_refs } : null,
  feedback: submitted && mode !== "exam" ? feedback() : null,
  reviewChoices: submitted && mode !== "exam" && scenario !== "explanation"
    ? (["Again", "Hard", "Good", "Easy"] as const).filter(rating => rating === "Again"
      || (!assisted && confidence !== "guess" && (scenario === "recall" || submittedAnswer.selected?.[0] === "A")))
      .map(rating => ({ rating, dueAt: Date.now() + ({ Again: 1, Hard: 1, Good: 2, Easy: 8 }[rating]) * 86400000,
        intervalDays: { Again: 1, Hard: 1, Good: 2, Easy: 8 }[rating] })) : undefined,
  submittedAnswer: submitted ? submittedAnswer : null,
  summary: complete ? { completed: count, graded: scenario === "recall" || scenario === "explanation" ? 0 : count,
    correct: count, freshGraded: 1, freshCorrect: 1, newObjectives: 1, delayedRecall: 1, burden: null } : undefined,
  results: complete && mode === "exam" ? [{ ...feedback(), title: "개념 구별", question, submittedAnswer }] : undefined,
});
const progress = { total: 24, covered: 12, delayedRecall: 4, questionGaps: 1, legacyObjectives: 0 };
const dash: LearningDashboard = { enabled: true, minutes: 60, bufferDays: 3, progress, missingLectures: [{ title: "다음 강의", date: "2026-10-12" }], uncertainRanges: 1, activeSession: null, examQuestions: 6, plan: { budgetSeconds: 3600, estimatedSeconds: 2400, activeSeconds: 600, remaining: 2, complete: false, completed: ["done"], entries: [{ key: "done", lane: "review", seconds: 60 }, { key: "a", lane: "new", seconds: 120 }, { key: "b", lane: "review", seconds: 60 }], infeasible: false, newRequiredMinutes: 20, revision: 1 }, lectures: [{ ...progress, subject: "local", runId: "demo", title: "강의 흐름과 개념 구별" }], objectives: [{ key: "a", title: "두 개념의 구별", lecture: "강의 흐름과 개념 구별", subject: "local", runId: "demo", kind: "discrimination", sourceRefs: question.source_refs, covered: false, related: [] }] };
window.fetch = async (input, init) => {
  const path = new URL(String(input), location.origin).pathname;
  const body = init?.body ? JSON.parse(String(init.body)) : {};
  let result: unknown;
  if (path.endsWith("/availability")) result = { enabled: true };
  else if (path.endsWith("/dashboard")) result = dash;
  else if (path.endsWith("/settings")) result = {};
  else if (path.endsWith("/sessions")) result = { sessionId: "demo" };
  else if (path.endsWith("/action")) { options ||= body.action === "options"; assisted ||= body.action === "help"; result = view(); }
  else if (path.endsWith("/submit")) { if (scenario !== "recall" && scenario !== "explanation" && !body.answer.selected?.length) throw Error("missing answer"); submittedAnswer = body.answer; confidence = body.confidence ?? null; submitted = true; result = view(); }
  else if (path.endsWith("/acknowledge")) {
    if (scenario === "recall" && typeof body.selfCorrect !== "boolean") throw Error("missing self-assessment");
    if (mode !== "exam" && scenario !== "explanation" && !view().reviewChoices?.some(c => c.rating === body.reviewRating)) throw Error("invalid recall rating");
    count++; submitted = false; options = Boolean(scenario); assisted = false; confidence = null; complete = count === 2; result = view();
  }
  else if (path.endsWith("/end")) { complete = true; result = view(); }
  else if (path.endsWith("/undo")) { count--; submitted = false; options = true; assisted = true; complete = false; result = view(); }
  else if (path.endsWith("/sessions/demo")) result = view();
  else throw Error(`Unexpected API ${path}`);
  return new Response(JSON.stringify(result), { headers: { "Content-Type": "application/json" } });
};
const { LearningPage } = await import("../src/learning/LearningPage");
const { GuidePage } = await import("../src/notices/GuidePage");
createRoot(document.getElementById("root")!).render(<MemoryRouter initialEntries={[scenario === "guide" ? "/guide#learning" : scenario === "recall" || scenario === "explanation" ? "/bank/local/demo?session=demo" : scenario === "exam" ? "/study?session=demo" : "/study"]}><Routes><Route path="/study" element={<LearningPage />} /><Route path="/bank/:subject/:runId" element={<LearningPage />} /><Route path="/guide" element={<GuidePage />} /></Routes></MemoryRouter>);

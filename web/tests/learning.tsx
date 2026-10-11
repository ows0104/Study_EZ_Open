// Interactive browser fixture: real screen, synthetic data, no account/network writes.
import { createRoot } from "react-dom/client";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import type { LearningAnswer, LearningDashboard, LearningSession } from "../src/types/learning";
import "../src/styles/base.css";
import choiceRounds from "./choice-pools.fixture.json";

const scenario = new URLSearchParams(location.search).get("scenario");
let mode: LearningSession["mode"] = scenario === "exam" ? "exam" : scenario === "recall" || scenario === "explanation" ? "extra" : "daily";
let submitted = false, options = true, assisted = false, complete = false, count = 0;
let submittedAnswer: LearningAnswer = {}, confidence: string | null = null;
const question = { question_id: "Q1", concept_id: "C1", format: scenario === "recall" ? "list" : "mcq", question: scenario === "recall" ? "학습 계획을 세울 때 먼저 확인할 세 가지는?" : "두 개념을 구별할 때 가장 먼저 확인할 것은?", options: scenario === "recall" ? [] : [{ id: "A", text: "두 개념의 차이를 만드는 조건" }, { id: "B", text: "문제에 사용된 보기의 순서" }], matching_left: [], matching_right: [], sequence_items: [], source_refs: [{ source_id: "S1", locator: "p12" }] };
const response = { answer: "A. 두 개념의 차이를 만드는 조건", answerUnits: [], correctOptionIds: ["A"], answerPairs: [], correctOrder: [], optionExplanations: [{ option_id: "A", text: "조건에 따라 결과가 달라지는 이유를 구별합니다." }, { option_id: "B", text: "보기 순서는 지식의 차이를 설명하지 않습니다." }], sourceRefs: question.source_refs, correct: true, confidence: "sure", explanation: "같은 결과처럼 보여도 발생하는 조건이 다를 수 있습니다. 그 차이를 기준으로 묶어 보세요.", minimum: "구별 조건 → 결과" };
if (scenario === "recall") Object.assign(response, { answer: "목표, 공부할 범위, 쓸 수 있는 시간", answerUnits: ["목표", "공부할 범위", "쓸 수 있는 시간"], correctOptionIds: [], optionExplanations: [], explanation: "목표와 범위를 먼저 정한 뒤 쓸 수 있는 시간 안에 분량을 배정합니다.", minimum: "목표 · 범위 · 시간" });
const round = () => choiceRounds[count % choiceRounds.length];
const media = { slides: [{ page: 12, url: "/tests/reference-slide.svg" }, { page: 13, url: "/tests/reference-slide.svg" }], missingSlidePages: [], sourceDocument: { filename: "참고 강의록.pdf", url: "/tests/reference-slide.svg" } };
const isCorrect = () => scenario === "choices" ? submittedAnswer.selected?.join() === round().feedback.correctOptionIds.join() : submittedAnswer.selected?.[0] === "A";
const feedback = () => scenario === "explanation" ? { explanation: response.explanation, minimum: response.minimum }
  : ({ ...(scenario === "choices" ? round().feedback : response), ...media, confidence, correct: scenario === "recall" ? null : isCorrect() });
const view = (): LearningSession => ({
  sessionId: "demo", mode, status: complete ? "complete" : "active", index: count, total: 2,
  seconds: 60 * count, canUndo: count > 0 && mode !== "exam", token: `token-${count}`,
  lane: mode === "daily" ? count ? "review" : "new" : mode,
  lecture: "강의 흐름과 개념 구별", subject: "local", runId: "demo",
  optionsShown: options, assisted: assisted || scenario === "explanation", submitted,
  question: scenario === "explanation" ? null : scenario === "choices" ? round().question : { ...question, options: options ? question.options : [] },
  recallPrompt: scenario ? undefined : "두 개념의 차이는 무엇으로 판단하나요?", objective: "개념 구별",
  help: assisted ? { context: "큰 흐름에서 개념을 구별하는 단계입니다.", explanation: response.explanation,
    minimum: response.minimum, rationale: "이 강의의 학습목표입니다.", source_refs: question.source_refs } : null,
  feedback: submitted && mode !== "exam" ? feedback() : null,
  reviewChoices: submitted && mode !== "exam" && scenario !== "explanation"
    ? (["Again", "Hard", "Good", "Easy"] as const).filter(rating => rating === "Again"
      || (!assisted && confidence !== "guess" && (scenario === "recall" || isCorrect())))
      .map(rating => ({ rating, dueAt: Date.now() + ({ Again: 1, Hard: 1, Good: 2, Easy: 8 }[rating]) * 86400000,
        intervalDays: { Again: 1, Hard: 1, Good: 2, Easy: 8 }[rating] })) : undefined,
  submittedAnswer: submitted ? submittedAnswer : null,
  summary: complete ? { completed: count, graded: scenario === "recall" || scenario === "explanation" ? 0 : count,
    correct: count, freshGraded: 1, freshCorrect: 1, newObjectives: 1, delayedRecall: 1, burden: null } : undefined,
  results: complete && mode === "exam" ? [{ ...feedback(), title: "개념 구별", question, submittedAnswer }] : undefined,
});
const progress = { total: 24, covered: 12, delayedRecall: 4, questionGaps: 1, legacyObjectives: 0 };
const dash: LearningDashboard = { enabled: true, minutes: 60, bufferDays: 3, progress, missingLectures: [{ title: "다음 강의", date: "2026-10-12" }], uncertainRanges: 1, activeSession: null, examQuestions: 6, plan: { budgetSeconds: 3600, estimatedSeconds: 2400, activeSeconds: 600, remaining: 2, complete: false, completed: ["done"], entries: [{ key: "done", lane: "review", seconds: 60 }, { key: "a", lane: "new", seconds: 120 }, { key: "b", lane: "review", seconds: 60 }], infeasible: false, newRequiredMinutes: 20, revision: 1 }, lectures: [{ ...progress, subject: "local", runId: "demo", title: "강의 흐름과 개념 구별" }], objectives: [{ key: "a", title: "두 개념의 구별", lecture: "강의 흐름과 개념 구별", subject: "local", runId: "demo", kind: "discrimination", sourceRefs: question.source_refs, covered: false, related: [] }] };
dash.workload = { unseen: 12, dueReviews: 3, nextReviewAt: Date.UTC(2026, 9, 13), firstPassTargetAt: Date.UTC(2026, 9, 17),
  examAt: Date.UTC(2026, 9, 20), today: { total: 3, completed: 1, remaining: 2, new: 1, review: 1, deferred: 0 } };
dash.lectures[0].workload = dash.workload;
if (scenario === "workload" || scenario === "budget") {
  dash.lectures.push({ subject: "약리학", runId: "done", title: "약물 대사와 배설", total: 16, covered: 16,
    delayedRecall: 3, questionGaps: 0, legacyObjectives: 16, workload: { ...dash.workload, unseen: 0, dueReviews: 0,
      today: { total: 2, completed: 2, remaining: 0, new: 0, review: 0, deferred: 0 } } });
  dash.progress = { total: 40, covered: 28, delayedRecall: 7, questionGaps: 1, legacyObjectives: 16 };
  dash.workload = { ...dash.workload, today: { ...dash.workload.today!, total: 5, completed: 3 } };
}
if (scenario === "budget") {
  dash.workload!.today = { total: 5, completed: 3, remaining: 0, new: 0, review: 0, deferred: 2 };
  dash.lectures[0].workload = { ...dash.workload!, today: { total: 3, completed: 1, remaining: 0, new: 0, review: 0, deferred: 2 } };
  dash.plan.complete = true; dash.plan.activeSeconds = dash.plan.budgetSeconds;
}
const scopedScenario = Boolean(scenario?.startsWith("scoped"));
if (scopedScenario) {
  dash.progress = { total: 80, covered: 0, delayedRecall: 0, questionGaps: 0, legacyObjectives: 80 };
  dash.workload = { ...dash.workload!, unseen: 80, dueReviews: 0, nextReviewAt: null,
    today: { total: 1, completed: 0, remaining: 1, new: 1, review: 0, deferred: 0 } };
  dash.lectures = [{ ...dash.progress, subject: "local", runId: "demo", title: "강의 흐름과 개념 구별", workload: dash.workload }];
  dash.plan.remaining = 1; dash.plan.infeasible = true; dash.plan.newRequiredMinutes = 471;
  dash.examQuestions = 0;
  if (scenario === "scoped-active") { dash.activeSession = "demo"; dash.activeSessionInfo = { lecture: "이전에 공부하던 강의", subject: "other", runId: "earlier" }; }
  if (scenario === "scoped-unassigned") { dash.plan.remaining = 0; dash.workload.today = { total: 0, completed: 0, remaining: 0, new: 0, review: 0, deferred: 0 }; }
  if (scenario === "scoped-complete") {
    dash.progress.covered = 80; dash.workload.unseen = 0; dash.workload.dueReviews = 3;
    dash.workload.today = { total: 2, completed: 2, remaining: 0, new: 0, review: 0, deferred: 0 };
    dash.plan.complete = true; dash.plan.remaining = 0; dash.examQuestions = 3;
  }
  if (scenario === "scoped-budget") {
    dash.workload.today = { total: 3, completed: 1, remaining: 0, new: 0, review: 0, deferred: 2 };
    dash.plan.complete = true; dash.plan.activeSeconds = dash.plan.budgetSeconds;
  }
  if (scenario === "scoped-empty" || scenario === "scoped-excluded") {
    dash.progress = { total: 0, covered: 0, delayedRecall: 0, questionGaps: 0, legacyObjectives: 0 };
    dash.workload = { ...dash.workload, unseen: 0, dueReviews: 0, today: null }; dash.lectures = [];
    dash.plan.remaining = 0;
    if (scenario === "scoped-excluded") dash.scopeOnlyLectures = [{ subject: "local", runId: "demo", title: "도입 강의", ranges: [{ title: "도입", status: "excluded", reason: "시험 범위 제외", source_refs: question.source_refs }] }];
  } else { dash.lectures[0] = { ...dash.lectures[0], ...dash.progress, workload: dash.workload }; }
}
window.fetch = async (input, init) => {
  const path = new URL(String(input), location.origin).pathname;
  const body = init?.body ? JSON.parse(String(init.body)) : {};
  let result: unknown;
  if (path.endsWith("/availability")) result = { enabled: true };
  else if (path.endsWith("/dashboard")) result = dash;
  else if (path.endsWith("/settings")) result = {};
  else if (path.endsWith("/sessions")) {
    if (scopedScenario && (body.subject !== "local" || body.runId !== "demo")) throw Error("scope lost");
    if (scenario === "scoped-unassigned" && body.mode !== "extra") throw Error("unassigned lecture must use extra");
    if (scenario === "scoped-budget" && body.mode !== "extra") throw Error("time budget must use extra");
    mode = body.mode; result = { sessionId: "demo" };
  }
  else if (path.endsWith("/action")) { options ||= body.action === "options"; assisted ||= body.action === "help"; result = view(); }
  else if (path.endsWith("/submit")) { if (scenario !== "recall" && scenario !== "explanation" && !body.answer.selected?.length) throw Error("missing answer"); submittedAnswer = body.answer; confidence = body.confidence ?? null; submitted = true; result = view(); }
  else if (path.endsWith("/acknowledge")) {
    if (scenario === "recall" && typeof body.selfCorrect !== "boolean") throw Error("missing self-assessment");
    if (mode !== "exam" && scenario !== "explanation" && !view().reviewChoices?.some(c => c.rating === body.reviewRating)) throw Error("invalid recall rating");
    count++; submitted = false; options = true; assisted = false; confidence = null; complete = count === 2; result = view();
  }
  else if (path.endsWith("/end")) { complete = true; result = view(); }
  else if (path.endsWith("/undo")) { count--; submitted = false; options = true; assisted = true; complete = false; result = view(); }
  else if (path.endsWith("/sessions/demo")) result = view();
  else throw Error(`Unexpected API ${path}`);
  return new Response(JSON.stringify(result), { headers: { "Content-Type": "application/json" } });
};
const { LearningPage } = await import("../src/learning/LearningPage");
const { GuidePage } = await import("../src/notices/GuidePage");
createRoot(document.getElementById("root")!).render(<MemoryRouter initialEntries={[scenario === "guide" ? "/guide#learning" : scopedScenario ? "/bank/local/demo" : scenario === "recall" || scenario === "explanation" ? "/bank/local/demo?session=demo" : scenario === "exam" || scenario === "choices" || scenario === "layout" ? "/study?session=demo" : "/study"]}><Routes><Route path="/study" element={<LearningPage />} /><Route path="/bank/:subject/:runId" element={<LearningPage />} /><Route path="/guide" element={<GuidePage />} /></Routes></MemoryRouter>);

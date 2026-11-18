/** 순서 맞추기 화면 눈으로 보기(2026-11-18 ordering-screen). ?answer=1이면 답면. 가짜 데이터만 쓴다. */
import React from "react";
import { createRoot } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import "../src/styles/base.css";
import "../src/bank/main-quiz.css";
import type { RootView } from "../src/types/rootLearning";
import { RootSolve } from "../src/bank/RootSolve";

const STEPS = ["세포 진입", "초기 전사", "추가 탈외피", "DNA 복제", "후기 유전자 발현", "입자 조립", "방출"];
const ids = STEPS.map((_, i) => `o${i}`);
const items = [3, 0, 6, 1, 5, 2, 4].map(i => ({ id: ids[i], text: STEPS[i] }));
const answered = new URLSearchParams(location.search).has("answer");
const view: RootView = {
  sessionId: "s1", revision: "v1", version: 1, day: "2026-11-18", policy: {} as RootView["policy"], position: 4, count: 20,
  finished: false, blocked: null, canUndo: true, mapSeen: false, summary: {} as RootView["summary"],
  task: { id: "t1", question: { question_id: "Q174", question: "폭스바이러스의 복제주기 단계는?", concept_id: "C1", tier: "Core", importance: 5,
    format: "list", retrieval_direction: "direct", source_refs: [], conflict_id: "", options: [], matching_left: [], matching_right: [],
    sequence_items: [], order_items: items } as never, response: null, attempted: answered ? true : null, helped: false,
    answer: answered ? { answer: STEPS.join("; "), answerUnits: STEPS, answerPairs: [], correctOrder: [], correctOptionIds: [],
      orderCorrectIds: ids, medicalReview: null, slides: [] } as never : null },
};
try { localStorage.setItem("studyez:main-quiz-mode", "mcq"); } catch { /* 이 화면은 저장소 없이도 객관식으로 시작하지 않는다 */ }
const root = createRoot(document.getElementById("root")!);
const draw = (v: RootView) => root.render(<MemoryRouter><RootSolve view={v} scope="look" disabled={false} advancing={false}
  onAction={() => {}} onToday={() => {}} onError={() => {}} /></MemoryRouter>);
draw({ ...view, task: { ...view.task!, answer: null } });
// 몇 단계를 놓은 뒤(답면이면 그다음 답을 받은 상태로).
const press = (key: string) => document.activeElement?.dispatchEvent(new KeyboardEvent("keydown", { key, code: `Digit${key}`, bubbles: true }));
setTimeout(async () => {
  for (const n of answered ? ["2", "4", "6", "1", "5", "3", "7"] : ["2", "4", "6"]) { press(n); await new Promise(r => setTimeout(r, 20)); }
  if (answered) draw(view);
}, 100);
